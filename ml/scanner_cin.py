"""
scanner_cin.py — Scanner CIN universel pour HealthGate
Stratégie : rpicam-still → prétraitement séquentiel → tesseract subprocess (timeout 5s)
Supporte : Maroc, Côte d'Ivoire, Sénégal, Mali, et cartes africaines en général
Si incomplet → formulaire_manuel: True avec champs partiellement pré-remplis
"""

import cv2
import re
import os
import base64
import subprocess
import numpy as np
from datetime import datetime

TIMEOUT_CAPTURE   = 3    # secondes max pour rpicam-still
TIMEOUT_TESSERACT = 5    # secondes max pour tesseract
OCR_LANG          = 'fra+eng'
_IMG_TMP          = '/tmp/scan_processed.jpg'


# ─── Prétraitement image ─────────────────────────────────────────────────────

def _pretraiter(img: np.ndarray) -> np.ndarray:
    """Gris → CLAHE → Otsu THRESH_BINARY."""
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gris = clahe.apply(gris)
    _, seuil = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return seuil


# ─── OCR via subprocess tesseract (timeout strict) ───────────────────────────

def _ocr(img: np.ndarray) -> str:
    """Sauvegarde en /tmp/scan_processed.jpg puis appelle tesseract (timeout 5s)."""
    try:
        cv2.imwrite(_IMG_TMP, img)
        res = subprocess.run(
            ['tesseract', _IMG_TMP, 'stdout', '-l', OCR_LANG, '--psm', '6'],
            capture_output=True, text=True, timeout=TIMEOUT_TESSERACT
        )
        return res.stdout
    except subprocess.TimeoutExpired:
        print("[SCANNER] Tesseract timeout (5s)")
        return ""
    except FileNotFoundError:
        print("[SCANNER] tesseract non installé")
        return ""
    except Exception as e:
        print(f"[SCANNER] Erreur tesseract : {e}")
        return ""
    finally:
        if os.path.exists(_IMG_TMP):
            os.remove(_IMG_TMP)


# ─── Extraction des champs ───────────────────────────────────────────────────

_LABELS_A_IGNORER = {
    'NOM', 'NAME', 'SURNAME', 'PRENOM', 'PRÉNOM', 'GIVEN', 'FIRST',
    'DATE', 'BIRTH', 'BORN', 'DOB', 'NAISSANCE', 'SEXE', 'SEX',
    'NATIONALITY', 'NATIONALITE', 'NATIONALITÉ', 'PLACE', 'LIEU',
    'EXPIRY', 'EXPIRES', 'VALID', 'ISSUED', 'PRENOMS', 'PRÉNOMS',
}


def _nettoyer(val: str) -> str:
    return re.sub(r'[^a-zA-ZÀ-ÿ\s\-\']', '', val).strip()


def _apres_label(texte: str, patterns: list) -> str:
    """Retourne la valeur sur la même ligne après ':', ou la ligne suivante."""
    lignes = texte.split('\n')
    for i, ligne in enumerate(lignes):
        for pat in patterns:
            if re.search(pat, ligne, re.IGNORECASE):
                m = re.search(pat + r'\s*:?\s*(.+)', ligne, re.IGNORECASE)
                if m:
                    val = _nettoyer(m.group(1))
                    if len(val) >= 2:
                        return val.title()
                # Valeur sur la ligne suivante
                for j in range(i + 1, min(i + 3, len(lignes))):
                    val = _nettoyer(lignes[j])
                    if len(val) >= 2:
                        return val.title()
    return ""


def _extraire_nom(texte: str) -> str:
    # Labels directs
    val = _apres_label(texte, [r'\bNOM\b', r'\bNAME\b', r'\bSURNAME\b'])
    if val:
        return val
    # Fallback : première ligne tout-majuscules avec 2+ mots
    for ligne in texte.split('\n'):
        ligne = ligne.strip()
        if not ligne or any(c.isdigit() for c in ligne):
            continue
        mots = ligne.split()
        if len(mots) < 2:
            continue
        chars_alpha = [c for c in ligne if c.isalpha()]
        if not chars_alpha or not all(c.isupper() for c in chars_alpha):
            continue
        if any(m.upper() in _LABELS_A_IGNORER for m in mots):
            continue
        val = _nettoyer(ligne)
        if len(val) >= 4:
            return val.title()
    return ""


def _extraire_prenom(texte: str) -> str:
    return _apres_label(texte, [
        r'\bPR[EÉ]NOMS?\b', r'\bFIRST\s*NAME\b', r'\bGIVEN\s*NAME\b', r'\bFORENAME\b',
    ])


def _extraire_date_naissance(texte: str) -> tuple:
    """Retourne (date DD/MM/YYYY, age) ou ('', None). Cherche \d{2}/\d{2}/\d{4} en priorité."""
    def _valider(j, mo, a):
        if 1900 <= a <= datetime.now().year and 1 <= mo <= 12 and 1 <= j <= 31:
            today = datetime.now()
            age = today.year - a - ((today.month, today.day) < (mo, j))
            if 0 < age < 120:
                return f"{j:02d}/{mo:02d}/{a}", age
        return None, None

    # Priorité : après label contextuel (né(e), date, born)
    ctx = re.search(
        r'(?:n[eé]e?\s*(?:le)?|naissance|date|born)[^\d]{0,15}(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{4})',
        texte, re.IGNORECASE
    )
    if ctx:
        date, age = _valider(int(ctx.group(1)), int(ctx.group(2)), int(ctx.group(3)))
        if date:
            return date, age

    # Regex directe DD/MM/YYYY ou DD-MM-YYYY n'importe où dans le texte
    m = re.search(r'\b(\d{2})[\/\-](\d{2})[\/\-](\d{4})\b', texte)
    if m:
        date, age = _valider(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if date:
            return date, age

    # YYYY-MM-DD
    m = re.search(r'\b(\d{4})[\/\-](\d{2})[\/\-](\d{2})\b', texte)
    if m:
        date, age = _valider(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if date:
            return date, age

    return "", None


def _extraire_sexe(texte: str) -> tuple:
    """Retourne (code 0/1/-1, libellé). 0=Femme, 1=Homme, -1=Non détecté."""
    m = re.search(
        r'(?:sexe|sex|genre)\s*[:\-]?\s*([MF])\b|'
        r'\b(masculin|male|homme)\b|\b(f[eé]minin|female|femme)\b',
        texte, re.IGNORECASE
    )
    if not m:
        return -1, "Non détecté"
    texte_match = (m.group(1) or m.group(2) or m.group(3) or "").upper()
    if texte_match in ('M', 'MASCULIN', 'MALE', 'HOMME'):
        return 1, "Homme"
    if texte_match in ('F', 'FÉMININ', 'FEMININ', 'FEMALE', 'FEMME'):
        return 0, "Femme"
    return -1, "Non détecté"


def _extraire_nationalite(texte: str) -> str:
    return _apres_label(texte, [r'\bNATIONALIT[EÉ]\b', r'\bNATIONALITY\b'])


def _extraire_tout(texte: str) -> dict:
    """Extrait tous les champs et logue les résultats."""
    print(f"[SCANNER] OCR ({len(texte)} chars) : {repr(texte[:150])}")

    nom = _extraire_nom(texte)
    print(f"[SCANNER] NOM        → {repr(nom) if nom else 'non trouvé'}")

    prenom = _extraire_prenom(texte)
    # Fallback : ligne suivant le nom
    if not prenom and nom:
        lignes = texte.split('\n')
        nom_low = nom.lower()
        for i, l in enumerate(lignes):
            if nom_low in l.lower():
                for j in range(i + 1, min(i + 3, len(lignes))):
                    val = _nettoyer(lignes[j])
                    if len(val) >= 2 and val.upper() not in _LABELS_A_IGNORER:
                        prenom = val.title()
                        print(f"[SCANNER] PRENOM     → {repr(prenom)} (fallback après nom)")
                        break
                if prenom:
                    break
    print(f"[SCANNER] PRENOM     → {repr(prenom) if prenom else 'non trouvé'}")

    date_n, age = _extraire_date_naissance(texte)
    print(f"[SCANNER] DATE_NAISS → {repr(date_n) if date_n else 'non trouvée'}")

    sexe_code, sexe_lib = _extraire_sexe(texte)
    nationalite = _extraire_nationalite(texte)

    print(f"[SCANNER] Résultat : nom={repr(nom)} prenom={repr(prenom)} date={repr(date_n)} sexe={sexe_lib}")
    return {"nom": nom, "prenom": prenom, "date_naissance": date_n,
            "age": age, "sexe": sexe_code, "sexe_libelle": sexe_lib,
            "nationalite": nationalite}


# ─── Capture rpicam-still ────────────────────────────────────────────────────

def _capturer_image() -> np.ndarray | None:
    chemin = '/tmp/scan_cin_raw.jpg'
    try:
        subprocess.run(
            ['rpicam-still', '-o', chemin,
             '--width', '1280', '--height', '720',
             '--immediate', '--timeout', '500', '--nopreview'],
            check=True, timeout=TIMEOUT_CAPTURE
        )
        return cv2.imread(chemin)
    except Exception as e:
        print(f"[SCANNER] Capture échouée : {e}")
        return None
    finally:
        if os.path.exists(chemin):
            os.remove(chemin)


# ─── Fonction principale ──────────────────────────────────────────────────────

def scanner_piece_identite(source=None) -> dict:
    """
    Scan CIN (< 8s). Pipeline séquentiel : capture → prétraitement → tesseract.
    Retourne formulaire_manuel=True avec champs partiels si extraction incomplète.

    source : None → rpicam-still | str → fichier | bytes → base64 | ndarray
    """
    # Chargement image
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

    # Prétraitement + OCR séquentiel
    img_prep = _pretraiter(image)
    texte = _ocr(img_prep)

    if not texte.strip():
        print("[SCANNER] Tesseract n'a produit aucun texte")
        return _besoin_formulaire("OCR sans résultat")

    info = _extraire_tout(texte)

    if info["nom"] and info["prenom"] and info["date_naissance"]:
        return {
            "succes":            True,
            "formulaire_manuel": False,
            "nom":               info["nom"],
            "prenom":            info["prenom"],
            "date_naissance":    info["date_naissance"],
            "age":               info["age"] or 30,
            "nationalite":       info["nationalite"],
            "sexe":              info["sexe"],
            "sexe_libelle":      info["sexe_libelle"],
            "texte_brut":        texte[:200],
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
        "nationalite":       partial.get("nationalite", ""),
        "sexe":              partial.get("sexe", -1),
        "sexe_libelle":      partial.get("sexe_libelle", "Non détecté"),
        "texte_brut":        "",
        "message":           message,
    }


def _resultat_simulation() -> dict:
    import random
    noms    = ["Alaoui", "Koné", "Diallo", "Traoré", "Benali", "El Fassi", "Touré", "Sy"]
    prenoms = ["Mohamed", "Fatima", "Aminata", "Mamadou", "Ahmed", "Aïssatou", "Ibrahim"]
    return {
        "succes":            True,
        "formulaire_manuel": False,
        "nom":               random.choice(noms),
        "prenom":            random.choice(prenoms),
        "date_naissance":    "15/03/1985",
        "age":               random.randint(20, 70),
        "nationalite":       "",
        "sexe":              random.choice([0, 1]),
        "sexe_libelle":      random.choice(["Homme", "Femme"]),
        "texte_brut":        "[Simulation]",
        "message":           "Mode simulation",
    }


def capturer_et_scanner(index_cam: int = 0) -> dict:
    return scanner_piece_identite()


def pretraiter_image(image: np.ndarray) -> np.ndarray:
    """Compat avec les anciens appels."""
    return _pretraiter(image)


if __name__ == "__main__":
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else None
    r   = scanner_piece_identite(source=src)
    for k, v in r.items():
        print(f"  {k:<20} : {v}")
