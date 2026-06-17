"""
scanner_cin.py — Scanner CIN ultra-rapide pour HealthGate
Stratégie : 1 capture rpicam-still + 3 prétraitements OCR parallèles + timeout 5s
Si incomplet → formulaire_manuel: True
"""

import cv2
import re
import os
import base64
import subprocess
import numpy as np
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout

try:
    import pytesseract
    TESSERACT_DISPONIBLE = True
except ImportError:
    TESSERACT_DISPONIBLE = False

TIMEOUT_OCR = 5.0
OCR_CONFIG  = '--psm 6 --oem 3'
OCR_LANG    = 'ara+fra'


# ─── 3 prétraitements ────────────────────────────────────────────────────────

def _prep_v1(img: np.ndarray) -> np.ndarray:
    """Niveaux de gris + seuillage Otsu."""
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, seuil = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return seuil


def _prep_v2(img: np.ndarray) -> np.ndarray:
    """CLAHE + seuillage adaptatif."""
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contraste = clahe.apply(gris)
    return cv2.adaptiveThreshold(
        contraste, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )


def _prep_v3(img: np.ndarray) -> np.ndarray:
    """Binarisation inverse + resize x2."""
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binaire = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return cv2.resize(binaire, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)


_PREPROCESSEURS = [_prep_v1, _prep_v2, _prep_v3]


# ─── OCR worker ──────────────────────────────────────────────────────────────

def _ocr_worker(img: np.ndarray, prep_fn) -> str:
    try:
        return pytesseract.image_to_string(prep_fn(img), lang=OCR_LANG, config=OCR_CONFIG)
    except Exception:
        return ""


# ─── Extraction des champs ───────────────────────────────────────────────────

def _extraire_champ(texte: str, patterns_label: list) -> str:
    """Cherche la valeur après un label (inline ou ligne suivante)."""
    lignes = texte.split('\n')
    for i, ligne in enumerate(lignes):
        for pat in patterns_label:
            if re.search(pat, ligne, re.IGNORECASE):
                # Valeur inline
                m = re.search(pat + r'\s*[:\-]?\s*(.+)', ligne, re.IGNORECASE)
                if m:
                    val = re.sub(r'[^؀-ۿa-zA-ZÀ-ÿ\s\-]', '', m.group(1)).strip()
                    if len(val) >= 2:
                        return val.title()
                # Valeur sur la ligne suivante
                if i + 1 < len(lignes):
                    val = re.sub(r'[^؀-ۿa-zA-ZÀ-ÿ\s\-]', '', lignes[i + 1]).strip()
                    if len(val) >= 2:
                        return val.title()
    return ""


def _extraire_nom(texte: str) -> str:
    return _extraire_champ(texte, [r'NOM', r'الاسم العائلي'])


def _extraire_prenom(texte: str) -> str:
    return _extraire_champ(texte, [r'PR[EÉ]NOM', r'الاسم الشخصي'])


def _extraire_date_naissance(texte: str) -> tuple:
    """Retourne (date DD/MM/YYYY, age) ou ('', None). Regex strict."""
    m = re.search(r'\b(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{4})\b', texte)
    if m:
        j, mo, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1900 <= a <= datetime.now().year and 1 <= mo <= 12 and 1 <= j <= 31:
            today = datetime.now()
            age = today.year - a - ((today.month, today.day) < (mo, j))
            if 0 < age < 120:
                return f"{j:02d}/{mo:02d}/{a}", age
    return "", None


def _fusionner(textes: list) -> dict:
    nom = prenom = date_n = ""
    age = None
    for texte in textes:
        if not nom:
            nom = _extraire_nom(texte)
        if not prenom:
            prenom = _extraire_prenom(texte)
        if not date_n:
            date_n, age = _extraire_date_naissance(texte)
        if nom and prenom and date_n:
            break
    return {"nom": nom, "prenom": prenom, "date_naissance": date_n, "age": age}


# ─── Capture rpicam-still ────────────────────────────────────────────────────

def _capturer_image() -> np.ndarray | None:
    chemin = '/tmp/scan_cin.jpg'
    try:
        subprocess.run(
            ['rpicam-still', '-o', chemin,
             '--width', '640', '--height', '480',
             '--immediate', '--timeout', '500', '--nopreview'],
            check=True, timeout=3
        )
        return cv2.imread(chemin)
    except Exception:
        return None
    finally:
        if os.path.exists(chemin):
            os.remove(chemin)


# ─── Fonction principale ──────────────────────────────────────────────────────

def scanner_piece_identite(source=None) -> dict:
    """
    Scan CIN rapide (5s max). Retourne formulaire_manuel=True si incomplet.

    source : None/int → rpicam-still | str → fichier | bytes → base64 | ndarray
    """
    # Charger l'image
    if isinstance(source, np.ndarray):
        image = source
    elif isinstance(source, bytes):
        try:
            nparr = np.frombuffer(base64.b64decode(source), np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception:
            image = None
    elif isinstance(source, str) and os.path.exists(source):
        image = cv2.imread(source)
    else:
        image = _capturer_image()

    if image is None:
        return _besoin_formulaire("Capture échouée")

    if not TESSERACT_DISPONIBLE:
        return _resultat_simulation()

    # 3 OCR en parallèle avec timeout global
    textes = []
    try:
        with ThreadPoolExecutor(max_workers=3) as ex:
            futures = [ex.submit(_ocr_worker, image, fn) for fn in _PREPROCESSEURS]
            try:
                for f in as_completed(futures, timeout=TIMEOUT_OCR):
                    t = f.result(timeout=0)
                    if t:
                        textes.append(t)
            except FuturesTimeout:
                for f in futures:
                    f.cancel()
    except Exception:
        pass

    if not textes:
        return _besoin_formulaire("OCR sans résultat")

    info = _fusionner(textes)

    if info["nom"] and info["prenom"] and info["date_naissance"]:
        return {
            "succes":            True,
            "formulaire_manuel": False,
            "nom":               info["nom"],
            "prenom":            info["prenom"],
            "date_naissance":    info["date_naissance"],
            "age":               info["age"] or 30,
            "sexe":              -1,
            "sexe_libelle":      "Non détecté",
            "texte_brut":        textes[0][:200],
            "message":           "Scan réussi",
        }

    return _besoin_formulaire("OCR incomplet", partial=info)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _besoin_formulaire(message: str, partial: dict = None) -> dict:
    partial = partial or {}
    return {
        "succes":            False,
        "formulaire_manuel": True,
        "nom":               partial.get("nom", ""),
        "prenom":            partial.get("prenom", ""),
        "date_naissance":    partial.get("date_naissance", ""),
        "age":               partial.get("age") or 30,
        "sexe":              -1,
        "sexe_libelle":      "Non détecté",
        "texte_brut":        "",
        "message":           message,
    }


def _resultat_simulation() -> dict:
    import random
    noms    = ["Alaoui", "Benali", "El Fassi", "Chraibi", "Tazi"]
    prenoms = ["Mohamed", "Fatima", "Ahmed", "Khadija", "Youssef"]
    return {
        "succes":            True,
        "formulaire_manuel": False,
        "nom":               random.choice(noms),
        "prenom":            random.choice(prenoms),
        "date_naissance":    "15/03/1985",
        "age":               random.randint(20, 70),
        "sexe":              random.choice([0, 1]),
        "sexe_libelle":      random.choice(["Homme", "Femme"]),
        "texte_brut":        "[Simulation]",
        "message":           "Mode simulation",
    }


def capturer_et_scanner(index_cam: int = 0) -> dict:
    return scanner_piece_identite(source=index_cam)


def pretraiter_image(image: np.ndarray) -> np.ndarray:
    """Compat avec les anciens appels."""
    return _prep_v1(image)


if __name__ == "__main__":
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else None
    r   = scanner_piece_identite(source=src)
    for k, v in r.items():
        print(f"  {k:<20} : {v}")
