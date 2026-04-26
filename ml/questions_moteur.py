"""
questions_moteur.py — Générateur de questions ciblées HealthGate
Projet HealthGate | Centrale Casablanca | PLBD 4 | 2025-2026

Ce module sélectionne 3 à 5 questions simples à poser au patient à partir :
- des constantes vitales
- du texte libre des symptômes
- de l'âge
- du sexe

Les réponses sont ensuite encodées en features numériques réutilisables par le modèle.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import re
import sqlite3
import unicodedata
from typing import Dict, List, Tuple

from nlp_extractor import extraire_features_nlp, normaliser_texte


MIN_QUESTIONS = 4
MAX_QUESTIONS = 6
BASE_DIR = Path(__file__).resolve().parent
UNIFIED_DB_PATH = BASE_DIR / "data" / "healthgate_unified.db"
QUESTION_USAGE_PATH = BASE_DIR / "data" / "question_usage_state.json"
_EXTERNAL_QUESTION_BANK: List[dict] | None = None
_QUESTION_USAGE_CACHE: dict | None = None
MAX_USAGE_HISTORY = 150


# ─────────────────────────────────────────────────────────────────────────────
# Features numériques attendues côté modèle
# ─────────────────────────────────────────────────────────────────────────────

FEATURES_QUESTIONS = [
    "q_douleur_irradiee_bras",
    "q_antecedent_infarctus",
    "q_medicaments_coeur",
    "q_douleur_repos_effort",
    "q_duree_dyspnee",
    "q_dyspnee_aggrave_effort",
    "q_antecedent_asthme",
    "q_duree_fievre",
    "q_frissons_sueurs",
    "q_voyage_paludisme",
    "q_hypertension_connue",
    "q_medicaments_tension",
    "q_maux_tete_vision",
    "q_a_mange_aujourdhui",
    "q_insuline_pris",
    "q_localisation_abdomen",
    "q_fievre_associee_abdomen",
    "q_vomissements_abdomen",
    "q_trauma_perte_conscience",
    "q_trauma_saignement",
    "q_trauma_zone",
    "q_neuro_faiblesse",
    "q_neuro_parole",
    "q_neuro_confusion",
    "q_pediatrie_hydratation",
    "q_grossesse_possible",
    "q_antecedent_symptome",
    "q_aggravation_effort",
    "q_prise_medicament",
    "q_duree_symptomes",
]


def _question(
    question_id: str,
    texte: str,
    feature_name: str,
    type_question: str = "oui_non",
    choix: List[str] | None = None,
    placeholder: str | None = None,
) -> dict:
    return {
        "id": question_id,
        "texte": texte,
        "type": type_question,
        "feature_name": feature_name,
        **({"choix": choix} if choix else {}),
        **({"placeholder": placeholder} if placeholder else {}),
    }


QUESTION_BANK: Dict[str, Dict] = {
    "douleur_thoracique": {
        "poids": 100,
        "condition": lambda c, nlp, age, sex, texte: (
            nlp.get("nlp_chest_pain", 0) == 1 or c.get("heart_rate", 0) > 120
        ),
        "questions": [
            _question(
                "q_douleur_irradiee_bras",
                "La douleur irradie-t-elle dans le bras gauche ou la mâchoire ?",
                "q_douleur_irradiee_bras",
            ),
            _question(
                "q_antecedent_infarctus",
                "Avez-vous déjà eu un infarctus ou un problème cardiaque grave ?",
                "q_antecedent_infarctus",
            ),
            _question(
                "q_medicaments_coeur",
                "Prenez-vous des médicaments pour le cœur ?",
                "q_medicaments_coeur",
            ),
            _question(
                "q_douleur_repos_effort",
                "La douleur est-elle apparue au repos ou à l'effort ?",
                "q_douleur_repos_effort",
                "choix",
                ["Au repos", "A l'effort", "Les deux", "Je ne sais pas"],
            ),
        ],
    },
    "dyspnee": {
        "poids": 95,
        "condition": lambda c, nlp, age, sex, texte: (
            nlp.get("nlp_dyspnea", 0) == 1 or c.get("spo2", 98) < 93
        ),
        "questions": [
            _question(
                "q_duree_dyspnee",
                "Décrivez depuis quand la gêne respiratoire a commencé.",
                "q_duree_dyspnee",
                "texte_libre",
                placeholder="Exemple: depuis 2 heures, depuis hier, depuis 4 jours",
            ),
            _question(
                "q_dyspnee_aggrave_effort",
                "Est-ce que cela empire quand vous bougez ?",
                "q_dyspnee_aggrave_effort",
            ),
            _question(
                "q_antecedent_asthme",
                "Avez-vous de l'asthme ou une maladie des poumons ?",
                "q_antecedent_asthme",
            ),
        ],
    },
    "fievre": {
        "poids": 90,
        "condition": lambda c, nlp, age, sex, texte: (
            nlp.get("nlp_fever", 0) == 1 or c.get("temperature", 37) >= 39.0
        ),
        "questions": [
            _question(
                "q_duree_fievre",
                "Depuis quand la fièvre est-elle présente ?",
                "q_duree_fievre",
                "texte_libre",
                placeholder="Exemple: depuis ce matin, depuis 2 jours",
            ),
            _question(
                "q_frissons_sueurs",
                "Avez-vous des frissons ou des sueurs la nuit ?",
                "q_frissons_sueurs",
            ),
            _question(
                "q_voyage_paludisme",
                "Avez-vous voyagé dans une zone de paludisme récemment ?",
                "q_voyage_paludisme",
            ),
        ],
    },
    "hypertension": {
        "poids": 80,
        "condition": lambda c, nlp, age, sex, texte: (
            c.get("bp_systolic", 120) >= 160
            or c.get("bp_diastolic", 80) >= 100
            or (
                age >= 65
                and (
                    nlp.get("nlp_pain", 0) == 1
                    or nlp.get("nlp_dyspnea", 0) == 1
                    or nlp.get("nlp_neurological", 0) == 1
                )
            )
        ),
        "questions": [
            _question(
                "q_hypertension_connue",
                "Avez-vous une hypertension connue ?",
                "q_hypertension_connue",
            ),
            _question(
                "q_medicaments_tension",
                "Prenez-vous des médicaments pour la tension ?",
                "q_medicaments_tension",
            ),
            _question(
                "q_maux_tete_vision",
                "Avez-vous des maux de tête ou des troubles de la vision ?",
                "q_maux_tete_vision",
            ),
        ],
    },
    "glycemie": {
        "poids": 75,
        "condition": lambda c, nlp, age, sex, texte: (
            c.get("glucose", 90) < 70 or "diabet" in normaliser_texte(texte) or "insuline" in normaliser_texte(texte)
        ),
        "questions": [
            _question(
                "q_a_mange_aujourdhui",
                "Avez-vous mangé aujourd'hui ?",
                "q_a_mange_aujourdhui",
            ),
            _question(
                "q_insuline_pris",
                "Avez-vous pris votre insuline ou votre traitement du diabète ?",
                "q_insuline_pris",
            ),
        ],
    },
    "abdomen": {
        "poids": 85,
        "condition": lambda c, nlp, age, sex, texte: (
            nlp.get("nlp_abdominal_pain", 0) == 1 or "ventre" in normaliser_texte(texte)
        ),
        "questions": [
            _question(
                "q_localisation_abdomen",
                "Où se situe surtout la douleur abdominale ?",
                "q_localisation_abdomen",
                "texte_libre",
                placeholder="Exemple: en bas à droite, au centre, partout",
            ),
            _question(
                "q_fievre_associee_abdomen",
                "Avez-vous de la fièvre en plus ?",
                "q_fievre_associee_abdomen",
            ),
            _question(
                "q_vomissements_abdomen",
                "Avez-vous vomi ou eu des nausées ?",
                "q_vomissements_abdomen",
            ),
        ],
    },
    "trauma": {
        "poids": 92,
        "condition": lambda c, nlp, age, sex, texte: nlp.get("nlp_trauma", 0) == 1,
        "questions": [
            _question(
                "q_trauma_perte_conscience",
                "Avez-vous perdu connaissance lors du choc ?",
                "q_trauma_perte_conscience",
            ),
            _question(
                "q_trauma_saignement",
                "Y a-t-il un saignement abondant ?",
                "q_trauma_saignement",
            ),
            _question(
                "q_trauma_zone",
                "Où avez-vous le plus mal ?",
                "q_trauma_zone",
                "choix",
                ["Tête", "Poitrine", "Ventre", "Bras ou jambe"],
            ),
        ],
    },
    "neuro": {
        "poids": 93,
        "condition": lambda c, nlp, age, sex, texte: nlp.get("nlp_neurological", 0) == 1,
        "questions": [
            _question(
                "q_neuro_faiblesse",
                "Avez-vous une faiblesse ou une paralysie d'un côté ?",
                "q_neuro_faiblesse",
            ),
            _question(
                "q_neuro_parole",
                "Avez-vous du mal à parler ou à trouver vos mots ?",
                "q_neuro_parole",
            ),
            _question(
                "q_neuro_confusion",
                "Êtes-vous confus ou désorienté ?",
                "q_neuro_confusion",
            ),
        ],
    },
    "pediatrie": {
        "poids": 70,
        "condition": lambda c, nlp, age, sex, texte: age < 5 and (
            nlp.get("nlp_fever", 0) == 1 or nlp.get("nlp_dyspnea", 0) == 1 or nlp.get("nlp_abdominal_pain", 0) == 1
        ),
        "questions": [
            _question(
                "q_pediatrie_hydratation",
                "L'enfant boit-il et urine-t-il normalement ?",
                "q_pediatrie_hydratation",
            ),
            _question(
                "q_antecedent_symptome",
                "A-t-il déjà eu ce problème auparavant ?",
                "q_antecedent_symptome",
            ),
            _question(
                "q_duree_symptomes",
                "Expliquez depuis quand les symptômes ont commencé.",
                "q_duree_symptomes",
                "texte_libre",
                placeholder="Exemple: depuis hier soir, depuis 3 jours",
            ),
        ],
    },
    "grossesse": {
        "poids": 78,
        "condition": lambda c, nlp, age, sex, texte: (
            sex == 0 and 12 <= age <= 55 and (
                nlp.get("nlp_abdominal_pain", 0) == 1 or nlp.get("nlp_fever", 0) == 1 or "saign" in normaliser_texte(texte)
            )
        ),
        "questions": [
            _question(
                "q_grossesse_possible",
                "Êtes-vous enceinte ou pourriez-vous l'être ?",
                "q_grossesse_possible",
            ),
            _question(
                "q_fievre_associee_abdomen",
                "Avez-vous de la fièvre en plus ?",
                "q_fievre_associee_abdomen",
            ),
            _question(
                "q_vomissements_abdomen",
                "Avez-vous vomi ou eu des nausées ?",
                "q_vomissements_abdomen",
            ),
        ],
    },
}


FALLBACK_QUESTIONS = [
    _question(
        "q_duree_symptomes",
        "Depuis quand vos symptômes ont-ils commencé ?",
        "q_duree_symptomes",
        "texte_libre",
        placeholder="Exemple: depuis ce matin, depuis 2 jours",
    ),
    _question(
        "q_antecedent_symptome",
        "Avez-vous déjà eu ce problème auparavant ?",
        "q_antecedent_symptome",
    ),
    _question(
        "q_aggravation_effort",
        "Est-ce que votre état s'aggrave quand vous bougez ?",
        "q_aggravation_effort",
    ),
    _question(
        "q_prise_medicament",
        "Avez-vous pris un médicament avant de venir ?",
        "q_prise_medicament",
    ),
]


def _normaliser_bool(valeur) -> int:
    if valeur is None:
        return 0
    if isinstance(valeur, bool):
        return int(valeur)
    if isinstance(valeur, (int, float)):
        return int(valeur != 0)

    texte = normaliser_texte(str(valeur))
    if any(mot in texte for mot in ["oui", "ouais", "yes", "1", "vrai", "true"]):
        return 1
    return 0


def _encoder_choix(question: dict, reponse) -> int:
    if reponse is None:
        return 0

    if isinstance(reponse, (int, float)):
        return int(reponse)

    choix = question.get("choix") or []
    texte_reponse = normaliser_texte(str(reponse))
    for index, option in enumerate(choix):
        if normaliser_texte(option) in texte_reponse or texte_reponse in normaliser_texte(option):
            return index

    if texte_reponse.isdigit():
        return int(texte_reponse)

    return 0


def _normaliser_texte_reponse(reponse) -> str:
    return normaliser_texte(str(reponse or "").strip())


def _encoder_duree_generique(texte: str) -> int:
    if not texte:
        return 0

    if any(mot in texte for mot in ["semaine", "semaines", "mois", "plus de 3 jours", "4 jours", "5 jours", "6 jours"]):
        return 2
    if any(mot in texte for mot in ["jour", "jours", "hier", "avant hier", "2 jours", "3 jours"]):
        return 1
    if any(mot in texte for mot in ["heure", "heures", "ce matin", "cette nuit", "depuis peu", "quelques heures", "minute", "minutes"]):
        return 0

    match = re.search(r"(\d+)", texte)
    if match:
        valeur = int(match.group(1))
        if "heure" in texte or "h" in texte:
            return 0 if valeur < 24 else 1
        if "jour" in texte:
            return 2 if valeur > 3 else 1

    return 0


def _encoder_duree_dyspnee(texte: str) -> int:
    if not texte:
        return 0

    if any(mot in texte for mot in ["semaine", "semaines", "plus de 3 jours", "4 jours", "5 jours", "6 jours", "mois"]):
        return 3
    if any(mot in texte for mot in ["1 jour", "2 jours", "3 jours", "depuis hier", "jours"]):
        return 2
    if any(mot in texte for mot in ["quelques heures", "2 heures", "3 heures", "4 heures", "5 heures", "6 heures", "7 heures", "8 heures"]):
        return 1
    if any(mot in texte for mot in ["minute", "minutes", "moins de 1 heure", "ce matin", "depuis peu", "1 heure"]):
        return 0

    match = re.search(r"(\d+)", texte)
    if match:
        valeur = int(match.group(1))
        if "heure" in texte or "h" in texte:
            if valeur <= 1:
                return 0
            if valeur <= 8:
                return 1
            if valeur < 24:
                return 1
            return 2
        if "jour" in texte:
            return 3 if valeur > 3 else 2

    return 0


def _encoder_localisation_abdomen(texte: str) -> int:
    if any(mot in texte for mot in ["droite", "flanc droit", "fosse iliaque droite", "bas droite"]):
        return 0
    if any(mot in texte for mot in ["gauche", "flanc gauche", "bas gauche"]):
        return 1
    if any(mot in texte for mot in ["centre", "milieu", "epigastre", "autour du nombril"]):
        return 2
    if any(mot in texte for mot in ["partout", "diffuse", "diffus", "tout le ventre"]):
        return 3
    return 0


def _encoder_texte_libre(question: dict, reponse) -> int:
    texte = _normaliser_texte_reponse(reponse)
    feature = question.get("feature_name") or ""

    if not texte:
        return 0

    if feature == "q_duree_dyspnee":
        return _encoder_duree_dyspnee(texte)
    if feature in {"q_duree_fievre", "q_duree_symptomes"}:
        return _encoder_duree_generique(texte)
    if feature == "q_localisation_abdomen":
        return _encoder_localisation_abdomen(texte)

    # Pour les autres features, un texte non vide est interpreté comme une confirmation.
    return 1


def _charger_banque_questions_externe() -> List[dict]:
    global _EXTERNAL_QUESTION_BANK
    if _EXTERNAL_QUESTION_BANK is not None:
        return _EXTERNAL_QUESTION_BANK

    banque: List[dict] = []

    # Priorite a la base unifiee (patients + questions) quand disponible.
    if UNIFIED_DB_PATH.exists():
        try:
            with sqlite3.connect(UNIFIED_DB_PATH) as conn:
                rows = conn.execute(
                    """
                    SELECT question_uid, scenario, feature_name, type, texte, choix_json, placeholder, poids
                    FROM question_bank
                    """
                ).fetchall()

            for row in rows:
                feature_name = str(row[2] or "").strip()
                if feature_name not in FEATURES_QUESTIONS:
                    continue

                qtype = str(row[3] or "oui_non").strip() or "oui_non"
                if qtype not in {"oui_non", "choix", "texte_libre"}:
                    qtype = "oui_non"

                choix = []
                choix_raw = row[5] or ""
                if choix_raw:
                    try:
                        parsed = json.loads(choix_raw)
                        if isinstance(parsed, list):
                            choix = [str(v) for v in parsed]
                    except Exception:
                        choix = []

                banque.append(
                    {
                        "id": str(row[0] or "").strip() or f"ext_{len(banque)+1}",
                        "scenario": str(row[1] or "general").strip() or "general",
                        "feature_name": feature_name,
                        "type": qtype,
                        "texte": str(row[4] or "").strip(),
                        "choix": choix,
                        "placeholder": str(row[6] or "").strip(),
                        "poids": int(row[7] or 60),
                    }
                )
        except Exception:
            banque = []

    if banque:
        _EXTERNAL_QUESTION_BANK = banque
        return _EXTERNAL_QUESTION_BANK

    _EXTERNAL_QUESTION_BANK = banque
    return _EXTERNAL_QUESTION_BANK


def _inferer_scenarios(
    constantes: dict,
    features_nlp: dict,
    age: int,
    sex: int,
    texte_norm: str,
) -> List[str]:
    scenarios = ["general"]

    if features_nlp.get("nlp_chest_pain", 0) == 1:
        scenarios.append("douleur_thoracique")
    if features_nlp.get("nlp_dyspnea", 0) == 1 or constantes.get("spo2", 98) < 93:
        scenarios.append("dyspnee")
    if features_nlp.get("nlp_fever", 0) == 1 or constantes.get("temperature", 37) >= 39.0:
        scenarios.append("fievre")
    if features_nlp.get("nlp_abdominal_pain", 0) == 1 or "ventre" in texte_norm:
        scenarios.append("abdomen")
    if features_nlp.get("nlp_trauma", 0) == 1:
        scenarios.append("trauma")
    if features_nlp.get("nlp_neurological", 0) == 1:
        scenarios.append("neuro")
    if constantes.get("bp_systolic", 120) >= 160 or constantes.get("bp_diastolic", 80) >= 100:
        scenarios.append("hypertension")
    if constantes.get("glucose", 90) < 70 or "diabet" in texte_norm:
        scenarios.append("glycemie")
    if age < 5:
        scenarios.append("pediatrie")
    if sex == 0 and 12 <= age <= 55 and "saign" in texte_norm:
        scenarios.append("grossesse")

    return list(dict.fromkeys(scenarios))


def _ajouter_candidats_banque_externe(
    candidats: List[Tuple[int, dict]],
    constantes: dict,
    features_nlp: dict,
    age: int,
    sex: int,
    texte_norm: str,
    signature: int,
) -> None:
    banque = _charger_banque_questions_externe()
    if not banque:
        return

    scenarios = set(_inferer_scenarios(constantes, features_nlp, age, sex, texte_norm))
    pool = [q for q in banque if q.get("scenario") in scenarios]
    if not pool:
        return

    rng = random.Random(signature)
    rng.shuffle(pool)

    # On injecte un sous-ensemble large pour favoriser la diversité, puis la sélection
    # finale garde les meilleures questions sans doublons de feature.
    limite = min(len(pool), 80)
    for ext in pool[:limite]:
        q = _question(
            question_id=ext.get("id") or f"ext_{signature}",
            texte=ext.get("texte") or "Pouvez-vous préciser vos symptômes ?",
            feature_name=ext.get("feature_name") or "q_antecedent_symptome",
            type_question=ext.get("type") or "oui_non",
            choix=ext.get("choix") or None,
            placeholder=ext.get("placeholder") or None,
        )
        score = int(ext.get("poids", 60))
        candidats.append((score, deepcopy(q)))


def _signature_patient(constantes: dict, symptom_text: str, age: int, sex: int) -> int:
    """Construit une signature stable pour varier la sélection de manière déterministe."""
    parties = [
        str(age),
        str(sex),
        normaliser_texte(symptom_text or ""),
        str(round(float(constantes.get("temperature", 0) or 0), 1)),
        str(int(float(constantes.get("heart_rate", 0) or 0))),
        str(int(float(constantes.get("bp_systolic", 0) or 0))),
        str(int(float(constantes.get("bp_diastolic", 0) or 0))),
        str(round(float(constantes.get("spo2", 0) or 0), 1)),
        str(int(float(constantes.get("respiratory_rate", 0) or 0))),
        str(round(float(constantes.get("glucose", 0) or 0), 1)),
    ]
    chaine = "|".join(parties)
    return int(hashlib.sha256(chaine.encode("utf-8")).hexdigest()[:8], 16)


def _charger_historique_questions() -> dict:
    global _QUESTION_USAGE_CACHE
    if _QUESTION_USAGE_CACHE is not None:
        return _QUESTION_USAGE_CACHE

    if not QUESTION_USAGE_PATH.exists():
        _QUESTION_USAGE_CACHE = {}
        return _QUESTION_USAGE_CACHE

    try:
        with QUESTION_USAGE_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
            _QUESTION_USAGE_CACHE = data if isinstance(data, dict) else {}
    except Exception:
        _QUESTION_USAGE_CACHE = {}

    return _QUESTION_USAGE_CACHE


def _sauvegarder_historique_questions(historique: dict) -> None:
    global _QUESTION_USAGE_CACHE
    _QUESTION_USAGE_CACHE = historique
    try:
        QUESTION_USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with QUESTION_USAGE_PATH.open("w", encoding="utf-8") as f:
            json.dump(historique, f, ensure_ascii=False)
    except Exception:
        # Le moteur continue de fonctionner meme si la persistence echoue.
        pass


def _historique_key(signature: int) -> str:
    return f"sig_{signature:08x}"


def _mettre_a_jour_historique_questions(historique: dict, key: str, questions: list) -> None:
    ids = [str(q.get("id", "")).strip() for q in questions if str(q.get("id", "")).strip()]
    if not ids:
        return

    precedents = historique.get(key, [])
    precedents = [str(v) for v in precedents if str(v).strip()]
    fusion = (precedents + ids)[-MAX_USAGE_HISTORY:]
    historique[key] = fusion


def _enrichir_candidats_transverses(
    candidats: List[Tuple[int, dict]],
    constantes: dict,
    features_nlp: dict,
    age: int,
    sex: int,
    texte_norm: str,
) -> None:
    """Ajoute des candidats transverses pour mieux couvrir les profils atypiques."""
    if features_nlp.get("nlp_pain", 0) == 1 or constantes.get("heart_rate", 0) > 105:
        candidats.append((67, deepcopy(_question("q_aggravation_effort", "Votre douleur augmente-t-elle à l'effort ?", "q_aggravation_effort"))))

    if age >= 65 or "chronique" in texte_norm or "depuis" in texte_norm:
        candidats.append((66, deepcopy(_question("q_antecedent_symptome", "Ces symptômes sont-ils déjà survenus auparavant ?", "q_antecedent_symptome"))))

    if "medic" in texte_norm or "traitement" in texte_norm or constantes.get("glucose", 90) < 70:
        candidats.append((65, deepcopy(_question("q_prise_medicament", "Avez-vous pris un traitement avant de venir ?", "q_prise_medicament"))))

    if sex == 0 and 12 <= age <= 55 and ("retard" in texte_norm or "saign" in texte_norm):
        candidats.append((70, deepcopy(_question("q_grossesse_possible", "Existe-t-il une possibilité de grossesse ?", "q_grossesse_possible"))))

    if features_nlp.get("nlp_fever", 0) == 1 and constantes.get("temperature", 37) >= 38.5:
        candidats.append((68, deepcopy(_question("q_duree_symptomes", "Décrivez depuis quand les symptômes ont débuté.", "q_duree_symptomes", "texte_libre", placeholder="Exemple: depuis hier, depuis 3 jours")) ))

    if constantes.get("spo2", 98) < 92:
        candidats.append((91, deepcopy(_question("q_duree_dyspnee", "La gêne respiratoire est présente depuis quand exactement ?", "q_duree_dyspnee", "texte_libre", placeholder="Exemple: depuis 1h, depuis cette nuit"))))

    if constantes.get("temperature", 37) >= 39.2:
        candidats.append((89, deepcopy(_question("q_duree_fievre", "Précisez la durée de la fièvre et son évolution.", "q_duree_fievre", "texte_libre", placeholder="Exemple: fièvre depuis 2 jours, en hausse"))))


def _garantir_question_ouverte(selection: list, candidats: List[Tuple[int, dict]], vus: set) -> list:
    if any(q.get("type") == "texte_libre" for q in selection):
        return selection

    ouverts = [q for _, q in sorted(candidats, key=lambda item: item[0], reverse=True) if q.get("type") == "texte_libre"]
    for q in ouverts:
        feature = q.get("feature_name")
        if feature in vus:
            continue
        if selection:
            selection[-1] = deepcopy(q)
        else:
            selection.append(deepcopy(q))
        vus.add(feature)
        break

    return selection


def _selection_diversifiee(
    candidats: List[Tuple[int, dict]],
    signature: int,
    nb_voulu: int,
    ids_a_eviter: set | None = None,
) -> list:
    """Sélectionne des questions en conservant la pertinence tout en variant les combinaisons."""
    if not candidats:
        return []

    ids_a_eviter = ids_a_eviter or set()

    # Grouper par feature pour pouvoir choisir des variantes differentes dans le temps.
    par_feature = {}
    for score, question in candidats:
        feature = question["feature_name"]
        par_feature.setdefault(feature, []).append((score, question))

    meilleurs = []
    for feature, variantes in par_feature.items():
        variantes = sorted(variantes, key=lambda item: item[0], reverse=True)

        # Prioriser une variante pas encore vue pour cette signature patient.
        choisie = None
        for item in variantes:
            qid = str(item[1].get("id", "")).strip()
            if qid and qid not in ids_a_eviter:
                choisie = item
                break

        if choisie is None:
            # Rotation pseudo-aléatoire pour éviter la même formulation en boucle.
            index = signature % len(variantes)
            choisie = variantes[index]

        meilleurs.append(choisie)

    base = sorted(meilleurs, key=lambda item: item[0], reverse=True)
    pool = base[: max(nb_voulu + 6, 10)]

    selection = []
    deja = set()

    # Toujours garder les 2 plus pertinents si disponibles.
    for score, question in pool[:2]:
        feature = question["feature_name"]
        if feature in deja:
            continue
        selection.append(deepcopy(question))
        deja.add(feature)

    # Compléter avec un parcours pseudo-aléatoire déterministe.
    if len(selection) < nb_voulu and pool:
        start = signature % len(pool)
        stride = (signature % 7) + 1
        while stride % 2 == 0:
            stride += 1

        index = start
        tours = 0
        limite = len(pool) * 3
        while len(selection) < nb_voulu and tours < limite:
            _, question = pool[index]
            feature = question["feature_name"]
            if feature not in deja:
                selection.append(deepcopy(question))
                deja.add(feature)
            index = (index + stride) % len(pool)
            tours += 1

    return selection[:nb_voulu]


def detecter_flags(constantes: dict, symptom_text: str, age: int, sex: int) -> dict:
    """Retourne des drapeaux cliniques rapides utilises avant generation des questions."""
    constantes = constantes or {}
    nlp = extraire_features_nlp(symptom_text or "")

    flags = {
        "critique_immediate": False,
        "detresse_respiratoire": False,
        "suspicion_cardiaque": False,
        "fievre_elevee": False,
        "profil_vulnerable": age < 5 or age > 70,
        "grossesse_possible": sex == 0 and 12 <= age <= 55,
    }

    spo2 = float(constantes.get("spo2", 98) or 98)
    fc = float(constantes.get("heart_rate", 75) or 75)
    temp = float(constantes.get("temperature", 37) or 37)
    ta_sys = float(constantes.get("bp_systolic", 120) or 120)

    if nlp.get("nlp_loss_of_consciousness", 0) == 1 or nlp.get("nlp_severe_bleeding", 0) == 1:
        flags["critique_immediate"] = True

    if spo2 < 92 or nlp.get("nlp_dyspnea", 0) == 1:
        flags["detresse_respiratoire"] = True

    if nlp.get("nlp_chest_pain", 0) == 1 and (fc > 110 or ta_sys > 160):
        flags["suspicion_cardiaque"] = True

    if temp >= 39 or nlp.get("nlp_fever", 0) == 1:
        flags["fievre_elevee"] = True

    if flags["critique_immediate"]:
        flags["detresse_respiratoire"] = True

    return flags


def generer_questions(constantes: dict, symptom_text: str, age: int, sex: int) -> list:
    """Génère 4 à 6 questions adaptées au patient."""
    constantes = constantes or {}
    symptom_text = symptom_text or ""
    features_nlp = extraire_features_nlp(symptom_text)

    questions_candidats: List[Tuple[int, dict]] = []
    texte_norm = normaliser_texte(symptom_text)

    for scenario in sorted(QUESTION_BANK.values(), key=lambda item: item["poids"], reverse=True):
        if scenario["condition"](constantes, features_nlp, age, sex, texte_norm):
            for ordre, question in enumerate(scenario["questions"]):
                questions_candidats.append((scenario["poids"] - ordre, deepcopy(question)))

    signature = _signature_patient(constantes, symptom_text, age, sex)
    _ajouter_candidats_banque_externe(
        questions_candidats,
        constantes,
        features_nlp,
        age,
        sex,
        texte_norm,
        signature,
    )

    _enrichir_candidats_transverses(
        questions_candidats,
        constantes,
        features_nlp,
        age,
        sex,
        texte_norm,
    )

    if not questions_candidats:
        for ordre, question in enumerate(FALLBACK_QUESTIONS):
            questions_candidats.append((50 - ordre, deepcopy(question)))

    historique = _charger_historique_questions()
    histo_key = _historique_key(signature)
    ids_a_eviter = set(str(v) for v in historique.get(histo_key, []))
    signature_runtime = signature ^ random.SystemRandom().randint(0, 0x7FFFFFFF)

    nb_voulu = MIN_QUESTIONS + (signature % (MAX_QUESTIONS - MIN_QUESTIONS + 1))
    selection = _selection_diversifiee(
        questions_candidats,
        signature_runtime,
        nb_voulu,
        ids_a_eviter=ids_a_eviter,
    )
    vus = {q["feature_name"] for q in selection}
    selection = _garantir_question_ouverte(selection, questions_candidats, vus)

    # S'assurer qu'il y a au moins MIN_QUESTIONS questions.
    if len(selection) < MIN_QUESTIONS:
        for question in FALLBACK_QUESTIONS:
            if question["feature_name"] in vus:
                continue
            selection.append(deepcopy(question))
            vus.add(question["feature_name"])
            if len(selection) >= MIN_QUESTIONS:
                break

    for index, question in enumerate(selection, start=1):
        question["id"] = question.get("id") or f"q{index}"
        if question.get("type") != "choix":
            question.pop("choix", None)

    _mettre_a_jour_historique_questions(historique, histo_key, selection)
    _sauvegarder_historique_questions(historique)

    return selection[:MAX_QUESTIONS]


def encoder_reponses(questions: list, reponses: dict) -> dict:
    """Encode les réponses du questionnaire en features numériques."""
    reponses = reponses or {}
    features = {feature: 0 for feature in FEATURES_QUESTIONS}

    for question in questions or []:
        feature_name = question.get("feature_name") or question.get("id")
        if not feature_name:
            continue

        valeur = reponses.get(question.get("id"))
        if valeur is None:
            valeur = reponses.get(feature_name)

        if question.get("type") == "oui_non":
            features[feature_name] = _normaliser_bool(valeur)
        elif question.get("type") == "choix":
            features[feature_name] = _encoder_choix(question, valeur)
        elif question.get("type") == "texte_libre":
            features[feature_name] = _encoder_texte_libre(question, valeur)
        else:
            features[feature_name] = _normaliser_bool(valeur)

    return features


# ─────────────────────────────────────────────────────────────────────────────
# Moteur strict de questions ciblées
# ─────────────────────────────────────────────────────────────────────────────

MIN_QUESTIONS = 3
MAX_QUESTIONS = 5

FEATURES_QUESTIONS = [
    "q_craquement_trauma",
    "q_appui_pied_trauma",
    "q_gonflement_trauma",
    "q_deformation_trauma",
    "q_perte_conscience_trauma",
    "q_saignement_trauma",
    "q_mecanisme_trauma",
    "q_douleur_irradiee_bras",
    "q_douleur_repos_effort",
    "q_duree_douleur_thoracique",
    "q_sueurs_froides_cardiaque",
    "q_antecedent_infarctus",
    "q_medicaments_coeur",
    "q_palpitations_cardiaque",
    "q_duree_dyspnee",
    "q_asthme_poumon",
    "q_dyspnee_repos",
    "q_crachats_sang",
    "q_crise_similaire_respiratoire",
    "q_fievre_associee_respiratoire",
    "q_localisation_abdomen",
    "q_debut_abdomen",
    "q_vomissements_abdomen",
    "q_fievre_abdomen",
    "q_aggravation_marche",
    "q_sang_selles",
    "q_neuro_faiblesse",
    "q_neuro_parole",
    "q_neuro_debut_soudain",
    "q_neuro_perte_conscience",
    "q_neuro_antcedent",
    "q_duree_fievre",
    "q_frissons_fievre",
    "q_voyage_fievre",
    "q_medicaments_fievre",
    "q_toux_fievre",
    "q_entourage_malade",
    "q_douleur_urinaire_fievre",
    "q_douleur_flancs",
    "q_urines_troubles",
    "q_duree_urinaire",
    "q_mal_de_gorge_fievre",
    "q_dysphagie_orl",
    "q_duree_orl",
    "q_ganglions_orl",
    "q_rougeur_peau",
    "q_demangeaison_peau",
    "q_allergie_peau",
    "q_plaie_peau",
    "q_traitement_diabete",
    "q_mange_diabete",
    "q_tremblements_diabete",
    "q_duree_mal_diabete",
    "q_grossesse_mois",
    "q_saignement_vaginal",
    "q_contractions_grossesse",
    "q_bebe_bouge",
    "q_hydratation_pediatrie",
    "q_reveil_pediatrie",
    "q_convulsions_pediatrie",
    "q_duree_mal_pediatrie",
    "q_hypertension_connue",
    "q_traitement_tension",
    "q_vision_hypertension",
    "q_medicaments_generaux",
    "q_allergies_generales",
    "q_premiere_fois",
    "q_geriatrie_chutes",
    "q_geriatrie_medicaments",
    "q_geriatrie_memor",
]


def _q(
    question_id: str,
    texte: str,
    feature_name: str,
    categorie: str,
    priorite: int,
    type_question: str = "oui_non",
    choix: List[str] | None = None,
) -> dict:
    question = {
        "id": question_id,
        "texte": texte,
        "type": type_question,
        "feature_name": feature_name,
        "categorie": categorie,
        "priorite": priorite,
    }
    if type_question == "choix" and choix:
        question["choix"] = choix
    return question


DETECTION_MOTS_CLES = {
    "trauma": {"mots": ["chute", "tomb", "accident", "voiture", "moto", "velo", "blessure", "fracture", "cass", "os", "entorse", "genou", "cheville", "pied", "bras", "coup", "heurte", "agression", "couteau", "balle", "brulure", "feu", "contusion"], "exclure_si": []},
    "cardiaque": {"mots": ["poitrine", "thorax", "coeur", "cardiaque", "palpitation", "serrement", "oppression", "infarctus", "bras gauche", "machoire", "angine"], "exclure_si": []},
    "respiratoire": {"mots": ["respir", "essouffl", "souffle", "haleter", "haletant", "poumon", "bronchite", "asthme", "toux", "cracher", "mal a respirer", "manque d'air"], "exclure_si": []},
    "abdominal": {"mots": ["ventre", "abdomen", "estomac", "intestin", "nause", "vomit", "diarr", "constip", "foie", "rate", "bas-ventre", "crampe", "appendice"], "exclure_si": []},
    "neurologique": {"mots": ["tete", "migraine", "vertige", "vision", "vue", "paralys", "engourdissement", "parler", "elocution", "convulsion", "epilepsie", "inconscient", "cerveau"], "exclure_si": []},
    "fievre": {"mots": ["fievre", "chaud", "temperature", "frisson", "sueur", "transpire", "brulant", "38", "39", "40", "41", "sokhana", "sakhen"], "exclure_si": []},
    "urinaire": {"mots": ["urine", "uriner", "pipi", "brulure urinaire", "envie frequente", "sang dans les urines", "rein", "vessie", "prostate"], "exclure_si": []},
    "orl": {"mots": ["gorge", "oreille", "nez", "rhume", "enrhume", "avaler", "deglutir", "mal de gorge", "otite", "sinusite", "bouche"], "exclure_si": []},
    "dermatologie": {"mots": ["peau", "rougeur", "eruption", "bouton", "demangeaison", "gratter", "allergie", "urticaire", "plaie", "cicatrice", "gonflement", "oedeme"], "exclure_si": []},
    "diabete": {"mots": ["diabete", "diabetique", "insuline", "sucre", "glycemie", "hypoglycemie", "hyperglycemie", "soif intense"], "exclure_si": []},
    "grossesse": {"mots": ["enceinte", "grossesse", "bebe", "accouchement", "contraction", "perdre les eaux", "saignement vaginal", "saignements vaginaux", "bas-ventre", "bas ventre"], "exclure_si": []},
    "pediatrie": {"mots": ["enfant", "bebe", "nourrisson", "mon fils", "ma fille", "il tete", "elle tete", "vaccin"], "exclure_si": []},
    "hypertension": {"mots": ["tension", "hypertension", "hta", "pression"], "exclure_si": []},
    "geriatrie": {"mots": ["chute", "marche", "memoire", "confusion", "traitement", "medicament"], "exclure_si": []},
}

FLAGS_CONSTANTES = {
    "fievre": lambda c: float(c.get("temperature", 37) or 37) > 38.5,
    "hypothermie": lambda c: float(c.get("temperature", 37) or 37) < 36.0,
    "cardiaque": lambda c: float(c.get("heart_rate", 75) or 75) > 110 or float(c.get("heart_rate", 75) or 75) < 50,
    "respiratoire": lambda c: float(c.get("spo2", 98) or 98) < 94,
    "hypertension": lambda c: float(c.get("bp_systolic", 120) or 120) > 155,
    "diabete": lambda c: float(c.get("glucose", 90) or 90) < 70 or float(c.get("glucose", 90) or 90) > 250,
}

BANQUE_QUESTIONS = {
    "trauma": [
        _q("trauma_01", "Avez-vous entendu un craquement au moment de la blessure ?", "q_craquement_trauma", "trauma", 1),
        _q("trauma_02", "Pouvez-vous poser le pied par terre ou bouger la partie blessée ?", "q_appui_pied_trauma", "trauma", 2),
        _q("trauma_03", "Le membre est-il gonfle ou deformé ?", "q_gonflement_trauma", "trauma", 3),
        _q("trauma_04", "Avez-vous perdu connaissance après le choc ?", "q_perte_conscience_trauma", "trauma", 4),
        _q("trauma_05", "Y a-t-il un saignement visible ?", "q_saignement_trauma", "trauma", 5),
        _q("trauma_06", "Comment s'est produit l'accident ?", "q_mecanisme_trauma", "trauma", 6, "choix", ["Chute", "Accident de voiture", "Accident de moto", "Agression", "Autre"]),
        _q("trauma_07", "La douleur est-elle localisee au pied, a la cheville, au genou, au bras ou ailleurs ?", "q_deformation_trauma", "trauma", 7, "choix", ["Pied", "Cheville", "Genou", "Bras", "Autre"]),
    ],
    "cardiaque": [
        _q("cardiaque_01", "La douleur irradie-t-elle vers le bras gauche ou la machoire ?", "q_douleur_irradiee_bras", "cardiaque", 1),
        _q("cardiaque_02", "La douleur est-elle apparue au repos ou pendant un effort ?", "q_douleur_repos_effort", "cardiaque", 2, "choix", ["Au repos", "Pendant un effort", "Les deux"]),
        _q("cardiaque_03", "Depuis combien de temps avez-vous cette douleur ?", "q_duree_douleur_thoracique", "cardiaque", 3, "choix", ["Moins de 30 minutes", "30 min a 2 heures", "Plus de 2 heures"]),
        _q("cardiaque_04", "Avez-vous des sueurs froides en ce moment ?", "q_sueurs_froides_cardiaque", "cardiaque", 4),
        _q("cardiaque_05", "Avez-vous deja eu un infarctus ou une maladie du coeur ?", "q_antecedent_infarctus", "cardiaque", 5),
        _q("cardiaque_06", "Prenez-vous des medicaments pour le coeur ou la tension ?", "q_medicaments_coeur", "cardiaque", 6),
        _q("cardiaque_07", "Ressentez-vous des palpitations ou un rythme irregulier ?", "q_palpitations_cardiaque", "cardiaque", 7),
    ],
    "respiratoire": [
        _q("respiratoire_01", "L'essoufflement est-il apparu soudainement ou progressivement ?", "q_duree_dyspnee", "respiratoire", 1, "choix", ["Soudainement", "Progressivement en quelques heures", "Depuis plusieurs jours"]),
        _q("respiratoire_02", "Avez-vous de l'asthme ou une maladie des poumons ?", "q_asthme_poumon", "respiratoire", 2),
        _q("respiratoire_03", "Avez-vous du mal a respirer meme au repos ?", "q_dyspnee_repos", "respiratoire", 3),
        _q("respiratoire_04", "Crachez-vous du sang ou des crachats colores ?", "q_crachats_sang", "respiratoire", 4),
        _q("respiratoire_05", "Avez-vous deja eu des crises similaires ?", "q_crise_similaire_respiratoire", "respiratoire", 5),
        _q("respiratoire_06", "Avez-vous de la fievre en plus de la difficulte a respirer ?", "q_fievre_associee_respiratoire", "respiratoire", 6),
    ],
    "fievre": [
        _q("fievre_01", "Depuis combien de jours avez-vous de la fievre ?", "q_duree_fievre", "fievre", 1, "choix", ["Moins de 24 heures", "1 a 3 jours", "Plus de 3 jours"]),
        _q("fievre_02", "Avez-vous des frissons intenses ?", "q_frissons_fievre", "fievre", 2),
        _q("fievre_03", "Avez-vous voyage en dehors de la ville recemment ?", "q_voyage_fievre", "fievre", 3),
        _q("fievre_04", "Avez-vous pris des medicaments contre la fievre ?", "q_medicaments_fievre", "fievre", 4),
        _q("fievre_05", "Avez-vous de la toux en plus de la fievre ?", "q_toux_fievre", "fievre", 5),
        _q("fievre_06", "D'autres personnes dans votre entourage sont-elles malades ?", "q_entourage_malade", "fievre", 6),
    ],
    "abdominal": [
        _q("abdominal_01", "Ou se situe exactement la douleur ?", "q_localisation_abdomen", "abdominal", 1, "choix", ["Cote droit", "Cote gauche", "Centre", "Tout le ventre"]),
        _q("abdominal_02", "La douleur est-elle apparue brutalement ou progressivement ?", "q_debut_abdomen", "abdominal", 2, "choix", ["Brutalement", "Progressivement"]),
        _q("abdominal_03", "Avez-vous vomi ou avez-vous envie de vomir ?", "q_vomissements_abdomen", "abdominal", 3),
        _q("abdominal_04", "Avez-vous de la fievre en meme temps ?", "q_fievre_abdomen", "abdominal", 4),
        _q("abdominal_05", "La douleur empire-t-elle quand vous marchez ou bougez ?", "q_aggravation_marche", "abdominal", 5),
        _q("abdominal_06", "Avez-vous du sang dans vos selles ?", "q_sang_selles", "abdominal", 6),
    ],
    "neurologique": [
        _q("neuro_01", "Ressentez-vous une faiblesse ou une paralysie d'un cote du corps ?", "q_neuro_faiblesse", "neurologique", 1),
        _q("neuro_02", "Avez-vous du mal a parler ou a comprendre ce qu'on vous dit ?", "q_neuro_parole", "neurologique", 2),
        _q("neuro_03", "Les symptomes sont-ils apparus soudainement ?", "q_neuro_debut_soudain", "neurologique", 3),
        _q("neuro_04", "Avez-vous perdu connaissance meme brievement ?", "q_neuro_perte_conscience", "neurologique", 4),
        _q("neuro_05", "Avez-vous des antecedents d'AVC ou d'epilepsie ?", "q_neuro_antcedent", "neurologique", 5),
    ],
    "urinaire": [
        _q("urinaire_01", "Avez-vous de la fievre en plus des douleurs urinaires ?", "q_douleur_urinaire_fievre", "urinaire", 1),
        _q("urinaire_02", "Avez-vous des douleurs dans le dos ou les flancs ?", "q_douleur_flancs", "urinaire", 2),
        _q("urinaire_03", "Vos urines sont-elles troubles ou de couleur anormale ?", "q_urines_troubles", "urinaire", 3),
        _q("urinaire_04", "Depuis combien de temps avez-vous ces symptomes ?", "q_duree_urinaire", "urinaire", 4, "choix", ["Moins de 24 heures", "1 a 3 jours", "Plus de 3 jours"]),
    ],
    "orl": [
        _q("orl_01", "Avez-vous de la fievre en plus du mal de gorge ?", "q_mal_de_gorge_fievre", "orl", 1),
        _q("orl_02", "Avez-vous du mal a avaler les aliments solides ?", "q_dysphagie_orl", "orl", 2),
        _q("orl_03", "Depuis combien de jours avez-vous ces symptomes ?", "q_duree_orl", "orl", 3, "choix", ["Moins de 2 jours", "2 a 5 jours", "Plus de 5 jours"]),
        _q("orl_04", "Avez-vous des ganglions gonfles dans le cou ?", "q_ganglions_orl", "orl", 4),
    ],
    "dermatologie": [
        _q("derm_01", "La rougeur ou l'irritation de la peau s'etend-elle ?", "q_rougeur_peau", "dermatologie", 1),
        _q("derm_02", "Avez-vous des demangeaisons importantes ?", "q_demangeaison_peau", "dermatologie", 2),
        _q("derm_03", "Pensez-vous a une allergie ou a un contact recent avec quelque chose d'inhabituel ?", "q_allergie_peau", "dermatologie", 3),
        _q("derm_04", "La peau est-elle ouverte, avec plaie ou suintement ?", "q_plaie_peau", "dermatologie", 4),
    ],
    "diabete": [
        _q("diabete_01", "Avez-vous pris votre traitement du diabete aujourd'hui ?", "q_traitement_diabete", "diabete", 1),
        _q("diabete_02", "Avez-vous mange normalement aujourd'hui ?", "q_mange_diabete", "diabete", 2),
        _q("diabete_03", "Ressentez-vous des tremblements ou des sueurs froides ?", "q_tremblements_diabete", "diabete", 3),
        _q("diabete_04", "Depuis combien de temps vous sentez-vous mal ?", "q_duree_mal_diabete", "diabete", 4, "choix", ["Moins d'1 heure", "1 a 6 heures", "Plus de 6 heures"]),
    ],
    "grossesse": [
        _q("grossesse_01", "A combien de mois de grossesse etes-vous ?", "q_grossesse_mois", "grossesse", 1, "choix", ["Moins de 3 mois", "3 a 6 mois", "Plus de 6 mois", "Je ne sais pas"]),
        _q("grossesse_02", "Avez-vous des saignements vaginaux ?", "q_saignement_vaginal", "grossesse", 2),
        _q("grossesse_03", "Avez-vous des contractions ou des douleurs pelviennes ?", "q_contractions_grossesse", "grossesse", 3),
        _q("grossesse_04", "Le bebe bouge-t-il normalement ?", "q_bebe_bouge", "grossesse", 4),
    ],
    "pediatrie": [
        _q("pediatrie_01", "L'enfant mange-t-il ou tete-t-il normalement ?", "q_hydratation_pediatrie", "pediatrie", 1),
        _q("pediatrie_02", "L'enfant est-il difficile a reveiller ou tres agite ?", "q_reveil_pediatrie", "pediatrie", 2),
        _q("pediatrie_03", "A-t-il eu des convulsions ?", "q_convulsions_pediatrie", "pediatrie", 3),
        _q("pediatrie_04", "Depuis combien de temps est-il malade ?", "q_duree_mal_pediatrie", "pediatrie", 4, "choix", ["Moins de 24 heures", "1 a 3 jours", "Plus de 3 jours"]),
    ],
    "hypertension": [
        _q("hta_01", "Avez-vous une hypertension connue et traitee ?", "q_hypertension_connue", "hypertension", 1),
        _q("hta_02", "Avez-vous pris vos medicaments aujourd'hui ?", "q_traitement_tension", "hypertension", 2),
        _q("hta_03", "Avez-vous des troubles de la vision en ce moment ?", "q_vision_hypertension", "hypertension", 3),
    ],
    "geriatrie": [
        _q("geriat_01", "Avez-vous fait une chute recemment ?", "q_geriatrie_chutes", "geriatrie", 1),
        _q("geriat_02", "Prenez-vous plusieurs medicaments chaque jour ?", "q_geriatrie_medicaments", "geriatrie", 2),
        _q("geriat_03", "Avez-vous des troubles de memoire ou de confusion inhabituels ?", "q_geriatrie_memor", "geriatrie", 3),
    ],
    "generale": [
        _q("general_01", "Prenez-vous des medicaments en ce moment ?", "q_medicaments_generaux", "generale", 1),
        _q("general_02", "Avez-vous des allergies connues aux medicaments ?", "q_allergies_generales", "generale", 2),
        _q("general_03", "Est-ce la premiere fois que vous avez ces symptomes ?", "q_premiere_fois", "generale", 3),
    ],
}


def _texte_normalise_symptome(symptom_text: str) -> str:
    return normaliser_texte(symptom_text or "")


def _texte_recherche(texte: str) -> str:
    if not isinstance(texte, str) or not texte.strip():
        return ""
    texte = texte.lower().strip()
    texte = unicodedata.normalize("NFD", texte)
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    texte = re.sub(r"\s+", " ", texte)
    return texte


def _contient_mot_cle(texte_norm: str, mots: List[str]) -> bool:
    texte_norm = _texte_recherche(texte_norm)
    for mot in mots:
        mot_norm = _texte_recherche(mot)
        if mot_norm and mot_norm in texte_norm:
            return True
    return False


def _detected_categories_from_text(symptom_text: str, age: int, sex: int) -> List[str]:
    texte_norm = _texte_normalise_symptome(symptom_text)
    categories: List[str] = []

    for categorie, spec in DETECTION_MOTS_CLES.items():
        if categorie == "grossesse":
            if sex == 0 and 14 <= age <= 55 and _contient_mot_cle(texte_norm, spec["mots"]):
                categories.append(categorie)
            elif sex == 0 and 14 <= age <= 55 and any(mot in texte_norm for mot in ["saignement vaginal", "saignements vaginaux", "bas-ventre", "bas ventre"]):
                categories.append(categorie)
            continue

        if categorie == "pediatrie":
            if age < 12 or _contient_mot_cle(texte_norm, spec["mots"]):
                categories.append(categorie)
            continue

        if categorie == "geriatrie":
            if age > 65:
                categories.append(categorie)
            continue

        if _contient_mot_cle(texte_norm, spec["mots"]):
            categories.append(categorie)

    return categories


def _detected_categories_from_constants(constantes: dict) -> List[str]:
    constantes = constantes or {}
    categories: List[str] = []
    for categorie, predicate in FLAGS_CONSTANTES.items():
        try:
            if predicate(constantes):
                categories.append(categorie)
        except Exception:
            continue
    return categories


def _dedoublonner_questions(questions: List[dict]) -> List[dict]:
    vus = set()
    resultat = []
    for question in questions:
        identifiant = question.get("feature_name") or question.get("id")
        if not identifiant or identifiant in vus:
            continue
        vus.add(identifiant)
        resultat.append(question)
    return resultat


def _rotater_questions(questions: List[dict], signature: int) -> List[dict]:
    if not questions:
        return []
    index = signature % len(questions)
    return questions[index:] + questions[:index]


def _questions_generales(signature: int) -> List[dict]:
    banque = sorted(BANQUE_QUESTIONS["generale"], key=lambda q: (q.get("priorite", 99), q.get("id", "")))
    return _rotater_questions(banque, signature)


def _selectionner_questions_categories(categories: List[str], signature: int, nb_voulu: int) -> List[dict]:
    selection: List[dict] = []
    categories_ordonnee = list(dict.fromkeys(categories))
    rng = random.Random(signature)
    rng.shuffle(categories_ordonnee)

    for categorie in categories_ordonnee:
        banque = sorted(BANQUE_QUESTIONS.get(categorie, []), key=lambda q: (q.get("priorite", 99), q.get("id", "")))
        if not banque:
            continue
        rotation = _rotater_questions(banque, signature)
        quota = 2 if categorie != "generale" else 3
        selection.extend(rotation[:quota])
        if len(selection) >= nb_voulu:
            break

    return _dedoublonner_questions(selection)


def _signature_patient(constantes: dict, symptom_text: str, age: int, sex: int) -> int:
    parties = [
        str(age),
        str(sex),
        _texte_normalise_symptome(symptom_text),
        str(round(float(constantes.get("temperature", 0) or 0), 1)),
        str(int(float(constantes.get("heart_rate", 0) or 0))),
        str(int(float(constantes.get("bp_systolic", 0) or 0))),
        str(int(float(constantes.get("bp_diastolic", 0) or 0))),
        str(round(float(constantes.get("spo2", 0) or 0), 1)),
        str(int(float(constantes.get("respiratory_rate", 0) or 0))),
        str(round(float(constantes.get("glucose", 0) or 0), 1)),
    ]
    chaine = "|".join(parties)
    return int(hashlib.sha256(chaine.encode("utf-8")).hexdigest()[:8], 16)


def _questions_bank_flat() -> List[dict]:
    banque: List[dict] = []
    for categorie, questions in BANQUE_QUESTIONS.items():
        for question in questions:
            copie = deepcopy(question)
            copie.setdefault("categorie", categorie)
            banque.append(copie)
    return banque


def _charger_banque_questions_externe() -> List[dict]:
    banque: List[dict] = []

    if UNIFIED_DB_PATH.exists():
        try:
            with sqlite3.connect(UNIFIED_DB_PATH) as conn:
                rows = conn.execute(
                    """
                    SELECT question_uid, scenario, feature_name, type, texte, choix_json, placeholder, poids
                    FROM question_bank
                    """
                ).fetchall()

            for row in rows:
                feature_name = str(row[2] or "").strip()
                if feature_name and feature_name not in FEATURES_QUESTIONS:
                    continue

                qtype = str(row[3] or "oui_non").strip() or "oui_non"
                if qtype not in {"oui_non", "choix", "texte_libre"}:
                    qtype = "oui_non"

                choix = []
                choix_raw = row[5] or ""
                if choix_raw:
                    try:
                        parsed = json.loads(choix_raw)
                        if isinstance(parsed, list):
                            choix = [str(v) for v in parsed]
                    except Exception:
                        choix = []

                banque.append(
                    {
                        "id": str(row[0] or "").strip() or f"ext_{len(banque)+1}",
                        "categorie": str(row[1] or "generale").strip() or "generale",
                        "feature_name": feature_name or f"q_ext_{len(banque)+1}",
                        "type": qtype,
                        "texte": str(row[4] or "").strip(),
                        "choix": choix,
                        "placeholder": str(row[6] or "").strip(),
                        "priorite": int(row[7] or 60),
                    }
                )
        except Exception:
            banque = []

    if len(banque) >= 1000:
        return banque

    banque.extend(_questions_bank_flat())
    return banque


def detecter_flags(constantes: dict, symptom_text: str, age: int, sex: int) -> dict:
    constantes = constantes or {}
    symptom_text = symptom_text or ""
    text_categories = _detected_categories_from_text(symptom_text, age, sex)
    constant_categories = _detected_categories_from_constants(constantes)

    return {
        "categories_texte": text_categories,
        "categories_constantes": constant_categories,
        "categories": list(dict.fromkeys(text_categories + constant_categories)),
        "grossesse_possible": sex == 0 and 14 <= age <= 55 and "grossesse" in text_categories,
        "pediatrie": age < 12 or "pediatrie" in text_categories,
        "geriatrie": age > 65,
        "respiratoire": "respiratoire" in text_categories or "respiratoire" in constant_categories,
        "cardiaque": "cardiaque" in text_categories or "cardiaque" in constant_categories,
        "fievre": "fievre" in text_categories or "fievre" in constant_categories,
        "diabete": "diabete" in text_categories or "diabete" in constant_categories,
        "hypertension": "hypertension" in constant_categories,
    }


def generer_questions(constantes: dict, symptom_text: str, age: int, sex: int) -> list:
    constantes = constantes or {}
    symptom_text = symptom_text or ""
    signature = _signature_patient(constantes, symptom_text, age, sex)
    flags = detecter_flags(constantes, symptom_text, age, sex)
    categories = flags.get("categories", [])

    if not categories:
        categories = ["generale"]

    nb_voulu = MIN_QUESTIONS + (signature % (MAX_QUESTIONS - MIN_QUESTIONS + 1))
    selection = _selectionner_questions_categories(categories, signature, nb_voulu)

    if len(selection) < MIN_QUESTIONS:
        for question in _questions_generales(signature):
            if question.get("feature_name") in {q.get("feature_name") for q in selection}:
                continue
            selection.append(deepcopy(question))
            if len(selection) >= MIN_QUESTIONS:
                break

    selection = _dedoublonner_questions(selection)

    if len(selection) > MAX_QUESTIONS:
        selection = selection[:MAX_QUESTIONS]

    if len(selection) < MIN_QUESTIONS:
        for question in _questions_generales(signature):
            if question.get("feature_name") in {q.get("feature_name") for q in selection}:
                continue
            selection.append(deepcopy(question))
            if len(selection) >= MIN_QUESTIONS:
                break

    final = []
    for index, question in enumerate(selection, start=1):
        question = deepcopy(question)
        question["id"] = question.get("id") or f"q{index}"
        if question.get("type") == "choix" and not isinstance(question.get("choix"), list):
            question["type"] = "oui_non"
        if question.get("type") != "choix":
            question.pop("choix", None)
        final.append(question)

    return final[:MAX_QUESTIONS]


def encoder_reponses(questions: list, reponses: dict) -> dict:
    reponses = reponses or {}
    features = {feature: 0 for feature in FEATURES_QUESTIONS}

    for question in questions or []:
        feature_name = question.get("feature_name") or question.get("id")
        if not feature_name:
            continue
        if feature_name not in features:
            features[feature_name] = 0

        valeur = reponses.get(question.get("id"))
        if valeur is None:
            valeur = reponses.get(feature_name)

        if question.get("type") == "oui_non":
            features[feature_name] = _normaliser_bool(valeur)
        elif question.get("type") == "choix":
            features[feature_name] = _encoder_choix(question, valeur)
        else:
            features[feature_name] = _normaliser_bool(valeur)

    return features
