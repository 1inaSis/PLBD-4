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

import csv
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import re
from typing import Dict, List, Tuple

from nlp_extractor import extraire_features_nlp, normaliser_texte


MIN_QUESTIONS = 4
MAX_QUESTIONS = 6
BASE_DIR = Path(__file__).resolve().parent
QUESTION_BANK_PATH = BASE_DIR / "data" / "questions_50000.csv"
_EXTERNAL_QUESTION_BANK: List[dict] | None = None


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

    if not QUESTION_BANK_PATH.exists():
        _EXTERNAL_QUESTION_BANK = []
        return _EXTERNAL_QUESTION_BANK

    banque: List[dict] = []
    try:
        with QUESTION_BANK_PATH.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                feature_name = str(row.get("feature_name", "")).strip()
                if feature_name not in FEATURES_QUESTIONS:
                    continue

                qtype = str(row.get("type", "oui_non")).strip() or "oui_non"
                if qtype not in {"oui_non", "choix", "texte_libre"}:
                    qtype = "oui_non"

                choix = []
                choix_raw = row.get("choix_json", "")
                if choix_raw:
                    try:
                        parsed = json.loads(choix_raw)
                        if isinstance(parsed, list):
                            choix = [str(v) for v in parsed]
                    except Exception:
                        choix = []

                banque.append(
                    {
                        "id": str(row.get("question_uid", "")).strip() or f"ext_{len(banque)+1}",
                        "scenario": str(row.get("scenario", "general")).strip() or "general",
                        "feature_name": feature_name,
                        "type": qtype,
                        "texte": str(row.get("texte", "")).strip(),
                        "choix": choix,
                        "placeholder": str(row.get("placeholder", "")).strip(),
                        "poids": int(str(row.get("poids", "60") or "60")),
                    }
                )
    except Exception:
        banque = []

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


def _selection_diversifiee(candidats: List[Tuple[int, dict]], signature: int, nb_voulu: int) -> list:
    """Sélectionne des questions en conservant la pertinence tout en variant les combinaisons."""
    if not candidats:
        return []

    # Déduplication préalable par feature en conservant le meilleur score.
    meilleurs = {}
    for score, question in candidats:
        feature = question["feature_name"]
        precedent = meilleurs.get(feature)
        if precedent is None or score > precedent[0]:
            meilleurs[feature] = (score, question)

    base = sorted(meilleurs.values(), key=lambda item: item[0], reverse=True)
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

    nb_voulu = MIN_QUESTIONS + (signature % (MAX_QUESTIONS - MIN_QUESTIONS + 1))
    selection = _selection_diversifiee(questions_candidats, signature, nb_voulu)
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
