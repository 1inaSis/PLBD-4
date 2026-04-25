"""
nlp_extractor.py — Extracteur de symptômes NLP pour HealthGate
Projet HealthGate | Centrale Casablanca | PLBD 4 | 2025-2026

Ce module analyse une phrase libre saisie par le patient (en français)
et extrait des features binaires de symptômes utilisées par le modèle ML.

Approche : correspondance par mots-clés et expressions régulières en français.
Robuste aux phrases incomplètes, au dialecte marocain francisé et aux fautes.
"""

import re
import unicodedata
from typing import Dict, List


# ─────────────────────────────────────────────────────────────────────────────
# Dictionnaire de mots-clés par symptôme (français + variantes courantes)
# ─────────────────────────────────────────────────────────────────────────────
MOTS_CLES_SYMPTOMES: Dict[str, List[str]] = {

    "chest_pain": [
        "poitrine", "thorax", "thoracique", "sternum", "coeur", "cœur",
        "cardiaque", "angine", "infarctus", "serrement", "oppression",
        "douleur au coeur", "mal au coeur", "brûlure poitrine",
    ],

    "dyspnea": [
        "respir", "souffle", "essouffl", "haletant", "haleter",
        "difficultés à respirer", "du mal à respirer", "ne respire",
        "manque d'air", "manque air", "apnée", "étouffement", "étouffer",
        "asthme", "bronchite", "poumons",
    ],

    "loss_of_consciousness": [
        "inconscient", "évanoui", "évanouissement", "syncope", "perte de connaissance",
        "tombe", "tombé", "s'est effondré", "effondrement", "ne répond plus",
        "ne réagit plus", "coma", "assommé",
    ],

    "severe_bleeding": [
        "saign", "hémorrag", "sang qui coule", "beaucoup de sang",
        "perd du sang", "plaie profonde", "blessure profonde",
        "coupure profonde", "artère", "saignement abondant",
    ],

    "neurological_symptoms": [
        "paralys", "paralysie", "parésie", "engourdissement", "engourdi",
        "bouche tordue", "visage tordu", "ne parle plus", "n'arrive plus à parler",
        "difficultés à parler", "convulsion", "épilepsie", "tremblements",
        "vertiges sévères", "perte de vision", "vision double", "cécité",
        "cerveau", "neurologique",
    ],

    "abdominal_pain": [
        "ventre", "abdomen", "abdominal", "estomac", "intestin",
        "appendice", "nausée", "nausées", "vomit", "vomissement",
        "diarrhée", "bas-ventre", "bas ventre", "foie", "rate",
        "mal au ventre", "douleur ventre", "crampes ventre",
    ],

    "fever": [
        "fièvre", "fébrile", "température élevée", "chaud", "brûlant",
        "transpire", "transpiration", "frisson", "frissons",
        "38", "39", "40", "41",  # degrés dans le texte
        "sueur", "sueurs",
    ],

    "trauma": [
        "accident", "chute", "tombé", "tombe", "blessure", "blessé",
        "fracture", "cassé", "cassure", "os", "entorse", "luxation",
        "contusion", "ecchymose", "plaie", "coupure", "brûlure",
        "agression", "couteau", "coup", "heurté", "heurt",
        "voiture", "moto", "vélo", "renversé",
    ],

    "pain": [
        "douleur", "mal", "souffrance", "douloureux", "douloureuse",
        "ça fait mal", "j'ai mal", "fort mal", "très mal",
        "brûlure", "crampe", "élancement", "piquûre", "piqure",
    ],
}

# Expressions de criticité / urgence (indicateurs de gravité élevée)
EXPRESSIONS_URGENCE = [
    "ne respire plus", "ne répond plus", "ne réagit plus",
    "arrêt cardiaque", "crise cardiaque", "pas de pouls",
    "lèvres bleues", "inconscient", "convulse",
    "perd beaucoup de sang", "saignement abondant",
    "ne bouge plus", "paralysé", "effondré",
]


def normaliser_texte(texte: str) -> str:
    """
    Normalise le texte : minuscules, suppression accents, espaces multiples.
    Conserve les chiffres pour détecter les températures.
    """
    if not isinstance(texte, str) or not texte.strip():
        return ""

    # Minuscules
    texte = texte.lower().strip()

    # Supprimer les accents (pour les variantes mal écrites)
    texte_sans_accent = unicodedata.normalize("NFD", texte)
    texte_sans_accent = "".join(
        c for c in texte_sans_accent
        if unicodedata.category(c) != "Mn"
    )

    # On garde les deux versions pour la recherche
    return texte + " " + texte_sans_accent


def detecter_symptome(texte_norm: str, mots_cles: List[str]) -> int:
    """
    Retourne 1 si au moins un mot-clé est trouvé dans le texte, 0 sinon.
    Utilise une recherche partielle (startswith logique) pour les racines.
    """
    for mot in mots_cles:
        # On normalise aussi le mot-clé
        mot_norm = unicodedata.normalize("NFD", mot.lower())
        mot_norm = "".join(c for c in mot_norm if unicodedata.category(c) != "Mn")

        if mot_norm in texte_norm:
            return 1
    return 0


def estimer_score_douleur(texte: str) -> int:
    """
    Estime un score de douleur (0-10) à partir du texte libre.
    Se base sur les adverbes d'intensité et les chiffres.
    """
    texte_min = texte.lower()

    # Chercher un chiffre explicite de 1 à 10
    chiffres = re.findall(r'\b([1-9]|10)\b', texte_min)
    if chiffres:
        score = max(int(c) for c in chiffres)
        if score <= 10:
            return score

    # Estimation par intensité
    if any(mot in texte_min for mot in ["insupportable", "atroce", "mourir", "insoutenable"]):
        return 9
    if any(mot in texte_min for mot in ["très fort", "très mal", "intense", "sévère", "fort mal"]):
        return 7
    if any(mot in texte_min for mot in ["fort", "beaucoup", "bien mal", "vraiment mal"]):
        return 6
    if any(mot in texte_min for mot in ["modéré", "un peu", "léger", "légère"]):
        return 3
    if any(mot in texte_min for mot in ["douleur", "mal", "souffrance"]):
        return 5

    return 0


def detecter_urgence(texte: str) -> int:
    """
    Détecte si le texte contient des expressions d'urgence absolue.
    Retourne 1 si urgence critique détectée, 0 sinon.
    """
    texte_min = texte.lower()
    for expression in EXPRESSIONS_URGENCE:
        expr_norm = unicodedata.normalize("NFD", expression.lower())
        expr_norm = "".join(c for c in expr_norm if unicodedata.category(c) != "Mn")
        if expr_norm in texte_min:
            return 1
    return 0


def extraire_features_nlp(texte: str) -> Dict[str, int]:
    """
    Fonction principale : extrait toutes les features NLP depuis un texte libre.

    Paramètre
    ---------
    texte : str
        Phrase libre saisie ou dictée par le patient aux urgences.

    Retourne
    --------
    dict contenant les features binaires + score douleur NLP + flag urgence.
    """
    if not isinstance(texte, str) or not texte.strip():
        # Texte vide : toutes les features à 0
        return {
            "nlp_chest_pain":            0,
            "nlp_dyspnea":               0,
            "nlp_loss_of_consciousness": 0,
            "nlp_severe_bleeding":       0,
            "nlp_neurological":          0,
            "nlp_abdominal_pain":        0,
            "nlp_fever":                 0,
            "nlp_trauma":                0,
            "nlp_pain":                  0,
            "nlp_pain_score":            0,
            "nlp_urgence_critique":      0,
        }

    texte_norm = normaliser_texte(texte)

    features = {
        "nlp_chest_pain":            detecter_symptome(texte_norm, MOTS_CLES_SYMPTOMES["chest_pain"]),
        "nlp_dyspnea":               detecter_symptome(texte_norm, MOTS_CLES_SYMPTOMES["dyspnea"]),
        "nlp_loss_of_consciousness": detecter_symptome(texte_norm, MOTS_CLES_SYMPTOMES["loss_of_consciousness"]),
        "nlp_severe_bleeding":       detecter_symptome(texte_norm, MOTS_CLES_SYMPTOMES["severe_bleeding"]),
        "nlp_neurological":          detecter_symptome(texte_norm, MOTS_CLES_SYMPTOMES["neurological_symptoms"]),
        "nlp_abdominal_pain":        detecter_symptome(texte_norm, MOTS_CLES_SYMPTOMES["abdominal_pain"]),
        "nlp_fever":                 detecter_symptome(texte_norm, MOTS_CLES_SYMPTOMES["fever"]),
        "nlp_trauma":                detecter_symptome(texte_norm, MOTS_CLES_SYMPTOMES["trauma"]),
        "nlp_pain":                  detecter_symptome(texte_norm, MOTS_CLES_SYMPTOMES["pain"]),
        "nlp_pain_score":            estimer_score_douleur(texte),
        "nlp_urgence_critique":      detecter_urgence(texte),
    }

    return features


def enrichir_dataframe(df):
    """
    Ajoute les colonnes NLP à un DataFrame contenant une colonne 'symptom_text'.
    Si 'symptom_text' n'existe pas, crée des colonnes vides.
    """
    import pandas as pd

    if "symptom_text" not in df.columns:
        df["symptom_text"] = ""

    features_nlp = df["symptom_text"].apply(
        lambda texte: pd.Series(extraire_features_nlp(texte))
    )
    return pd.concat([df, features_nlp], axis=1)


# ─────────────────────────────────────────────────────────────────────────────
# Test rapide en ligne de commande
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    phrases_test = [
        "J'ai très mal à la poitrine depuis ce matin et j'ai du mal à respirer",
        "Il est inconscient, ne répond plus du tout",
        "Fièvre à 40 depuis 2 jours, mon enfant ne mange plus",
        "Petite coupure au doigt, saignement léger",
        "Je veux juste renouveler mon ordonnance",
        "Mal de ventre modéré depuis hier soir avec des nausées",
        "j ai tro mal au ventr et je vomi",   # fautes de frappe
        "",                                    # texte vide
    ]

    print("=" * 70)
    print("TEST DU MODULE NLP — HealthGate")
    print("=" * 70)

    for phrase in phrases_test:
        print(f"\n[TEXTE]   « {phrase} »")
        features = extraire_features_nlp(phrase)
        actifs = {k: v for k, v in features.items() if v > 0}
        if actifs:
            print(f"[FEATURES] {actifs}")
        else:
            print("[FEATURES] Aucun symptôme détecté")
