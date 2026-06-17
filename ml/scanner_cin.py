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

TIMEOUT_CAPTURE  = 3    # secondes max pour rpicam-still
TIMEOUT_TESSERACT = 5   # secondes max pour tesseract
OCR_LANG         = 'ara+fra+eng'
_IMG_TMP         = '/tmp/scan_cin_prep.png'


# ─── Prétraitement image (pipeline unique séquentiel) ────────────────────────

def _pretraiter(img: np.ndarray) -> np.ndarray:
    """Gris → CLAHE → luminosité → resize x2 → Otsu."""
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gris = clahe.apply(gris)
    gris = cv2.convertScaleAbs(gris, alpha=1.5, beta=30)
    gris = cv2.resize(gris, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    _, seuil = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return seuil


# ─── OCR via subprocess tesseract (timeout strict) ───────────────────────────

def _ocr(img: np.ndarray) -> str:
    """Sauvegarde l'image prétraitée puis appelle tesseract avec timeout=5s."""
    try:
        cv2.imwrite(_IMG_TMP, img)
        res = subprocess.run(
            ['tesseract', _IMG_TMP, 'stdout',
             '-l', OCR_LANG, '--psm', '6', '--oem', '3'],
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
    'EXPIRY', 'EXPIRES', 'VALID', 'ISSUED', 'COGNOME', 'NOME',
    'PRENOMS', 'PRÉNOMS',
}


def _nettoyer(val: str) -> str:
    return re.sub(r'[^؀-ۿa-zA-ZÀ-ÿ\s\-\']', '', val).strip()


def _extraire_champ(texte: str, patterns_label: list) -> str:
    """Cherche la valeur après un label (inline ou ligne suivante)."""
    lignes = texte.split('\n')
    for i, ligne in enumerate(lignes):
        for pat in patterns_label:
            if re.search(pat, ligne, re.IGNORECASE):
                m = re.search(pat + r'\s*[:\-]?\s*(.+)', ligne, re.IGNORECASE)
                if m:
                    val = _nettoyer(m.group(1))
                    if len(val) >= 2:
                        return val.title()
                for j in range(i + 1, min(i + 3, len(lignes))):
                    val = _nettoyer(lignes[j])
                    if len(val) >= 2:
                        return val.title()
    return ""


def _fallback_nom_majuscules(texte: str) -> str:
    """Première ligne tout-majuscules avec 2+ mots, sans chiffres ni labels."""
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


def _extraire_nom(texte: str) -> str:
    patterns = [
        r'\bNOM\b', r'\bNAME\b', r'\bSURNAME\b', r'\bCOGNOME\b',
        r'الاسم\s*العائلي', r'\bالاسم\b', r'\bاللقب\b',
    ]
    return _extraire_champ(texte, patterns) or _fallback_nom_majuscules(texte)


def _extraire_prenom(texte: str) -> str:
    patterns = [
        r'\bPR[EÉ]NOMS?\b', r'\bFIRST\s*NAME\b', r'\bGIVEN\s*NAME\b',
        r'\bFORENAME\b', r'\bGIVEN\b',
        r'الاسم\s*الشخصي', r'\bالشخصي\b',
    ]
    return _extraire_champ(texte, patterns)


def _fallback_prenom_apres_nom(texte: str, nom: str) -> str:
    """Prend la ligne suivant le nom si aucun label prénom trouvé."""
    lignes = texte.split('\n')
    nom_normalise = nom.lower()
    for i, ligne in enumerate(lignes):
        if nom_normalise in ligne.lower():
            for j in range(i + 1, min(i + 3, len(lignes))):
                val = _nettoyer(lignes[j])
                if len(val) >= 2 and val.upper() not in _LABELS_A_IGNORER:
                    return val.title()
    return ""


def _extraire_date_naissance(texte: str) -> tuple:
    """Retourne (date DD/MM/YYYY, age) ou ('', None)."""
    def _valider(j, mo, a):
        if 1900 <= a <= datetime.now().year and 1 <= mo <= 12 and 1 <= j <= 31:
            today = datetime.now()
            age = today.year - a - ((today.month, today.day) < (mo, j))
            if 0 < age < 120:
                return f"{j:02d}/{mo:02d}/{a}", age
        return None, None

    # DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
    m = re.search(r'\b(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})\b', texte)
    if m:
        date, age = _valider(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if date:
            return date, age

    # YYYY-MM-DD ou YYYY/MM/DD
    m = re.search(r'\b(\d{4})[\/\-\.](\d{1,2})[\/\-\.](\d{1,2})\b', texte)
    if m:
        date, age = _valider(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if date:
            return date, age

    # DD MM YYYY après label contextuel multilingue
    ctx = re.search(
        r'(?:n[eé](?:e)?\s*(?:le)?|naissance|date\s*of\s*birth|dob|born|تاريخ\s*(?:الولادة|الميلاد)?)'
        r'[^\d]{0,20}(\d{1,2})\s+(\d{1,2})\s+(\d{4})',
        texte, re.IGNORECASE
    )
    if ctx:
        date, age = _valider(int(ctx.group(1)), int(ctx.group(2)), int(ctx.group(3)))
        if date:
            return date, age

    # Fallback DD MM YYYY sans label
    m = re.search(r'\b(\d{1,2})\s+(\d{2})\s+(\d{4})\b', texte)
    if m:
        date, age = _valider(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if date:
            return date, age

    return "", None


def _extraire_nationalite(texte: str) -> str:
    return _extraire_champ(texte, [
        r'\bNATIONALIT[EÉ]\b', r'\bNATIONALITY\b',
        r'\bNATIONALIT[AÀ]\b', r'الجنسية',
    ])


def _extraire_tout(texte: str) -> dict:
    """Extrait tous les champs et logue les résultats."""
    print(f"[SCANNER] OCR ({len(texte)} chars) : {repr(texte[:150])}")

    nom = _extraire_nom(texte)
    print(f"[SCANNER] NOM        → {repr(nom) if nom else 'non trouvé'}")

    prenom = _extraire_prenom(texte)
    if not prenom and nom:
        prenom = _fallback_prenom_apres_nom(texte, nom)
        if prenom:
            print(f"[SCANNER] PRENOM     → {repr(prenom)} (fallback après nom)")
    print(f"[SCANNER] PRENOM     → {repr(prenom) if prenom else 'non trouvé'}")

    date_n, age = _extraire_date_naissance(texte)
    print(f"[SCANNER] DATE_NAISS → {repr(date_n) if date_n else 'non trouvée'}")

    nationalite = _extraire_nationalite(texte)

    print(f"[SCANNER] Résultat : nom={repr(nom)} prenom={repr(prenom)} date={repr(date_n)}")
    return {"nom": nom, "prenom": prenom, "date_naissance": date_n,
            "age": age, "nationalite": nationalite}


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
            "sexe":              -1,
            "sexe_libelle":      "Non détecté",
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
        "sexe":              -1,
        "sexe_libelle":      "Non détecté",
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
