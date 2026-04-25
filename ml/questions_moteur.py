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
from typing import Dict, List, Tuple

from nlp_extractor import extraire_features_nlp, normaliser_texte


MIN_QUESTIONS = 4
MAX_QUESTIONS = 6


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
) -> dict:
    return {
        "id": question_id,
        "texte": texte,
        "type": type_question,
        "feature_name": feature_name,
        **({"choix": choix} if choix else {}),
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
                "Depuis combien de temps avez-vous du mal à respirer ?",
                "q_duree_dyspnee",
                "choix",
                ["Moins de 1 heure", "Depuis quelques heures", "Depuis 1 à 3 jours", "Depuis plus de 3 jours"],
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
                "Depuis combien de temps avez-vous de la fièvre ?",
                "q_duree_fievre",
                "choix",
                ["Moins de 24h", "1 à 3 jours", "Plus de 3 jours"],
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
                "La douleur est-elle à droite, à gauche ou au centre ?",
                "q_localisation_abdomen",
                "choix",
                ["Droite", "Gauche", "Centre", "Diffuse"],
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
                "Depuis combien de temps cela a commencé ?",
                "q_duree_symptomes",
                "choix",
                ["Moins de 24h", "1 à 3 jours", "Plus de 3 jours"],
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
        "choix",
        ["Moins de 24h", "1 à 3 jours", "Plus de 3 jours"],
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
        candidats.append((68, deepcopy(_question("q_duree_symptomes", "Depuis combien de temps les symptômes ont-ils débuté ?", "q_duree_symptomes", "choix", ["Moins de 24h", "1 à 3 jours", "Plus de 3 jours"])) ))


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

    signature = _signature_patient(constantes, symptom_text, age, sex)
    nb_voulu = MIN_QUESTIONS + (signature % (MAX_QUESTIONS - MIN_QUESTIONS + 1))
    selection = _selection_diversifiee(questions_candidats, signature, nb_voulu)
    vus = {q["feature_name"] for q in selection}

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
        else:
            features[feature_name] = _normaliser_bool(valeur)

    return features
