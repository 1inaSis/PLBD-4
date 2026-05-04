from __future__ import annotations

import json
import os
import requests
from typing import List, Dict
from nlp_extractor import normaliser_texte, extraire_features_nlp

# Toutes les features que le modÃ¨le ML attend pour les rÃ©ponses encodÃ©es.
FEATURES_QUESTIONS = [
    'q_craquement_trauma', 'q_appui_pied_trauma', 'q_gonflement_trauma', 'q_deformation_trauma', 
    'q_perte_conscience_trauma', 'q_saignement_trauma', 'q_mecanisme_trauma', 'q_douleur_irradiee_bras', 
    'q_douleur_repos_effort', 'q_duree_douleur_thoracique', 'q_sueurs_froides_cardiaque', 'q_antecedent_infarctus', 
    'q_medicaments_coeur', 'q_palpitations_cardiaque', 'q_duree_dyspnee', 'q_asthme_poumon', 'q_dyspnee_repos', 
    'q_crachats_sang', 'q_crise_similaire_respiratoire', 'q_fievre_associee_respiratoire', 'q_localisation_abdomen', 
    'q_debut_abdomen', 'q_vomissements_abdomen', 'q_fievre_abdomen', 'q_aggravation_marche', 'q_sang_selles', 
    'q_neuro_faiblesse', 'q_neuro_parole', 'q_neuro_debut_soudain', 'q_neuro_perte_conscience', 'q_neuro_antcedent', 
    'q_duree_fievre', 'q_frissons_fievre', 'q_voyage_fievre', 'q_medicaments_fievre', 'q_toux_fievre', 
    'q_entourage_malade', 'q_douleur_urinaire_fievre', 'q_douleur_flancs', 'q_urines_troubles', 'q_duree_urinaire', 
    'q_mal_de_gorge_fievre', 'q_dysphagie_orl', 'q_duree_orl', 'q_ganglions_orl', 'q_rougeur_peau', 
    'q_demangeaison_peau', 'q_allergie_peau', 'q_plaie_peau', 'q_traitement_diabete', 'q_mange_diabete', 
    'q_tremblements_diabete', 'q_duree_mal_diabete', 'q_grossesse_mois', 'q_saignement_vaginal', 
    'q_contractions_grossesse', 'q_bebe_bouge', 'q_hydratation_pediatrie', 'q_reveil_pediatrie', 
    'q_convulsions_pediatrie', 'q_duree_mal_pediatrie', 'q_hypertension_connue', 'q_traitement_tension', 
    'q_vision_hypertension', 'q_medicaments_generaux', 'q_allergies_generales', 'q_premiere_fois', 
    'q_geriatrie_chutes', 'q_geriatrie_medicaments', 'q_geriatrie_memor'
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


def generer_questions(constantes: dict, symptom_text: str, age: int, sex: int) -> list:
    '''
    GeÃ©nÃ¨re des questions dynamiques via Groq API (modele llama-3.3-70b-versatile).
    Renvoie une liste de questions structurees.
    '''
    # Essaie de trouver la clÃ© d'API dans l'environnement, sinon affiche un mock pour le developpement
    api_key = os.environ.get("GROQ_API_KEY", "")
    
    if not api_key:
        print("[AVERTISSEMENT] Pas de GROQ_API_KEY dÃ©finie.")
        # Questions de secours basiques piochÃ©es au hasard pour le frontend si l'API est absente
        return [
            {
                "id": "q1",
                "texte": "Avez-vous des antÃ©cÃ©dents mÃ©dicaux notables ?",
                "type": "oui_non",
                "feature_name": "q_medicaments_generaux"
            },
            {
                "id": "q2",
                "texte": "Depuis combien de temps le symptÃ´me a-t-il apparu ?",
                "type": "choix",
                "choix": ["Aujourd'hui", "Moins de 3 jours", "Plus d'une semaine"],
                "feature_name": "q_premiere_fois"
            }
        ]

    prompt_system = 'Tu es un(e) infirmier(e) d accueil et orientation (IAO) aux urgences.'
    
    # Liste des features existantes dans le modÃ¨le:
    valid_features = ", ".join(FEATURES_QUESTIONS[:15]) + "... (et d'autres)"

    prompt_user = f"Le patient a {age} ans, sexe {'Homme' if sex==1 else 'Femme'}.\n"
    prompt_user += f"Tension et Constantes : {json.dumps(constantes)}\n"
    prompt_user += f"Motif ou symptÃ´mes actuels : {symptom_text}\n\n"
    prompt_user += "GÃ©nÃ¨re exactement 4 questions mÃ©dicales d'urgence pertinentes et directes Ã  poser Ã  ce patient "
    prompt_user += "pour analyser l'urgence ou prÃ©ciser son symptÃ´me principal.\n"
    prompt_user += "Donne UNIQUEMENT un tableau JSON natif contenant des objets sous la forme:\n"
    prompt_user += "[\n  {\n"
    prompt_user += '    "id": "q_id_unique",\n'
    prompt_user += '    "texte": "La question naturelle posÃ©e",\n'
    prompt_user += '    "type": "choix" ou "oui_non" ou "texte_libre",\n'
    prompt_user += '    "choix": ["Option 1", "Option 2"] (si type="choix"),\n'
    prompt_user += '    "feature_name": "le_nom_de_la_feature"\n'
    prompt_user += "  }\n]\n"
    prompt_user += "Ne met RIEN DEVANT ou APRES le JSON. MÃªme pas de '`json' ou de texte."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": prompt_system},
            {"role": "user", "content": prompt_user}
        ],
        "temperature": 0.4
    }

    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=8)
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"].strip()
            # Nettoie les eventuels blocs markdown si l'IA en a gÃ©nÃ©rÃ©
            if content.startswith("`"):
                content = content.replace("`json", "").replace("`", "").strip()

            questions = json.loads(content)
            # ScuritÃ© : on s'assure que c'est une liste
            if isinstance(questions, list):
                return questions
        print(f"[Erreur API] {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[Exception API] Erreur rÃ©seau ou de parsing JSON : {e}")

    # Fallback si Ã§a a Ã©chouÃ©
    return [
        {
            "id": "q_secours",
            "texte": "DÃ©crivez plus en dÃ©tail vos symptÃ´mes:",
            "type": "texte_libre",
            "feature_name": "q_premiere_fois"
        }
    ]
