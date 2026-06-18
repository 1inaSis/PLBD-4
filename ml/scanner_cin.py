"""
scanner_cin.py — Scanner CIN universel pour HealthGate
Stratégie : rpicam-still → Groq Vision (llama-3.2-90b-vision-preview) → JSON
Supporte : Maroc, Côte d'Ivoire, Sénégal, Mali, et toutes cartes africaines
Si Groq échoue ou image illisible → formulaire_manuel: True
"""

import os
import re
import json
import base64
import subprocess
from pathlib import Path
from datetime import datetime
from dotenv import dotenv_values

TIMEOUT_CAPTURE = 4
_IMG_TMP        = '/tmp/cin.jpg'
_MODELE_GROQ    = 'llama-3.2-90b-vision-preview'

# Racine du projet = deux niveaux au-dessus de ce fichier (ml/scanner_cin.py)
_RACINE = Path(__file__).resolve().parent.parent


def _charger_api_key() -> str:
    """Cherche GROQ_API_KEY dans : env système → backend/.env → .env racine."""
    cle = os.environ.get('GROQ_API_KEY', '').strip()
    if cle:
        return cle

    for chemin in [_RACINE / 'backend' / '.env', _RACINE / '.env']:
        if chemin.exists():
            valeur = dotenv_values(chemin).get('GROQ_API_KEY', '').strip()
            if valeur:
                print(f"[SCANNER] GROQ_API_KEY chargée depuis {chemin}")
                return valeur

    return ''

_PROMPT = (
    "Tu es un expert en lecture de cartes d'identité africaines (Côte d'Ivoire, Maroc, etc.).\n"
    "Analyse cette image de carte et extrais ces informations.\n"
    "Réponds UNIQUEMENT avec ce JSON, rien d'autre :\n"
    '{"nom": "NOM EN MAJUSCULES", "prenom": "Prénom(s)", '
    '"date_naissance": "DD/MM/YYYY", "sexe": "M ou F"}\n\n'
    "Règles :\n"
    "- date_naissance doit être antérieure à 2015\n"
    "- Corrige les erreurs de lecture évidentes\n"
    "- Si information absente → null"
)


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


# ─── Groq Vision ─────────────────────────────────────────────────────────────

def _encoder_image(chemin: str) -> str:
    with open(chemin, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def _analyser_avec_groq(image_path: str) -> dict | None:
    api_key = _charger_api_key()
    if not api_key:
        print("[SCANNER] GROQ_API_KEY absente (env, backend/.env, .env racine)")
        return None

    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        b64 = _encoder_image(image_path)

        reponse = client.chat.completions.create(
            model=_MODELE_GROQ,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    },
                    {"type": "text", "text": _PROMPT},
                ],
            }],
            max_tokens=256,
            temperature=0,
        )

        contenu = reponse.choices[0].message.content.strip()
        print(f"[SCANNER] Groq réponse brute : {contenu}")
        return _parser_reponse(contenu)

    except Exception as e:
        print(f"[SCANNER] Erreur Groq : {e}")
        return None


def _parser_reponse(contenu: str) -> dict | None:
    # Extrait le bloc JSON même si Groq ajoute du texte autour
    m = re.search(r'\{[^{}]+\}', contenu, re.DOTALL)
    if not m:
        print("[SCANNER] Aucun JSON trouvé dans la réponse")
        return None

    try:
        data = json.loads(m.group())
    except json.JSONDecodeError as e:
        print(f"[SCANNER] JSON invalide : {e}")
        return None

    nom    = (data.get('nom')    or '').strip().upper()
    prenom = (data.get('prenom') or '').strip().title()
    date   = (data.get('date_naissance') or '').strip()
    sexe   = (data.get('sexe')   or '').strip().upper()

    # Valide format date DD/MM/YYYY
    if date and not re.match(r'^\d{2}/\d{2}/\d{4}$', date):
        date = ''

    age = _calculer_age(date)

    sexe_code = 1 if sexe == 'M' else (0 if sexe == 'F' else -1)
    sexe_lib  = 'Homme' if sexe_code == 1 else ('Femme' if sexe_code == 0 else 'Non détecté')

    print(f"[SCANNER] Extrait → nom={repr(nom)} prenom={repr(prenom)} date={repr(date)} sexe={sexe_lib}")
    return {
        "nom": nom, "prenom": prenom, "date_naissance": date,
        "age": age, "sexe": sexe_code, "sexe_libelle": sexe_lib,
    }


def _calculer_age(date_str: str) -> int | None:
    try:
        j, mo, a = (int(x) for x in date_str.split('/'))
        today = datetime.now()
        age = today.year - a - ((today.month, today.day) < (mo, j))
        return age if 0 < age < 120 else None
    except Exception:
        return None


# ─── Fonction principale ──────────────────────────────────────────────────────

def scanner_piece_identite(source=None) -> dict:
    """
    Scan CIN via Groq Vision. Pipeline : capture → base64 → Groq → JSON.
    Retourne formulaire_manuel=True si Groq échoue ou image illisible.

    source : None → rpicam-still | str (chemin fichier) | bytes (JPEG brut)
    """
    image_path = None
    fichier_temporaire = False

    try:
        if isinstance(source, str) and os.path.exists(source):
            image_path = source

        elif isinstance(source, (bytes, bytearray)):
            with open(_IMG_TMP, 'wb') as f:
                f.write(source)
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

        info = _analyser_avec_groq(image_path)

        if info and info["nom"] and info["prenom"] and info["date_naissance"]:
            return {
                "succes":            True,
                "formulaire_manuel": False,
                "nom":               info["nom"],
                "prenom":            info["prenom"],
                "date_naissance":    info["date_naissance"],
                "age":               info["age"] or 30,
                "nationalite":       "",
                "sexe":              info["sexe"],
                "sexe_libelle":      info["sexe_libelle"],
                "texte_brut":        "",
                "message":           "Scan réussi (Groq Vision)",
            }

        return _besoin_formulaire("Groq Vision : extraction incomplète", partial=info)

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
        "nationalite":       "",
        "sexe":              partial.get("sexe", -1),
        "sexe_libelle":      partial.get("sexe_libelle", "Non détecté"),
        "texte_brut":        "",
        "message":           message,
    }


if __name__ == "__main__":
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else None
    r   = scanner_piece_identite(source=src)
    for k, v in r.items():
        print(f"  {k:<20} : {v}")
