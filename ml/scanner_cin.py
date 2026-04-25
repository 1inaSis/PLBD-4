"""
scanner_cin.py — Scanner de pièce d'identité pour HealthGate
Projet HealthGate | Centrale Casablanca | PLBD 4 | 2025-2026

Utilise OpenCV + Tesseract OCR pour extraire :
- Nom, prénom, âge, sexe depuis une photo de CIN ou passeport

Compatible : Raspberry Pi (picamera2) + PC (webcam USB)
"""

import cv2
import re
import os
import base64
import numpy as np
from datetime import datetime

# Tesseract OCR — installation requise :
# Windows : https://github.com/UB-Mannheim/tesseract/wiki
# Linux/Pi : sudo apt install tesseract-ocr tesseract-ocr-fra tesseract-ocr-ara
try:
    import pytesseract
    # Windows : décommenter la ligne suivante avec votre chemin
    # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    TESSERACT_DISPONIBLE = True
except ImportError:
    TESSERACT_DISPONIBLE = False
    print("[AVERTISSEMENT] pytesseract non installé — mode simulation activé")


# ─────────────────────────────────────────────────────────────────────────────
# Prétraitement de l'image pour améliorer l'OCR
# ─────────────────────────────────────────────────────────────────────────────

def pretraiter_image(image: np.ndarray) -> np.ndarray:
    """
    Améliore la qualité de l'image pour l'OCR :
    - Redimensionnement
    - Niveaux de gris
    - Débruitage
    - Seuillage adaptatif
    """
    # Redimensionner si trop petite
    hauteur, largeur = image.shape[:2]
    if largeur < 800:
        facteur = 800 / largeur
        image = cv2.resize(image, None, fx=facteur, fy=facteur,
                           interpolation=cv2.INTER_CUBIC)

    # Convertir en niveaux de gris
    gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Débruitage
    debruite = cv2.fastNlMeansDenoising(gris, h=10)

    # Améliorer le contraste
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contraste = clahe.apply(debruite)

    # Seuillage adaptatif
    seuil = cv2.adaptiveThreshold(
        contraste, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )

    return seuil


def extraire_zone_texte(image: np.ndarray) -> np.ndarray:
    """
    Détecte et extrait la zone principale de texte sur la carte.
    Retourne l'image complète si la détection échoue.
    """
    gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binaire = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Trouver les contours
    contours, _ = cv2.findContours(binaire, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        # Trouver le plus grand rectangle
        plus_grand = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(plus_grand)

        # Vérifier que c'est une zone raisonnable (>30% de l'image)
        if w * h > 0.3 * image.shape[0] * image.shape[1]:
            return image[y:y+h, x:x+w]

    return image


# ─────────────────────────────────────────────────────────────────────────────
# Extraction des informations depuis le texte OCR
# ─────────────────────────────────────────────────────────────────────────────

def extraire_nom_prenom(texte: str) -> tuple:
    """Extrait le nom et prénom depuis le texte OCR."""
    lignes = [l.strip() for l in texte.split('\n') if l.strip()]

    nom = "Inconnu"
    prenom = "Inconnu"

    for i, ligne in enumerate(lignes):
        ligne_upper = ligne.upper()

        # Chercher les marqueurs explicites
        if any(m in ligne_upper for m in ['NOM:', 'NOM :', 'SURNAME', 'LAST NAME']):
            valeur = re.sub(r'(NOM\s*:?|SURNAME\s*:?)', '', ligne, flags=re.IGNORECASE).strip()
            if valeur:
                nom = valeur.title()

        elif any(m in ligne_upper for m in ['PRÉNOM', 'PRENOM', 'FIRST NAME', 'GIVEN']):
            valeur = re.sub(r'(PRÉNOM\s*:?|PRENOM\s*:?|FIRST NAME\s*:?)', '',
                           ligne, flags=re.IGNORECASE).strip()
            if valeur:
                prenom = valeur.title()

    # Si pas trouvé avec marqueurs, prendre les premières lignes en majuscules
    if nom == "Inconnu":
        for ligne in lignes[:6]:
            if re.match(r'^[A-ZÀÂÉÈÊËÎÏÔÙÛÜÇ\s\-]{3,30}$', ligne.upper()):
                if nom == "Inconnu":
                    nom = ligne.title()
                elif prenom == "Inconnu":
                    prenom = ligne.title()
                    break

    return nom, prenom


def extraire_date_naissance(texte: str) -> tuple:
    """
    Extrait la date de naissance et calcule l'âge.
    Retourne (date_str, age).
    """
    # Formats de date courants sur les CIN
    patterns = [
        r'(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{4})',  # DD/MM/YYYY
        r'(\d{4})[\/\-\.](\d{2})[\/\-\.](\d{2})',  # YYYY/MM/DD
        r'(\d{2})\s+(jan|fév|mar|avr|mai|jun|jul|aoû|sep|oct|nov|déc)[a-z]*\s+(\d{4})',
        r'(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{2})',  # DD/MM/YY
    ]

    mois_fr = {
        'jan': 1, 'fév': 2, 'mar': 3, 'avr': 4, 'mai': 5, 'jun': 6,
        'jul': 7, 'aoû': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'déc': 12
    }

    texte_lower = texte.lower()

    for pattern in patterns:
        match = re.search(pattern, texte_lower)
        if match:
            groupes = match.groups()
            try:
                if len(groupes[0]) == 4:  # YYYY/MM/DD
                    annee = int(groupes[0])
                    mois  = int(groupes[1])
                    jour  = int(groupes[2])
                elif isinstance(groupes[1], str) and groupes[1][:3] in mois_fr:
                    jour  = int(groupes[0])
                    mois  = mois_fr[groupes[1][:3]]
                    annee = int(groupes[2])
                else:
                    jour  = int(groupes[0])
                    mois  = int(groupes[1])
                    annee = int(groupes[2])
                    if annee < 100:
                        annee += 1900 if annee > 24 else 2000

                # Calcul de l'âge
                aujourd_hui = datetime.now()
                age = aujourd_hui.year - annee
                if (aujourd_hui.month, aujourd_hui.day) < (mois, jour):
                    age -= 1

                date_str = f"{jour:02d}/{mois:02d}/{annee}"
                if 0 < age < 120:
                    return date_str, age

            except (ValueError, TypeError):
                continue

    return "Inconnue", 30  # valeur par défaut


def extraire_sexe(texte: str) -> int:
    """
    Extrait le sexe depuis le texte OCR.
    Retourne 0 = Femme, 1 = Homme.
    """
    texte_upper = texte.upper()

    indicateurs_homme = ['SEXE: M', 'SEXE:M', 'SEX: M', 'SEX:M',
                         'MASCULIN', 'MALE', 'M\n', '\nM\n', 'GENRE: M']
    indicateurs_femme = ['SEXE: F', 'SEXE:F', 'SEX: F', 'SEX:F',
                         'FÉMININ', 'FEMININ', 'FEMALE', 'F\n', '\nF\n', 'GENRE: F']

    for ind in indicateurs_homme:
        if ind in texte_upper:
            return 1

    for ind in indicateurs_femme:
        if ind in texte_upper:
            return 0

    # Recherche par contexte
    match = re.search(r'sexe\s*:?\s*([mMfF])', texte, re.IGNORECASE)
    if match:
        return 1 if match.group(1).upper() == 'M' else 0

    return -1  # Inconnu


# ─────────────────────────────────────────────────────────────────────────────
# Fonction principale de scan
# ─────────────────────────────────────────────────────────────────────────────

def scanner_piece_identite(source=None) -> dict:
    """
    Scanne une pièce d'identité et extrait les informations.

    Paramètre
    ---------
    source : None (webcam), int (index caméra), str (chemin image),
             bytes (image en base64), np.ndarray (image OpenCV)

    Retourne
    --------
    dict avec : nom, prenom, date_naissance, age, sexe, succes, message
    """

    # ── Charger l'image ──────────────────────────────────────────
    if source is None or isinstance(source, int):
        # Capture depuis webcam ou Raspberry Pi
        index_cam = source if isinstance(source, int) else 0
        cap = cv2.VideoCapture(index_cam)

        if not cap.isOpened():
            return _resultat_erreur("Impossible d'accéder à la caméra.")

        # Attendre que la caméra se stabilise
        for _ in range(5):
            cap.read()

        ret, image = cap.read()
        cap.release()

        if not ret:
            return _resultat_erreur("Échec de la capture d'image.")

    elif isinstance(source, str) and os.path.exists(source):
        # Charger depuis un fichier
        image = cv2.imread(source)
        if image is None:
            return _resultat_erreur(f"Impossible de lire l'image : {source}")

    elif isinstance(source, bytes):
        # Image base64 (depuis l'API Flask)
        try:
            nparr = np.frombuffer(base64.b64decode(source), np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception:
            return _resultat_erreur("Image base64 invalide.")

    elif isinstance(source, np.ndarray):
        image = source

    else:
        return _resultat_erreur("Source d'image non reconnue.")

    # ── OCR ou simulation ─────────────────────────────────────────
    if not TESSERACT_DISPONIBLE:
        return _resultat_simulation()

    try:
        # Prétraitement
        image_traitee = pretraiter_image(image)

        # OCR avec plusieurs configurations pour maximiser la détection
        configs = [
            '--oem 3 --psm 3 -l fra+ara+eng',  # Auto + français + arabe + anglais
            '--oem 3 --psm 6 -l fra+eng',       # Bloc de texte uniforme
            '--oem 1 --psm 3 -l fra',            # LSTM uniquement
        ]

        meilleur_texte = ""
        for config in configs:
            try:
                texte = pytesseract.image_to_string(image_traitee, config=config)
                if len(texte) > len(meilleur_texte):
                    meilleur_texte = texte
            except Exception:
                continue

        if not meilleur_texte.strip():
            return _resultat_erreur("Aucun texte détecté. Repositionnez la carte.")

        # Extraction des informations
        nom, prenom           = extraire_nom_prenom(meilleur_texte)
        date_naissance, age   = extraire_date_naissance(meilleur_texte)
        sexe                  = extraire_sexe(meilleur_texte)

        return {
            "succes":          True,
            "nom":             nom,
            "prenom":          prenom,
            "date_naissance":  date_naissance,
            "age":             age,
            "sexe":            sexe,  # 0=Femme, 1=Homme, -1=Inconnu
            "sexe_libelle":    "Homme" if sexe == 1 else ("Femme" if sexe == 0 else "Non détecté"),
            "texte_brut":      meilleur_texte[:200],
            "message":         "Scan réussi",
        }

    except Exception as e:
        return _resultat_erreur(f"Erreur OCR : {str(e)}")


def _resultat_erreur(message: str) -> dict:
    """Retourne un résultat d'erreur standardisé."""
    return {
        "succes":         False,
        "nom":            "Inconnu",
        "prenom":         "Inconnu",
        "date_naissance": "Inconnue",
        "age":            30,
        "sexe":           -1,
        "sexe_libelle":   "Non détecté",
        "texte_brut":     "",
        "message":        message,
    }


def _resultat_simulation() -> dict:
    """Retourne des données simulées quand Tesseract n'est pas disponible."""
    import random
    noms    = ["Alaoui", "Benali", "El Fassi", "Chraibi", "Tazi", "Mansouri"]
    prenoms = ["Mohamed", "Fatima", "Ahmed", "Khadija", "Youssef", "Meryem"]
    return {
        "succes":          True,
        "nom":             random.choice(noms),
        "prenom":          random.choice(prenoms),
        "date_naissance":  "15/03/1985",
        "age":             random.randint(20, 70),
        "sexe":            random.choice([0, 1]),
        "sexe_libelle":    random.choice(["Homme", "Femme"]),
        "texte_brut":      "[Simulation — Tesseract non installé]",
        "message":         "Mode simulation (Tesseract absent)",
    }


def capturer_et_scanner(index_cam: int = 0) -> dict:
    """
    Capture une image depuis la caméra et la scanne.
    Fonction principale à appeler depuis le Raspberry Pi.
    """
    return scanner_piece_identite(source=index_cam)


# ─────────────────────────────────────────────────────────────────────────────
# Test en ligne de commande
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Tester avec une image fournie
        chemin = sys.argv[1]
        print(f"[TEST] Scan de : {chemin}")
        resultat = scanner_piece_identite(source=chemin)
    else:
        # Tester avec la webcam
        print("[TEST] Capture depuis la caméra (index 0)...")
        resultat = scanner_piece_identite(source=0)

    print("\n=== RÉSULTAT DU SCAN ===")
    for cle, valeur in resultat.items():
        if cle != "texte_brut":
            print(f"  {cle:<20} : {valeur}")
