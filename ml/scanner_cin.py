"""
scanner_cin.py — Scanner CIN universel pour HealthGate
Stratégie : rpicam-still → EasyOCR (init unique au démarrage) → extraction
Supporte : Maroc, Côte d'Ivoire, Sénégal, Mali, et cartes africaines en général
Si incomplet → formulaire_manuel: True avec champs partiellement pré-remplis

Note perf : premier import prend ~30s (chargement modèles EasyOCR),
            les scans suivants sont rapides (~2-4s).
"""

import re
import os
import base64
import subprocess
import numpy as np
from datetime import datetime

try:
    import cv2
    CV2_DISPONIBLE = True
except ImportError:
    CV2_DISPONIBLE = False

# ─── Init EasyOCR unique au chargement du module ─────────────────────────────

try:
    import easyocr
    print("[SCANNER] Chargement EasyOCR (première fois ~30s)...")
    _reader = easyocr.Reader(['fr', 'en'], gpu=False, verbose=False)
    EASYOCR_DISPONIBLE = True
    print("[SCANNER] EasyOCR prêt.")
except Exception as _e:
    _reader = None
    EASYOCR_DISPONIBLE = False
    print(f"[SCANNER] EasyOCR non disponible : {_e}")

TIMEOUT_CAPTURE = 4     # secondes max pour rpicam-still
_IMG_TMP        = '/tmp/cin.jpg'


# ─── OCR via EasyOCR ─────────────────────────────────────────────────────────

def _ocr(image_path: str) -> str:
    """
    Lance EasyOCR sur le fichier image et retourne le texte reconstruit.
    Les blocs sont triés par coordonnée Y (haut→bas) pour reconstituer l'ordre de lecture.
    """
    try:
        resultats = _reader.readtext(image_path, detail=1, paragraph=False)
        if not resultats:
            return ""
        # Trier par Y du coin supérieur gauche du bbox
        tries = sorted(resultats, key=lambda r: r[0][0][1])
        return '\n'.join(texte for _, texte, _ in tries)
    except Exception as e:
        print(f"[SCANNER] Erreur EasyOCR : {e}")
        return ""


# ─── Extraction des champs ───────────────────────────────────────────────────

_LABELS_A_IGNORER = {
    'NOM', 'NAME', 'SURNAME', 'PRENOM', 'PRÉNOM', 'GIVEN', 'FIRST',
    'DATE', 'BIRTH', 'BORN', 'DOB', 'NAISSANCE', 'SEXE', 'SEX',
    'NATIONALITY', 'NATIONALITE', 'NATIONALITÉ', 'PLACE', 'LIEU',
    'EXPIRY', 'EXPIRES', 'VALID', 'ISSUED', 'PRENOMS', 'PRÉNOMS',
}


def _nettoyer(val: str) -> str:
    return re.sub(r'[^a-zA-ZÀ-ÿ\s\-\']', '', val).strip()


_MOT_LABEL_RE = re.compile(
    r'^\s*(?:nom|name|surname|pr[eé]noms?|given|first|date|n[eé]e?|naissance|'
    r'sexe|sex|nationality|nationalit[eé]|lieu|born|expiry)\s*:',
    re.IGNORECASE
)


def _est_ligne_label(ligne: str) -> bool:
    """Vrai si la ligne est un label de champ (ex: 'Nom:', 'Prenoms:')."""
    return bool(_MOT_LABEL_RE.match(ligne))


def _apres_label(texte: str, patterns: list) -> str:
    """Retourne la valeur sur la même ligne après ':', ou la 1ère ligne suivante non-label."""
    lignes = texte.split('\n')
    for i, ligne in enumerate(lignes):
        for pat in patterns:
            if re.search(pat, ligne, re.IGNORECASE):
                # Valeur inline (après le label sur la même ligne)
                m = re.search(pat + r'\s*:?\s*(.+)', ligne, re.IGNORECASE)
                if m:
                    val = _nettoyer(m.group(1))
                    if len(val) >= 2:
                        return val.title()
                # Valeur sur la ligne suivante — skip les lignes de label
                for j in range(i + 1, min(i + 3, len(lignes))):
                    if _est_ligne_label(lignes[j]):
                        continue
                    val = _nettoyer(lignes[j])
                    if len(val) >= 2:
                        return val.title()
    return ""


_MOT_DATE_RE = re.compile(r'\bn[eé]e?\b', re.IGNORECASE)


def _supprimer_mots_date(val: str) -> str:
    """Supprime 'Née', 'Né', 'Nee' isolés qui contaminent le prénom."""
    return _MOT_DATE_RE.sub('', val).strip()


def _extraire_nom(texte: str) -> str:
    # Colon requis pour éviter de matcher "Prenoms" avec le pattern "Nom"
    val = _apres_label(texte, [r'\bNom\s*:', r'\bName\s*:', r'\bSurname\s*:'])
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
    val = _apres_label(texte, [
        r'\bPr[eé]noms?\s*:', r'\bFirst\s*Name\s*:', r'\bGiven\s*Name\s*:', r'\bForename\s*:',
    ])
    return _supprimer_mots_date(val) if val else ""


def _extraire_date_naissance(texte: str) -> tuple:
    """Retourne (date DD/MM/YYYY, age) ou ('', None)."""
    def _valider(j, mo, a):
        if 1900 <= a <= datetime.now().year and 1 <= mo <= 12 and 1 <= j <= 31:
            today = datetime.now()
            age = today.year - a - ((today.month, today.day) < (mo, j))
            if 0 < age < 120:
                return f"{j:02d}/{mo:02d}/{a}", age
        return None, None

    # Priorité : après label Né(e), date, born
    ctx = re.search(
        r'(?:n[eé]e?\s*(?:le)?|naissance|date|born)[^\d]{0,15}(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{4})',
        texte, re.IGNORECASE
    )
    if ctx:
        date, age = _valider(int(ctx.group(1)), int(ctx.group(2)), int(ctx.group(3)))
        if date:
            return date, age

    # DD/MM/YYYY ou DD-MM-YYYY n'importe où
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
    val = (m.group(1) or m.group(2) or m.group(3) or "").upper()
    if val in ('M', 'MASCULIN', 'MALE', 'HOMME'):
        return 1, "Homme"
    if val in ('F', 'FÉMININ', 'FEMININ', 'FEMALE', 'FEMME'):
        return 0, "Femme"
    return -1, "Non détecté"


def _extraire_nationalite(texte: str) -> str:
    return _apres_label(texte, [r'\bNATIONALIT[EÉ]\b', r'\bNATIONALITY\b'])


def _extraire_tout(texte: str) -> dict:
    """Extrait tous les champs avec logs détaillés."""
    print(f"[SCANNER] OCR ({len(texte)} chars) : {repr(texte[:150])}")

    nom = _extraire_nom(texte)
    print(f"[SCANNER] NOM        → {repr(nom) if nom else 'non trouvé'}")

    prenom = _extraire_prenom(texte)
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

def _capturer(chemin: str) -> bool:
    """Capture avec rpicam-still en 1920×1080. Retourne True si succès."""
    try:
        subprocess.run(
            ['rpicam-still', '-o', chemin,
             '--width', '1920', '--height', '1080',
             '--immediate', '--timeout', '1000', '--nopreview'],
            check=True, timeout=TIMEOUT_CAPTURE
        )
        return os.path.exists(chemin)
    except Exception as e:
        print(f"[SCANNER] Capture échouée : {e}")
        return False


# ─── Fonction principale ──────────────────────────────────────────────────────

def scanner_piece_identite(source=None) -> dict:
    """
    Scan CIN via EasyOCR. Pipeline : capture → EasyOCR → extraction.
    Retourne formulaire_manuel=True avec champs partiels si extraction incomplète.

    source : None → rpicam-still | str (chemin fichier) | bytes (base64) | ndarray
    """
    if not EASYOCR_DISPONIBLE:
        return _resultat_simulation()

    image_path = None
    fichier_temporaire = False

    try:
        if isinstance(source, str) and os.path.exists(source):
            image_path = source

        elif isinstance(source, (bytes, bytearray)):
            try:
                nparr = np.frombuffer(base64.b64decode(source), np.uint8)
                if CV2_DISPONIBLE:
                    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    cv2.imwrite(_IMG_TMP, img)
                    image_path = _IMG_TMP
                    fichier_temporaire = True
            except Exception:
                pass

        elif isinstance(source, np.ndarray) and CV2_DISPONIBLE:
            cv2.imwrite(_IMG_TMP, source)
            image_path = _IMG_TMP
            fichier_temporaire = True

        else:
            # Capture rpicam-still
            ok = _capturer(_IMG_TMP)
            if not ok:
                return _besoin_formulaire("Capture échouée")
            image_path = _IMG_TMP
            fichier_temporaire = True

        if image_path is None:
            return _besoin_formulaire("Source image invalide")

        texte = _ocr(image_path)

        if not texte.strip():
            print("[SCANNER] EasyOCR n'a produit aucun texte")
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

    finally:
        if fichier_temporaire and image_path and os.path.exists(image_path):
            os.remove(image_path)


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
        "message":           "Mode simulation (EasyOCR non disponible)",
    }


def capturer_et_scanner(index_cam: int = 0) -> dict:
    return scanner_piece_identite()


def pretraiter_image(image: np.ndarray) -> np.ndarray:
    """Compat avec les anciens appels — applique CLAHE+Otsu."""
    if not CV2_DISPONIBLE:
        return image
    gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gris = clahe.apply(gris)
    _, seuil = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return seuil


if __name__ == "__main__":
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else None
    r   = scanner_piece_identite(source=src)
    for k, v in r.items():
        print(f"  {k:<20} : {v}")
