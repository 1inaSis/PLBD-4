"""
question_bank_generator.py - Genere une banque externe de questions medicales.

Usage:
  py question_bank_generator.py --count 50000 --out data/questions_50000.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

# Mappage scenario principal par feature.
FEATURE_SCENARIO = {
    "q_douleur_irradiee_bras": "douleur_thoracique",
    "q_antecedent_infarctus": "douleur_thoracique",
    "q_medicaments_coeur": "douleur_thoracique",
    "q_douleur_repos_effort": "douleur_thoracique",
    "q_duree_dyspnee": "dyspnee",
    "q_dyspnee_aggrave_effort": "dyspnee",
    "q_antecedent_asthme": "dyspnee",
    "q_duree_fievre": "fievre",
    "q_frissons_sueurs": "fievre",
    "q_voyage_paludisme": "fievre",
    "q_hypertension_connue": "hypertension",
    "q_medicaments_tension": "hypertension",
    "q_maux_tete_vision": "hypertension",
    "q_a_mange_aujourdhui": "glycemie",
    "q_insuline_pris": "glycemie",
    "q_localisation_abdomen": "abdomen",
    "q_fievre_associee_abdomen": "abdomen",
    "q_vomissements_abdomen": "abdomen",
    "q_trauma_perte_conscience": "trauma",
    "q_trauma_saignement": "trauma",
    "q_trauma_zone": "trauma",
    "q_neuro_faiblesse": "neuro",
    "q_neuro_parole": "neuro",
    "q_neuro_confusion": "neuro",
    "q_pediatrie_hydratation": "pediatrie",
    "q_grossesse_possible": "grossesse",
    "q_antecedent_symptome": "general",
    "q_aggravation_effort": "general",
    "q_prise_medicament": "general",
    "q_duree_symptomes": "general",
}

FEATURE_TYPE = {
    "q_douleur_repos_effort": ("choix", ["Au repos", "A l'effort", "Les deux", "Je ne sais pas"], ""),
    "q_duree_dyspnee": ("texte_libre", [], "Exemple: depuis 2 heures, depuis hier"),
    "q_duree_fievre": ("texte_libre", [], "Exemple: depuis ce matin, depuis 2 jours"),
    "q_localisation_abdomen": ("texte_libre", [], "Exemple: en bas a droite, au centre"),
    "q_trauma_zone": ("choix", ["Tete", "Poitrine", "Ventre", "Bras ou jambe"], ""),
    "q_duree_symptomes": ("texte_libre", [], "Exemple: depuis 3 jours"),
}

BASE_QUESTIONS = {
    "q_douleur_irradiee_bras": [
        "La douleur va-t-elle vers le bras gauche ou la machoire ?",
        "La douleur thoracique irradie-t-elle vers le bras ou la machoire ?",
    ],
    "q_antecedent_infarctus": [
        "Avez-vous deja fait un infarctus ?",
        "Avez-vous un antecedent cardiaque severe ?",
    ],
    "q_medicaments_coeur": [
        "Prenez-vous un traitement pour le coeur ?",
        "Avez-vous un medicament cardiaque habituel ?",
    ],
    "q_douleur_repos_effort": [
        "La douleur est-elle apparue au repos ou pendant un effort ?",
        "Dans quel contexte la douleur a-t-elle commence (repos/effort) ?",
    ],
    "q_duree_dyspnee": [
        "Depuis quand la gene respiratoire est-elle presente ?",
        "Pouvez-vous preciser la duree de l'essoufflement ?",
    ],
    "q_dyspnee_aggrave_effort": [
        "La respiration devient-elle pire a l'effort ?",
        "La dyspnee augmente-t-elle quand vous bougez ?",
    ],
    "q_antecedent_asthme": [
        "Avez-vous de l'asthme ou une maladie pulmonaire ?",
        "Avez-vous un antecedent respiratoire connu ?",
    ],
    "q_duree_fievre": [
        "Depuis quand avez-vous de la fievre ?",
        "Depuis combien de temps la fievre est-elle presente ?",
    ],
    "q_frissons_sueurs": [
        "Avez-vous des frissons ou des sueurs nocturnes ?",
        "Ressentez-vous frissons et sueurs la nuit ?",
    ],
    "q_voyage_paludisme": [
        "Avez-vous voyage en zone de paludisme recemment ?",
        "Retournez-vous d'une zone a risque de paludisme ?",
    ],
    "q_hypertension_connue": [
        "Avez-vous une hypertension connue ?",
        "Etes-vous suivi pour tension arterielle elevee ?",
    ],
    "q_medicaments_tension": [
        "Prenez-vous un traitement antihypertenseur ?",
        "Avez-vous un medicament pour la tension ?",
    ],
    "q_maux_tete_vision": [
        "Avez-vous mal a la tete ou des troubles de la vision ?",
        "Ressentez-vous cephalees et vision floue ?",
    ],
    "q_a_mange_aujourdhui": [
        "Avez-vous mange aujourd'hui ?",
        "Avez-vous pris un repas recent ?",
    ],
    "q_insuline_pris": [
        "Avez-vous pris votre insuline/traitement diabetique ?",
        "Traitement du diabete pris aujourd'hui ?",
    ],
    "q_localisation_abdomen": [
        "Ou se situe surtout la douleur abdominale ?",
        "Precisez la zone principale de douleur abdominale.",
    ],
    "q_fievre_associee_abdomen": [
        "Avez-vous de la fievre avec la douleur abdominale ?",
        "La douleur du ventre est-elle associee a de la fievre ?",
    ],
    "q_vomissements_abdomen": [
        "Y a-t-il des nausees ou vomissements associes ?",
        "Avez-vous vomi avec cette douleur abdominale ?",
    ],
    "q_trauma_perte_conscience": [
        "Avez-vous perdu connaissance lors du traumatisme ?",
        "Y a-t-il eu une perte de connaissance au moment du choc ?",
    ],
    "q_trauma_saignement": [
        "Le saignement est-il abondant ?",
        "Avez-vous un saignement important apres le traumatisme ?",
    ],
    "q_trauma_zone": [
        "Quelle zone est la plus douloureuse apres le choc ?",
        "Ou avez-vous le plus mal depuis le traumatisme ?",
    ],
    "q_neuro_faiblesse": [
        "Avez-vous une faiblesse d'un cote du corps ?",
        "Ressentez-vous une paralysie ou faiblesse laterale ?",
    ],
    "q_neuro_parole": [
        "Avez-vous des difficultes a parler ?",
        "Avez-vous du mal a trouver vos mots ?",
    ],
    "q_neuro_confusion": [
        "Etes-vous confus ou desoriente ?",
        "Avez-vous un etat confusionnel ?",
    ],
    "q_pediatrie_hydratation": [
        "L'enfant boit-il et urine-t-il normalement ?",
        "L'hydratation de l'enfant vous semble-t-elle normale ?",
    ],
    "q_grossesse_possible": [
        "Existe-t-il une possibilite de grossesse ?",
        "Etes-vous enceinte ou possiblement enceinte ?",
    ],
    "q_antecedent_symptome": [
        "Avez-vous deja eu ces symptomes auparavant ?",
        "Ces symptomes sont-ils deja survenus dans le passe ?",
    ],
    "q_aggravation_effort": [
        "Les symptomes s'aggravent-ils a l'effort ?",
        "Votre etat est-il pire lorsque vous bougez ?",
    ],
    "q_prise_medicament": [
        "Avez-vous pris un medicament avant de venir ?",
        "Quel traitement avez-vous pris avant l'arrivee ?",
    ],
    "q_duree_symptomes": [
        "Depuis quand les symptomes ont-ils commence ?",
        "Precisez la duree globale des symptomes.",
    ],
}

STARTERS = [
    "Pour mieux evaluer votre situation,",
    "Afin d'affiner le triage,",
    "Pour adapter la priorite,",
    "Pour orienter rapidement la prise en charge,",
]

ENDERS = [
    "",
    " Merci de repondre precisement.",
    " Votre reponse aide la priorisation.",
    " C'est important pour la securite clinique.",
]


def build_question_text(rng: random.Random, feature_name: str) -> str:
    base = rng.choice(BASE_QUESTIONS[feature_name])
    starter = rng.choice(STARTERS)
    ender = rng.choice(ENDERS)
    return f"{starter} {base}{ender}".strip()

import requests

def build_question_text_ai(feature_name: str, scenario: str) -> str:
    """
    Exemple de l'approche API: L'IA génère la question au lieu de la piocher au hasard.
    ⚠️ Attention: Sur 50 000 lignes, cela fera 50 000 appels payants et lents.
    """
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer sk-VOTRE_CLE_API"
    }
    
    # 1. On donne du contexte médical à l'IA
    system_prompt = "Tu es un médecin urgentiste. Rédige une question courte et professionnelle pour un patient."
    user_prompt = f"Génère une question pour vérifier le symptôme/facteur '{feature_name}' dans le contexte d'un(e) {scenario}."

    data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.4
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=5)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content'].strip()
        else:
            return f"Question par défaut pour {feature_name} (Erreur API)"
    except Exception as e:
        return f"Question par défaut pour {feature_name} (Erreur réseau)"


def build_rows(count: int, seed: int = 42):
    rng = random.Random(seed)
    features = list(FEATURE_SCENARIO.keys())
    rows = []

    for i in range(count):
        feature = features[i % len(features)]
        scenario = FEATURE_SCENARIO[feature]
        qtype, choices, placeholder = FEATURE_TYPE.get(feature, ("oui_non", [], ""))

        # Variation contextuelle supplementaire
        texte = build_question_text(rng, feature)
        if rng.random() < 0.2 and scenario != "general":
            texte = f"[{scenario.upper()}] {texte}"

        rows.append(
            {
                "question_uid": f"Q{(i+1):06d}",
                "scenario": scenario,
                "feature_name": feature,
                "type": qtype,
                "texte": texte,
                "choix_json": json.dumps(choices, ensure_ascii=False) if choices else "",
                "placeholder": placeholder,
                "poids": 55 + rng.randint(0, 45),
            }
        )

    return rows


def write_csv(rows, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["question_uid", "scenario", "feature_name", "type", "texte", "choix_json", "placeholder", "poids"]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Genere une banque de questions medicales contextualisees")
    parser.add_argument("--count", type=int, default=50000, help="Nombre de questions a generer")
    parser.add_argument("--seed", type=int, default=42, help="Seed aleatoire")
    parser.add_argument("--out", type=str, default="data/questions_50000.csv", help="Chemin de sortie CSV")
    args = parser.parse_args()

    out_path = Path(__file__).resolve().parent / args.out
    rows = build_rows(args.count, args.seed)
    write_csv(rows, out_path)
    print(f"[OK] Banque generee: {len(rows)} questions -> {out_path}")


if __name__ == "__main__":
    main()
