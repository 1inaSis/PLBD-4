from __future__ import annotations

import json
import os
import requests
from dotenv import load_dotenv
from typing import List, Dict
from nlp_extractor import normaliser_texte, extraire_features_nlp

# Chargement automatique des cles API depuis le fichier .env
load_dotenv()

# Toutes les features que le modèle ML attend pour les réponses encodées.
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


# ── Labels français des zones du pictogramme ─────────────────────────────────
_ZONES_LABELS_FR = {
    "tete":          "Tête / Visage",
    "cou":           "Cou / Gorge",
    "poitrine":      "Poitrine / Coeur",
    "ventre":        "Ventre / Abdomen",
    "bas_ventre":    "Bas-ventre",
    "epaule_gauche": "Epaule gauche",
    "epaule_droite": "Epaule droite",
    "bras_gauche":   "Bras gauche",
    "bras_droit":    "Bras droit",
    "hanche_gauche": "Hanche / Dos gauche",
    "hanche_droite": "Hanche / Dos droit",
    "jambe_gauche":  "Jambe gauche",
    "jambe_droite":  "Jambe droite",
    "pied_gauche":   "Pied / Cheville gauche",
    "pied_droit":    "Pied / Cheville droit",
}

# ── Labels français des features NLP détectées ───────────────────────────────
_NLP_LABELS_FR = {
    "nlp_chest_pain":            "douleur thoracique",
    "nlp_dyspnea":               "dyspnee / essoufflement",
    "nlp_loss_of_consciousness": "perte de conscience",
    "nlp_severe_bleeding":       "saignement important",
    "nlp_neurological":          "symptomes neurologiques",
    "nlp_abdominal_pain":        "douleur abdominale",
    "nlp_fever":                 "fievre",
    "nlp_trauma":                "traumatisme",
    "nlp_urgence_critique":      "urgence critique",
}


def _gravite_constante(cle: str, valeur) -> str:
    """Retourne un libelle de gravite (NORMAL / ALERTE / CRITIQUE) pour une constante."""
    if valeur is None:
        return "non mesuree"
    v = float(valeur)
    if cle == "temperature":
        if v >= 41.0:            return "HYPERPYREXIE CRITIQUE"
        if v >= 39.0:            return "FIEVRE ELEVEE ALERTE"
        if v >= 37.5:            return "LEGERE FIEVRE"
        if v < 36.0:             return "HYPOTHERMIE ALERTE"
        return "NORMAL"
    if cle == "spo2":
        if v < 90:               return "CRITIQUE"
        if v < 93:               return "ALERTE"
        if v < 95:               return "LEGEREMENT BAS"
        return "NORMAL"
    if cle == "heart_rate":
        if v < 40 or v > 150:   return "CRITIQUE"
        if v < 50 or v > 130:   return "ALERTE"
        if v < 60 or v > 100:   return "LEGEREMENT ANORMAL"
        return "NORMAL"
    if cle == "bp_systolic":
        if v > 190 or v < 70:   return "CRITIQUE"
        if v > 160 or v < 80:   return "ALERTE"
        if v > 140 or v < 90:   return "LEGEREMENT ANORMAL"
        return "NORMAL"
    return ""


def generer_questions(
    constantes: dict,
    symptom_text: str,
    age: int,
    sex: int,
    zones_corps: list = None,
    features_nlp: dict = None,
) -> list:
    api_key = os.environ.get("GROQ_API_KEY", "")

    if not api_key:
        print("[AVERTISSEMENT] Pas de GROQ_API_KEY definie.")
        return [{"id": "q1", "texte": "Avez-vous des antecedents ?", "type": "oui_non", "feature_name": "q_medicaments_generaux"}]

    prompt_system = (
        "Tu es un infirmier d'accueil urgentiste (IAO) experimente aux urgences. "
        "Tu dois poser des questions CIBLEES sur la situation specifique du patient, "
        "pas des questions generiques. Chaque question doit potentiellement modifier le score ESI."
    )

    sexe_str = "Homme" if sex == 1 else "Femme"
    prompt_user = f"PATIENT : {age} ans, {sexe_str}\n\n"

    # Constantes vitales avec niveaux de gravite
    prompt_user += "CONSTANTES VITALES :\n"
    for cle, label, unite in [
        ("temperature", "Temperature",        "degC"),
        ("spo2",        "SpO2",               "%"),
        ("heart_rate",  "Frequence cardiaque", "bpm"),
        ("bp_systolic", "Tension systolique",  "mmHg"),
    ]:
        val = constantes.get(cle)
        if val is not None:
            niv = _gravite_constante(cle, val)
            prompt_user += f"  - {label} : {val} {unite} -> {niv}\n"

    # Zones douloureuses indiquees sur le pictogramme
    if zones_corps:
        zones_fr = [_ZONES_LABELS_FR.get(z, z) for z in zones_corps]
        prompt_user += f"\nZONES DOULOUREUSES INDIQUEES : {', '.join(zones_fr)}\n"
    else:
        prompt_user += "\nZONES DOULOUREUSES : non precisees\n"

    # Description textuelle
    prompt_user += f"\nDESCRIPTION DU PATIENT : << {symptom_text} >>\n"

    # Features NLP deja identifiees - ne pas reposer ces questions
    detectees = []
    if features_nlp:
        detectees = [
            _NLP_LABELS_FR[k]
            for k, v in features_nlp.items()
            if v and v > 0 and k in _NLP_LABELS_FR
        ]
    if detectees:
        prompt_user += f"\nDEJA IDENTIFIE PAR ANALYSE AUTOMATIQUE : {', '.join(detectees)}\n"
        prompt_user += "-> NE PAS reposer de questions sur ces elements, ils sont deja connus.\n"

    prompt_user += "\n"
    prompt_user += "Genere exactement 4 questions medicales CIBLEES pour affiner le triage ESI.\n"
    prompt_user += "REGLES IMPERATIVES :\n"
    prompt_user += "  1. Questions directement liees aux zones douloureuses et constantes ci-dessus.\n"
    prompt_user += "  2. Ne pas commencer par 'Avez-vous des antecedents ?' de facon generique.\n"
    prompt_user += "  3. Priorite aux questions qui peuvent faire passer l'ESI de 3 a 2 (aggravation, duree, signes associes).\n"
    prompt_user += "  4. Varier les types : 'oui_non', 'choix', 'texte_libre'.\n"
    prompt_user += "  5. Pour 'feature_name', copier-coller EXACTEMENT une valeur de cette liste :\n"
    prompt_user += str(FEATURES_QUESTIONS) + "\n\n"
    prompt_user += "Reponds UNIQUEMENT avec un tableau JSON valide, sans texte avant ni apres :\n"
    prompt_user += (
        '[\n'
        '  {\n'
        '    "id": "q_1",\n'
        '    "texte": "La question posee au patient",\n'
        '    "type": "oui_non",\n'
        '    "choix": ["Option A", "Option B"],\n'
        '    "feature_name": "q_feature_exacte_de_la_liste"\n'
        '  }\n'
        ']\n'
    )

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
        "temperature": 0.85
    }

    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=8)
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"].strip()
            if "```" in content:
                content = content.split('`json')[-1].split('`')[0].strip() if '`json' in content else content.split('`')[-1].split('`')[0].strip()
            questions = json.loads(content)
            if isinstance(questions, list):
                return questions
        else:
            print(f"[Erreur API] {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[Exception API] Erreur reseau ou de parsing JSON : {e}")

    return [{"id": "q_secours", "texte": "Que ressentez-vous?", "type": "texte_libre", "feature_name": "q_premiere_fois"}]


def generer_question_suivante(
    constantes: dict,
    symptom_text: str,
    age: int,
    sex: int,
    zones_corps: list,
    features_nlp: dict,
    reponses_precedentes: List[Dict],
    num_question: int,
) -> dict:
    """
    Génère UNE question adaptative en tenant compte de toutes les réponses précédentes.
    Retourne {"continuer": True, "question": ..., "type": ..., "choix": [...], "feature_name": ...}
    ou       {"continuer": False} si Groq estime avoir assez d'informations (après min 3 questions).
    """
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return {"continuer": False}

    prompt_system = (
        "Tu es un infirmier d'accueil urgentiste (IAO) expert en triage ESI. "
        "Tu poses des questions médicales CIBLÉES une par une, en t'adaptant aux réponses précédentes. "
        "Chaque question doit apporter de nouvelles informations pour affiner le score ESI. "
        "Tu évites de répéter des informations déjà connues."
    )

    sexe_str = "Homme" if sex == 1 else "Femme"
    prompt_user = f"PATIENT : {age} ans, {sexe_str}\n\n"

    prompt_user += "CONSTANTES VITALES :\n"
    for cle, label, unite in [
        ("temperature", "Température", "°C"),
        ("spo2",        "SpO2",        "%"),
        ("heart_rate",  "Fréquence cardiaque", "bpm"),
        ("bp_systolic", "Tension systolique",  "mmHg"),
    ]:
        val = constantes.get(cle)
        if val is not None:
            niv = _gravite_constante(cle, val)
            prompt_user += f"  - {label} : {val} {unite} → {niv}\n"

    if zones_corps:
        zones_fr = [_ZONES_LABELS_FR.get(z, z) for z in zones_corps]
        prompt_user += f"\nZONES DOULOUREUSES : {', '.join(zones_fr)}\n"

    prompt_user += f"\nDESCRIPTION : « {symptom_text} »\n"

    detectees = [
        _NLP_LABELS_FR[k]
        for k, v in (features_nlp or {}).items()
        if v and v > 0 and k in _NLP_LABELS_FR
    ]
    if detectees:
        prompt_user += f"\nDÉJÀ IDENTIFIÉ PAR NLP : {', '.join(detectees)}\n"

    if reponses_precedentes:
        prompt_user += "\nRÉPONSES PRÉCÉDENTES :\n"
        for i, r in enumerate(reponses_precedentes, 1):
            prompt_user += f"  Q{i} : {r.get('question', '')} → {r.get('reponse', '')}\n"

    features_utilisees = [r.get("feature_name") for r in reponses_precedentes if r.get("feature_name")]

    prompt_user += f"\n--- INSTRUCTION ---\n"
    prompt_user += f"C'est la question numéro {num_question} sur 5 maximum.\n"

    if num_question >= 3:
        prompt_user += (
            "Si tu as déjà suffisamment d'informations pour un triage ESI fiable, réponds :\n"
            '{"continuer": false}\n\n'
            "Sinon, génère une nouvelle question :\n"
        )
    else:
        prompt_user += "Tu DOIS poser une question (minimum 3 obligatoires).\n"

    if features_utilisees:
        prompt_user += f"Features déjà utilisées (NE PAS réutiliser) : {features_utilisees}\n"

    prompt_user += (
        "\nRéponds UNIQUEMENT avec un JSON valide (sans texte avant ni après) :\n"
        "{\n"
        '  "question": "La question posée au patient",\n'
        '  "type": "oui_non",\n'
        '  "choix": ["Option A", "Option B"],\n'
        '  "feature_name": "q_feature_exacte_de_la_liste",\n'
        '  "continuer": true\n'
        "}\n\n"
        f"feature_name DOIT être une valeur exacte de cette liste :\n{FEATURES_QUESTIONS}\n"
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": prompt_system},
            {"role": "user",   "content": prompt_user},
        ],
        "temperature": 0.7,
    }

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers, json=payload, timeout=10,
        )
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"].strip()
            if "```" in content:
                content = (
                    content.split("```json")[1].split("```")[0].strip()
                    if "```json" in content
                    else content.split("```")[1].split("```")[0].strip()
                )
            result = json.loads(content)
            if isinstance(result, dict):
                return result
        else:
            print(f"[Erreur API suivante] {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[Exception API] generer_question_suivante : {e}")

    return {"continuer": False}
