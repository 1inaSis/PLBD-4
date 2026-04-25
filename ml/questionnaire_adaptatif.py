"""
questionnaire_adaptatif.py — Questions dynamiques basées sur symptômes + constantes
Projet HealthGate | Centrale Casablanca | PLBD 4 | 2025-2026

Exemple : Si patient a fièvre (T>38) + toux → poser questions sur dyspnée, contact
         Si patient a douleur thoracique → questions EKG, antécédents cardiaques
         Si patient a SpO2 faible → questions sur asthme, respiration
"""

# ─────────────────────────────────────────────────────────────────────────────
# Banque de questions adaptatives
# ─────────────────────────────────────────────────────────────────────────────

QUESTIONS_ADAPTATIF = {
    # ── Fièvre (T >= 38°C) ──
    "fievre_presente": {
        "condition": lambda constantes, features_nlp: (
            constantes.get("temperature", 37) >= 38.0 and 
            features_nlp.get("nlp_fever", 0) == 1
        ),
        "questions": [
            {
                "id": "fievre_duree",
                "texte": "Depuis combien de jours avez-vous de la fièvre?",
                "type": "nombre",
                "options": ["< 24h", "1-3 jours", "3-7 jours", "> 1 semaine"],
                "score_impact": {"< 24h": 0, "1-3 jours": 1, "3-7 jours": 2, "> 1 semaine": 3},
            },
            {
                "id": "fievre_evolution",
                "texte": "La fièvre augmente ou diminue?",
                "type": "choix",
                "options": ["Augmente progressivement", "Stable", "Diminue", "Fluctuante"],
                "score_impact": {"Augmente progressivement": 2, "Stable": 0, "Diminue": -1, "Fluctuante": 1},
            },
            {
                "id": "toux_symptome",
                "texte": "Avez-vous une toux?",
                "type": "oui_non",
                "score_impact": {"Oui": 2, "Non": 0},
            },
        ],
    },

    # ── Douleur thoracique (chest_pain detected) ──
    "douleur_thoracique": {
        "condition": lambda constantes, features_nlp: (
            features_nlp.get("nlp_chest_pain", 0) == 1
        ),
        "questions": [
            {
                "id": "douleur_type",
                "texte": "Type de douleur à la poitrine?",
                "type": "choix_simple",
                "options": ["Aiguë / piqûre", "Brûlure", "Oppression", "Tiraillement"],
                "score_impact": {"Aiguë / piqûre": 1, "Brûlure": 2, "Oppression": 3, "Tiraillement": 1},
            },
            {
                "id": "douleur_rayonne",
                "texte": "La douleur irradie vers le bras, la mâchoire ou l'épaule?",
                "type": "oui_non",
                "score_impact": {"Oui": 3, "Non": 0},  # ← IMPORTANT pour infarctus
            },
            {
                "id": "douleur_effort",
                "texte": "Douleur déclenchée par l'effort?",
                "type": "oui_non",
                "score_impact": {"Oui": 2, "Non": 0},  # ← Angine de poitrine
            },
            {
                "id": "douleur_essoufflement",
                "texte": "Vous vous sentez essoufflé?",
                "type": "oui_non",
                "score_impact": {"Oui": 2, "Non": 0},
            },
        ],
    },

    # ── SpO2 faible (< 94%) ──
    "hypo_oxygenie": {
        "condition": lambda constantes, features_nlp: (
            constantes.get("spo2", 98) < 94
        ),
        "questions": [
            {
                "id": "dyspnee_degre",
                "texte": "Degré d'essoufflement? (0=aucun, 10=maximum)",
                "type": "curseur",
                "min": 0,
                "max": 10,
                "score_impact": lambda val: min(val, 5),  # Cap à 5
            },
            {
                "id": "antecedent_asthme",
                "texte": "Antécédent d'asthme ou BPCO?",
                "type": "oui_non",
                "score_impact": {"Oui": 2, "Non": 0},
            },
            {
                "id": "wheezing",
                "texte": "Vous entendez des sifflements en respirant?",
                "type": "oui_non",
                "score_impact": {"Oui": 2, "Non": 0},
            },
        ],
    },

    # ── Fréquence cardiaque élevée (> 100 bpm) ──
    "tachycardie": {
        "condition": lambda constantes, features_nlp: (
            constantes.get("heart_rate", 75) > 100
        ),
        "questions": [
            {
                "id": "fc_palpitatif",
                "texte": "Vous ressentez des palpitations?",
                "type": "oui_non",
                "score_impact": {"Oui": 2, "Non": 1},
            },
            {
                "id": "fc_regulier",
                "texte": "Le cœur bat régulièrement?",
                "type": "oui_non",
                "score_impact": {"Oui": 0, "Non": 2},  # ← Arythmie
            },
            {
                "id": "fc_anxiete",
                "texte": "Êtes-vous stressé ou anxieux en ce moment?",
                "type": "oui_non",
                "score_impact": {"Oui": 1, "Non": 0},
            },
        ],
    },

    # ── Tension artérielle haute (> 140/90) ──
    "hypertension": {
        "condition": lambda constantes, features_nlp: (
            constantes.get("bp_systolic", 120) > 140 or 
            constantes.get("bp_diastolic", 80) > 90
        ),
        "questions": [
            {
                "id": "hypertension_connue",
                "texte": "Avez-vous une hypertension connue?",
                "type": "oui_non",
                "score_impact": {"Oui": 0, "Non": 1},  # ← Nouvelle HTN plus grave
            },
            {
                "id": "maux_tete",
                "texte": "Vous avez des maux de tête?",
                "type": "oui_non",
                "score_impact": {"Oui": 1, "Non": 0},
            },
            {
                "id": "vision_trouble",
                "texte": "Vision trouble ou points lumineux?",
                "type": "oui_non",
                "score_impact": {"Oui": 2, "Non": 0},  # ← URGENT — crise hypertensive
            },
        ],
    },

    # ── Douleur abdominale ──
    "douleur_abdominale": {
        "condition": lambda constantes, features_nlp: (
            features_nlp.get("nlp_abdominal", 0) == 1
        ),
        "questions": [
            {
                "id": "abdomen_localisation",
                "texte": "Localisation de la douleur?",
                "type": "choix_simple",
                "options": ["Épigastre", "Flanc D", "Flanc G", "Hypogastre", "Diffuse"],
                "score_impact": {
                    "Épigastre": 1, "Flanc D": 2, "Flanc G": 1, 
                    "Hypogastre": 1, "Diffuse": 3
                },  # ← Diffuse = grave
            },
            {
                "id": "abdomen_garde",
                "texte": "Abdomen rigide ou très douloureux au toucher?",
                "type": "oui_non",
                "score_impact": {"Oui": 3, "Non": 0},  # ← URGENT
            },
            {
                "id": "nausee_vomissement",
                "texte": "Nausées ou vomissements?",
                "type": "oui_non",
                "score_impact": {"Oui": 1, "Non": 0},
            },
        ],
    },

    # ── Traumatisme ──
    "traumatisme": {
        "condition": lambda constantes, features_nlp: (
            features_nlp.get("nlp_trauma", 0) == 1
        ),
        "questions": [
            {
                "id": "trauma_perte_conscience",
                "texte": "Perte de conscience lors du trauma?",
                "type": "oui_non",
                "score_impact": {"Oui": 3, "Non": 0},  # ← TRÈS URGENT
            },
            {
                "id": "trauma_site",
                "texte": "Où avez-vous mal?",
                "type": "choix_simple",
                "options": ["Tête", "Thorax", "Abdomen", "Membre"],
                "score_impact": {"Tête": 2, "Thorax": 3, "Abdomen": 3, "Membre": 1},
            },
            {
                "id": "trauma_saignement",
                "texte": "Saignement abondant?",
                "type": "oui_non",
                "score_impact": {"Oui": 2, "Non": 0},
            },
        ],
    },

    # ── Symptômes neurologiques ──
    "symptomes_neuro": {
        "condition": lambda constantes, features_nlp: (
            features_nlp.get("nlp_neuro", 0) == 1
        ),
        "questions": [
            {
                "id": "neuro_vertige",
                "texte": "Vertige/sensation de tournoyement?",
                "type": "oui_non",
                "score_impact": {"Oui": 1, "Non": 0},
            },
            {
                "id": "neuro_faiblesse",
                "texte": "Faiblesse ou paralysie d'un côté du corps?",
                "type": "oui_non",
                "score_impact": {"Oui": 3, "Non": 0},  # ← Possible AVC
            },
            {
                "id": "neuro_trouble_parole",
                "texte": "Trouble de la parole, difficulté à trouver ses mots?",
                "type": "oui_non",
                "score_impact": {"Oui": 3, "Non": 0},  # ← Possible AVC
            },
            {
                "id": "neuro_confusion",
                "texte": "Confusion ou désorientation?",
                "type": "oui_non",
                "score_impact": {"Oui": 2, "Non": 0},
            },
        ],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Fonction principale
# ─────────────────────────────────────────────────────────────────────────────

def generer_questions_adaptatif(constantes: dict, features_nlp: dict) -> dict:
    """
    Génère un ensemble de questions adaptatives basées sur constantes + NLP.
    
    Params
    ------
    constantes : dict avec temperature, spo2, heart_rate, bp_systolic, bp_diastolic
    features_nlp : dict avec nlp_chest_pain, nlp_fever, etc.
    
    Returns
    -------
    dict : {
        "questions_proposees": [...],  # Liste de questions à poser
        "urgence_score": int,          # Score d'urgence supplémentaire
        "scenarios_matches": [...]     # Scénarios détectés (ex: "fievre_presente")
    }
    """
    questions_proposees = []
    urgence_bonus = 0
    scenarios_matched = []

    # Parcourir tous les scénarios
    for scenario_name, scenario_data in QUESTIONS_ADAPTATIF.items():
        condition_func = scenario_data["condition"]

        # Vérifier si le scénario s'applique
        if condition_func(constantes, features_nlp):
            scenarios_matched.append(scenario_name)

            # Ajouter toutes les questions de ce scénario
            for question in scenario_data["questions"]:
                questions_proposees.append({
                    "scenario": scenario_name,
                    **question,
                })

                # Bonus d'urgence initial par question
                urgence_bonus += 1

    return {
        "questions_proposees": questions_proposees,
        "urgence_bonus": urgence_bonus,
        "scenarios_matched": scenarios_matched,
        "nb_questions": len(questions_proposees),
    }


def calculer_score_adaptatif(reponses: dict) -> dict:
    """
    Calcule un score d'urgence supplémentaire basé sur les réponses adaptatives.
    
    Params
    ------
    reponses : dict avec {question_id: reponse_valeur, ...}
    
    Returns
    -------
    dict : {
        "score_total": int,
        "facteurs_alarmants": [...],  # Questions qui augmentent le score
        "esi_delta": int,             # Modification ESI suggérée
    }
    """
    score = 0
    facteurs_alarmants = []

    # Parcourir les réponses
    for question_id, reponse in reponses.items():
        # Chercher la question correspondante
        for scenario in QUESTIONS_ADAPTATIF.values():
            for q in scenario["questions"]:
                if q["id"] == question_id:
                    impact_func = q.get("score_impact")
                    
                    if isinstance(impact_func, dict):
                        # Impact statique (dictionnaire)
                        points = impact_func.get(reponse, 0)
                    elif callable(impact_func):
                        # Impact dynamique (fonction)
                        points = impact_func(reponse)
                    else:
                        points = 0

                    if points > 0:
                        score += points
                        facteurs_alarmants.append({
                            "question": q.get("texte"),
                            "reponse": reponse,
                            "points": points,
                        })
                    break

    return {
        "score_total": score,
        "facteurs_alarmants": facteurs_alarmants,
        "esi_delta": min(score // 3, 2),  # Décalage ESI max +2
    }
