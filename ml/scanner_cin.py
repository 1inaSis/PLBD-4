"""
scanner_cin.py — Scanner CIN universel pour HealthGate
Stratégie : rpicam-still → doctr (python-doctr) → extraction multi-passes
Supporte : Maroc, Côte d'Ivoire, Sénégal, Mali, et toutes cartes africaines
Si incomplet → formulaire_manuel: True avec champs partiellement pré-remplis

Note perf : premier import prend ~20s (chargement modèles doctr),
            les scans suivants sont rapides (~2-4s).
"""

import re
import os
import base64
import subprocess
import numpy as np
from datetime import datetime

os.environ.setdefault('DOCTR_CACHE_DIR', '/home/touaregs/.cache/doctr')

try:
    import cv2
    CV2_DISPONIBLE = True
except ImportError:
    CV2_DISPONIBLE = False

# ─── Init doctr unique au chargement du module ───────────────────────────────

try:
    from doctr.io import DocumentFile
    from doctr.models import ocr_predictor
    print("[SCANNER] Chargement modèles doctr (première fois ~20s)...")
    _model = ocr_predictor(
        det_arch='db_mobilenet_v3_large',
        reco_arch='crnn_mobilenet_v3_small',
        pretrained=True,
    )
    DOCTR_DISPONIBLE = True
    print("[SCANNER] doctr prêt.")
except Exception as _e:
    _model = None
    DOCTR_DISPONIBLE = False
    print(f"[SCANNER] doctr non disponible : {_e}")

TIMEOUT_CAPTURE = 4
_IMG_TMP        = '/tmp/cin.jpg'


# ─── OCR via doctr ───────────────────────────────────────────────────────────

def _ocr(image_path: str) -> str:
    """Lance doctr sur le fichier image et reconstruit le texte ligne par ligne."""
    try:
        doc = DocumentFile.from_images(image_path)
        result = _model(doc)
        lignes = []
        for block in result.pages[0].blocks:
            for line in block.lines:
                ligne_texte = ' '.join(w.value for w in line.words)
                if ligne_texte.strip():
                    lignes.append(ligne_texte.strip())
        return '\n'.join(lignes)
    except Exception as e:
        print(f"[SCANNER] Erreur doctr : {e}")
        return ""


# ─── Extraction multi-passes — toutes cartes africaines ──────────────────────

_PARASITES_NOM = {
    'carte', 'assure', 'assuré', 'etudiant', 'étudiant', 'scolaire',
    'identite', 'identité', 'attestation', 'numerode', 'numero',
    'securite', 'sécurité', 'sociale', 'couverture', 'maladie',
    'universelle', 'republique', 'république', 'republic',
    'national', 'nationale',
}

_PARASITES_PRENOM = {
    'née', 'né', 'nee', 'ne', 'date', 'naiss', 'naissance',
    'lieu', 'classe', 'ecole', 'école', 'formation',
}

_LABELS_IGNORER = {
    'NOM', 'NAME', 'SURNAME', 'PRENOM', 'PRÉNOM', 'PRENOMS', 'PRÉNOMS',
    'GIVEN', 'FIRST', 'FORENAME', 'DATE', 'BIRTH', 'BORN', 'DOB',
    'NAISSANCE', 'SEXE', 'SEX', 'NATIONALITY', 'NATIONALITE', 'NATIONALITÉ',
    'PLACE', 'LIEU', 'EXPIRY', 'EXPIRES', 'VALID', 'ISSUED',
}

# PASSE 1 — regex labels stricts
_RE_P1_NOM = re.compile(
    r'(?m)^\s*(?:Nom|NAME|SURNAME|NOM\s+DE\s+FAMILLE)\s*[:/]?\s*(.+)',
    re.IGNORECASE
)
_RE_P1_PRENOM = re.compile(
    r'(?m)^\s*(?:Pr[eé]noms?\s*(?:\([sS]\))?\s*|FIRST\s*NAME\b|FORENAME\b)\s*[:/]?\s*(.+)',
    re.IGNORECASE
)
_RE_P1_DATE = re.compile(
    r'(?:N[eé]e?\s*(?:\([eE]\))?\s*(?:le\b)?|DATE\s*(?:DE\s*)?NAISS(?:ANCE)?)'
    r'\s*[:/]?\s*(\d{2}[/\-\.]\d{2}[/\-\.](?:\d{2}|\d{4}))',
    re.IGNORECASE
)
# Cas spécial : "Prénom/Nom" ou "Nom/Prénom" sur une seule ligne combinée
_RE_P1_PRENOMNOM = re.compile(
    r'(?m)^\s*(?:Pr[eé]noms?\s*/\s*Nom|Nom\s*/\s*Pr[eé]nom)\s*[:/]?\s*(.+)',
    re.IGNORECASE
)

# Dates génériques
_RE_DATE_DMY4 = re.compile(r'\b(\d{2})[/\-\.](\d{2})[/\-\.](\d{4})\b')
_RE_DATE_YMD  = re.compile(r'\b(\d{4})[/\-\.](\d{2})[/\-\.](\d{2})\b')
_RE_DATE_DMY2 = re.compile(r'\b(\d{2})[/\-\.](\d{2})[/\-\.](\d{2})\b')

_RE_LIGNE_LABEL = re.compile(
    r'^\s*(?:nom|name|surname|pr[eé]noms?|given|first|forename|'
    r'date|n[eé]e?|naissance|sexe|sex|nationality|nationalit[eé]|'
    r'lieu|born|expiry|valid|issued|num[eé]ro)\s*[:/]',
    re.IGNORECASE
)


def _nettoyer(val: str) -> str:
    return re.sub(r'[^a-zA-ZÀ-ÿ\s\-\']', '', val).strip()


def _est_label(ligne: str) -> bool:
    return bool(_RE_LIGNE_LABEL.match(ligne))


def _normaliser(val: str) -> str:
    mapping = str.maketrans(
        'àáâãäåèéêëìíîïòóôõöùúûüýÿñç',
        'aaaaaaeeeeiiiioooooouuuuyyNC'
    )
    return val.lower().translate(mapping)


def _filtrer_parasites(val: str, parasites: set) -> str:
    mots = val.split()
    return ' '.join(m for m in mots if _normaliser(m) not in parasites)


def _convertir_annee(j: int, mo: int, a: int) -> tuple:
    """Année 2 chiffres → 4 chiffres (ex: 04 → 2004, 85 → 1985)."""
    if a < 100:
        seuil = datetime.now().year % 100
        a = 2000 + a if a <= seuil else 1900 + a
    return j, mo, a


def _valider_date(j: int, mo: int, a: int):
    j, mo, a = _convertir_annee(j, mo, a)
    if 1900 <= a <= datetime.now().year and 1 <= mo <= 12 and 1 <= j <= 31:
        today = datetime.now()
        age = today.year - a - ((today.month, today.day) < (mo, j))
        if 0 < age < 120:
            return f"{j:02d}/{mo:02d}/{a}", age
    return None, None


def _chercher_date(texte: str):
    """Cherche une date valide dans le texte (avec ou sans label)."""
    # Avec label naissance
    m = _RE_P1_DATE.search(texte)
    if m:
        raw = m.group(1)
        dm = _RE_DATE_DMY4.match(raw) or _RE_DATE_DMY2.match(raw)
        if dm:
            date, age = _valider_date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
            if date:
                return date, age

    # DD/MM/YYYY
    for m in _RE_DATE_DMY4.finditer(texte):
        date, age = _valider_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if date:
            return date, age

    # YYYY/MM/DD
    for m in _RE_DATE_YMD.finditer(texte):
        date, age = _valider_date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if date:
            return date, age

    # DD/MM/YY (2 chiffres → conversion automatique)
    for m in _RE_DATE_DMY2.finditer(texte):
        date, age = _valider_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if date:
            return date, age

    return "", None


# ─── PASSE 1 : labels stricts ────────────────────────────────────────────────

def _passe1(texte: str) -> dict:
    nom = prenom = ""

    # Cas spécial "Prénom/Nom" : split sur espace → dernier mot = NOM, reste = PRÉNOM
    m = _RE_P1_PRENOMNOM.search(texte)
    if m:
        valeur = _nettoyer(m.group(1)).strip()
        mots = valeur.split()
        if len(mots) >= 2:
            nom    = mots[-1].title()
            prenom = ' '.join(mots[:-1]).title()
            print(f"[P1] CAS Prénom/Nom combiné → NOM={repr(nom)} PRÉNOM={repr(prenom)}")

    # NOM par label strict
    if not nom:
        m = _RE_P1_NOM.search(texte)
        if m:
            val = _nettoyer(m.group(1)).strip()
            if len(val) >= 2:
                nom = val.title()
                print(f"[P1] NOM label → {repr(nom)}")

    # PRÉNOM par label strict
    if not prenom:
        m = _RE_P1_PRENOM.search(texte)
        if m:
            val = _nettoyer(m.group(1)).strip()
            if len(val) >= 2:
                prenom = val.title()
                print(f"[P1] PRÉNOM label → {repr(prenom)}")

    date, age = _chercher_date(texte)
    if date:
        print(f"[P1] DATE → {repr(date)}")

    return {"nom": nom, "prenom": prenom, "date": date, "age": age}


# ─── PASSE 2 : positionnelle (ancre = date) ──────────────────────────────────

def _passe2(texte: str, date_connue: str) -> dict:
    nom = prenom = ""
    lignes = texte.split('\n')

    # Localiser la ligne de la date (ancre temporelle)
    idx_date = -1
    for i, l in enumerate(lignes):
        if date_connue and date_connue[:5] in l:
            idx_date = i
            break
        if _RE_DATE_DMY4.search(l) or _RE_DATE_DMY2.search(l) or _RE_DATE_YMD.search(l):
            idx_date = i
            break

    print(f"[P2] Ancre date ligne {idx_date}")

    # Lignes avant la date (1-3 lignes) = candidats nom/prénom
    candidats = []
    if idx_date > 0:
        for i in range(max(0, idx_date - 3), idx_date):
            l = lignes[i].strip()
            if not l or _est_label(l):
                continue
            candidats.append((i, l))

    # Ligne tout-majuscules 2+ mots → NOM
    for i, l in candidats:
        mots = l.split()
        if len(mots) < 2:
            continue
        chars = [c for c in l if c.isalpha()]
        if not chars or not all(c.isupper() for c in chars):
            continue
        if any(m.upper() in _LABELS_IGNORER for m in mots):
            continue
        val = _nettoyer(l)
        if len(val) >= 4:
            nom = val.title()
            print(f"[P2] NOM majuscules (ligne {i}) → {repr(nom)}")
            break

    # Ligne mixte parmi les candidats → PRÉNOM
    for i, l in candidats:
        if nom and _nettoyer(l).lower() == nom.lower():
            continue
        chars = [c for c in l if c.isalpha()]
        if chars and not all(c.isupper() for c in chars):
            val = _nettoyer(l)
            if len(val) >= 2:
                prenom = val.title()
                print(f"[P2] PRÉNOM mixte (ligne {i}) → {repr(prenom)}")
                break

    # Dernier recours : 2 premières lignes non-label non-date
    if not nom and not prenom:
        non_label = []
        for l in lignes:
            l = l.strip()
            if not l or _est_label(l):
                continue
            if _RE_DATE_DMY4.search(l) or _RE_DATE_DMY2.search(l) or _RE_DATE_YMD.search(l):
                continue
            non_label.append(l)
            if len(non_label) >= 2:
                break
        if len(non_label) >= 1:
            val = _nettoyer(non_label[0])
            if len(val) >= 2:
                nom = val.title()
                print(f"[P2] NOM fallback (1re ligne) → {repr(nom)}")
        if len(non_label) >= 2:
            val = _nettoyer(non_label[1])
            if len(val) >= 2:
                prenom = val.title()
                print(f"[P2] PRÉNOM fallback (2e ligne) → {repr(prenom)}")

    return {"nom": nom, "prenom": prenom}


# ─── PASSE 3 : fallback intelligent ──────────────────────────────────────────

def _passe3(texte: str, nom: str, prenom: str, date: str, age) -> dict:
    lignes = texte.split('\n')

    # Nom trouvé mais prénom vide → ligne suivante non-label
    if nom and not prenom:
        nom_low = nom.lower()
        for i, l in enumerate(lignes):
            if nom_low in l.lower():
                for j in range(i + 1, min(i + 4, len(lignes))):
                    cand = lignes[j].strip()
                    if not cand or _est_label(cand):
                        continue
                    if _RE_DATE_DMY4.search(cand) or _RE_DATE_DMY2.search(cand):
                        continue
                    val = _nettoyer(cand)
                    if len(val) >= 2 and val.upper() not in _LABELS_IGNORER:
                        prenom = val.title()
                        print(f"[P3] PRÉNOM après nom → {repr(prenom)}")
                        break
                if prenom:
                    break

    # Prénom trouvé mais nom vide → ligne précédente non-label
    if prenom and not nom:
        prenom_low = prenom.lower()
        for i, l in enumerate(lignes):
            if prenom_low in l.lower():
                for j in range(i - 1, max(-1, i - 4), -1):
                    cand = lignes[j].strip()
                    if not cand or _est_label(cand):
                        continue
                    val = _nettoyer(cand)
                    if len(val) >= 2 and val.upper() not in _LABELS_IGNORER:
                        nom = val.title()
                        print(f"[P3] NOM avant prénom → {repr(nom)}")
                        break
                if nom:
                    break

    if not date:
        date, age = _chercher_date(texte)
        if date:
            print(f"[P3] DATE trouvée → {repr(date)}")

    return {"nom": nom, "prenom": prenom, "date": date, "age": age}


# ─── Nettoyage final ─────────────────────────────────────────────────────────

def _nettoyage_final(nom: str, prenom: str) -> tuple:
    if nom:
        nom = _filtrer_parasites(nom, _PARASITES_NOM)
        nom = re.sub(r'\s{2,}', ' ', nom).strip()
        if len(nom) < 2:
            nom = ""
    if prenom:
        prenom = _filtrer_parasites(prenom, _PARASITES_PRENOM)
        prenom = re.sub(r'\s{2,}', ' ', prenom).strip()
        if len(prenom) < 2:
            prenom = ""
    return nom, prenom


# ─── Champs complémentaires ──────────────────────────────────────────────────

def _extraire_sexe(texte: str) -> tuple:
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
    m = re.search(
        r'(?:NATIONALIT[EÉ]|NATIONALITY)\s*[:/]?\s*([A-Za-zÀ-ÿ]+)',
        texte, re.IGNORECASE
    )
    return m.group(1).title() if m else ""


# ─── Orchestrateur principal ──────────────────────────────────────────────────

def _extraire_tout(texte: str) -> dict:
    print(f"\n{'='*60}")
    print(f"[SCANNER] OCR brut ({len(texte)} chars) :")
    print(texte)
    print('='*60)

    # PASSE 1 — labels stricts
    print("\n--- PASSE 1 : labels stricts ---")
    r1 = _passe1(texte)
    nom, prenom, date, age = r1["nom"], r1["prenom"], r1["date"], r1["age"]
    print(f"[P1] Bilan → nom={repr(nom)} prenom={repr(prenom)} date={repr(date)}")

    # PASSE 2 — positionnelle si champs manquants
    if not nom or not prenom:
        print("\n--- PASSE 2 : positionnelle ---")
        r2 = _passe2(texte, date)
        if not nom:
            nom = r2["nom"]
        if not prenom:
            prenom = r2["prenom"]
        print(f"[P2] Bilan → nom={repr(nom)} prenom={repr(prenom)}")

    # PASSE 3 — fallback intelligent si encore incomplet
    if not nom or not prenom or not date:
        print("\n--- PASSE 3 : fallback intelligent ---")
        r3 = _passe3(texte, nom, prenom, date, age)
        nom, prenom = r3["nom"], r3["prenom"]
        if not date:
            date, age = r3["date"], r3["age"]
        print(f"[P3] Bilan → nom={repr(nom)} prenom={repr(prenom)} date={repr(date)}")

    # Nettoyage final
    nom, prenom = _nettoyage_final(nom, prenom)

    sexe_code, sexe_lib = _extraire_sexe(texte)
    nationalite = _extraire_nationalite(texte)

    print(f"\n[FINAL] nom={repr(nom)} prenom={repr(prenom)} date={repr(date)} age={age} sexe={sexe_lib}")
    return {
        "nom": nom, "prenom": prenom, "date_naissance": date,
        "age": age, "sexe": sexe_code, "sexe_libelle": sexe_lib,
        "nationalite": nationalite,
    }


# ─── Capture rpicam-still ────────────────────────────────────────────────────

def _capturer(chemin: str) -> bool:
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
    Scan CIN via doctr. Pipeline : capture → doctr → extraction multi-passes.
    Retourne formulaire_manuel=True avec champs partiels si extraction incomplète.

    source : None → rpicam-still | str (chemin fichier) | bytes (base64) | ndarray
    """
    if not DOCTR_DISPONIBLE:
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
            ok = _capturer(_IMG_TMP)
            if not ok:
                return _besoin_formulaire("Capture échouée")
            image_path = _IMG_TMP
            fichier_temporaire = True

        if image_path is None:
            return _besoin_formulaire("Source image invalide")

        texte = _ocr(image_path)

        if not texte.strip():
            print("[SCANNER] doctr n'a produit aucun texte")
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
        "message":           "Mode simulation (doctr non disponible)",
    }


if __name__ == "__main__":
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else None
    r   = scanner_piece_identite(source=src)
    for k, v in r.items():
        print(f"  {k:<20} : {v}")
