"""
Medical Data Generator - ESI Balanced & Physiologically Correlated
Author: Expert Data Scientist
"""
import pandas as pd
import numpy as np
import random
from pathlib import Path
from tqdm import tqdm

from questions_moteur import FEATURES_QUESTIONS

# Set reproducible seeds
np.random.seed(42)
random.seed(42)

NUM_PATIENTS = 50_000
OUTPUT_PATH = Path("data/patients_50000.csv")

# Ensure output directory exists
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# 1. ESI Distribution (Pondération pour éviter de noyer les cas graves)
ESI_WEIGHTS = [0.15, 0.25, 0.30, 0.20, 0.10] # ESI 1 (15%), 2 (25%), 3 (30%), 4 (20%), 5 (10%)
ESI_CLASSES = [1, 2, 3, 4, 5]

# 2. Symptoms by ESI mapping
SYMPTOMS_MAP = {
    1: ["arrêt_cardio", "detresse_respiratoire", "choc", "coma"],
    2: ["douleur_thoracique", "avc", "sepsis", "trauma_majeur"],
    3: ["fievre_moderee", "douleur_abdominale", "trauma_mineur"],
    4: ["douleur_legere", "petite_fievre", "toux"],
    5: ["renouvellement_ordonnance", "certificat", "suivi_routine"]
}

# 3. Symptom to Questions Mapping (Corrélation Questions <-> Symptômes)
# Assure que si un patient a une douleur thoracique, on répond 'oui' aux questions cardiaques
QUESTION_MAPPING = {
    "douleur_thoracique": ["q_douleur_irradiee_bras", "q_douleur_repos_effort", "q_medicaments_coeur", "q_antecedent_infarctus"],
    "arrêt_cardio": ["q_douleur_irradiee_bras", "q_antecedent_infarctus", "q_medicaments_coeur"],
    "detresse_respiratoire": ["q_dyspnee_aggrave_effort", "q_duree_dyspnee", "q_antecedent_asthme"],
    "choc": ["q_trauma_perte_conscience", "q_trauma_saignement", "q_trauma_zone"],
    "coma": ["q_neuro_confusion", "q_neuro_perte_conscience"],
    "avc": ["q_neuro_faiblesse", "q_neuro_parole", "q_hypertension_connue"],
    "sepsis": ["q_duree_fievre", "q_frissons_sueurs", "q_voyage_paludisme"],
    "trauma_majeur": ["q_trauma_saignement", "q_trauma_zone", "q_craquement_trauma", "q_deformation_trauma"],
    "fievre_moderee": ["q_duree_fievre", "q_frissons_sueurs"],
    "douleur_abdominale": ["q_localisation_abdomen", "q_vomissements_abdomen", "q_fievre_associee_abdomen"],
    "trauma_mineur": ["q_trauma_zone", "q_gonflement_trauma"],
    "douleur_legere": ["q_duree_symptomes"],
    "petite_fievre": ["q_duree_fievre"],
    "toux": ["q_toux_fievre"],
    "renouvellement_ordonnance": ["q_prise_medicament"],
    "certificat": [],
    "suivi_routine": []
}

# Phrases textes
TEXT_MAPPING = {
    "arrêt_cardio": ["Inconscient aucune respiration.", "S'est effondré subitement arrêt cardiaque."],
    "detresse_respiratoire": ["Je n'arrive plus à respirer, j'étouffe.", "Crise d'asthme très sévère, lèvres bleues."],
    "choc": ["Saignement massif, très faible tension.", "Perte de beaucoup de sang après un accident."],
    "coma": ["Totalement inconscient.", "Découvert dans le coma ce matin."],
    "douleur_thoracique": ["Forte douleur dans la poitrine qui irradie au bras gauche.", "Énorme pression sur le cœur, comme un étau."],
    "avc": ["Moitié du visage paralysée et difficulté à parler.", "Il a perdu l'usage de son bras droit soudainement."],
    "sepsis": ["Fièvre terrible, frissons et confusion totale.", "Peau marbrée et forte fièvre depuis hier."],
    "trauma_majeur": ["Accident de la route traumatisme crânien saignement.", "Chute de 3 mètres douleur extrême jambe."],
    "fievre_moderee": ["J'ai de la fièvre depuis 2 jours.", "38.5 de température et courbatures."],
    "douleur_abdominale": ["Maux de ventre en bas à droite intenses.", "Vomissements et crampes abdominales."],
    "trauma_mineur": ["Je me suis tordu la cheville.", "Coupure au doigt en cuisinant."],
    "douleur_legere": ["Mal au dos depuis une semaine.", "J'ai un peu mal à la tête."],
    "petite_fievre": ["Léger état grippal.", "37.8 ce matin, je me sens fatigué."],
    "toux": ["Je tousse depuis quelques jours.", "Gorge irritée."],
    "renouvellement_ordonnance": ["Je viens pour mon traitement tension.", "Renouvellement diabète."],
    "certificat": ["J'ai besoin d'un certificat d'aptitude", "Certificat de reprise du travail."],
    "suivi_routine": ["Contrôle annuel de routine", "Prise de sang de contrôle"]
}

def generate_vital_signs(esi):
    """
    Règle médicale impérative : Les constantes vitales définissent la gravité.
    SpO2 < 90% ou FC > 130 ou FC < 40 ou TAS < 85 = ESI 1 ou 2.
    """
    if esi == 1:
        spo2 = round(np.random.uniform(70, 89), 1)  # Critique < 90
        hr = int(np.random.choice([np.random.randint(20, 40), np.random.randint(140, 190)]))
        tas = int(np.random.uniform(50, 85)) # Choc
        tad = int(tas * 0.6)
        temp = round(np.random.uniform(35.0, 41.5), 1)
        resp = int(np.random.choice([np.random.randint(5, 10), np.random.randint(30, 45)]))
        pain = np.random.randint(0, 11)
        
    elif esi == 2:
        spo2 = round(np.random.uniform(90, 93), 1)
        hr = int(np.random.choice([np.random.randint(40, 50), np.random.randint(120, 140)]))
        tas = int(np.random.choice([np.random.randint(85, 100), np.random.randint(180, 220)]))
        tad = int(tas * 0.6)
        temp = round(np.random.choice([np.random.uniform(38.5, 40.5), np.random.uniform(35.5, 36.5)]), 1)
        resp = int(np.random.randint(22, 30))
        pain = np.random.randint(7, 11) # Forte douleur
        
    elif esi == 3:
        spo2 = round(np.random.uniform(94, 96), 1)
        hr = int(np.random.randint(90, 115))
        tas = int(np.random.randint(100, 160))
        tad = int(tas * 0.7)
        temp = round(np.random.uniform(37.5, 39.5), 1)
        resp = int(np.random.randint(16, 22))
        pain = np.random.randint(4, 8)
        
    else: # ESI 4 & 5 (Normaux)
        spo2 = round(np.random.uniform(97, 100), 1)
        hr = int(np.random.randint(60, 90))
        tas = int(np.random.randint(110, 140))
        tad = int(tas * 0.65)
        temp = round(np.random.uniform(36.5, 37.5), 1)
        resp = int(np.random.randint(12, 18))
        pain = np.random.randint(0, 4)

    return temp, hr, tas, tad, spo2, resp, pain

data = []

print("Génération de 50 000 patients avec constantes corrélées au niveau ESI...")
for i in tqdm(range(NUM_PATIENTS)):
    # Choix du niveau ESI (pondération pour éviter le biais ESI 4)
    esi = np.random.choice(ESI_CLASSES, p=ESI_WEIGHTS)
    
    # Démographie
    age = np.random.randint(1, 95)
    sex = np.random.choice([0, 1]) # 0 Femme, 1 Homme
    glucose = round(np.random.uniform(70, 140), 1)
    
    # Symptôme et NLP
    symptom_cat = np.random.choice(SYMPTOMS_MAP[esi])
    symptom_text = np.random.choice(TEXT_MAPPING[symptom_cat])
    
    # Constantes strictement corrélées à l'ESI
    temp, hr, tas, tad, spo2, resp, pain = generate_vital_signs(esi)
    
    # Binariser les symptômes en fonction de la catégorie
    chest_pain = 1 if symptom_cat in ["douleur_thoracique", "arrêt_cardio"] else 0
    dyspnea = 1 if symptom_cat == "detresse_respiratoire" or spo2 < 93 else 0
    loss_of_consciousness = 1 if symptom_cat in ["arrêt_cardio", "coma"] else 0
    severe_bleeding = 1 if symptom_cat in ["choc", "trauma_majeur"] else 0
    neurological_symptoms = 1 if symptom_cat in ["avc", "coma"] else 0
    abdominal_pain = 1 if symptom_cat == "douleur_abdominale" else 0
    fever = 1 if temp >= 38.0 else 0
    trauma = 1 if "trauma" in symptom_cat else 0

    # Initialiser toutes les questions à 0
    questions_data = {q: 0 for q in FEATURES_QUESTIONS}
    
    # Corréler les questions posées avec le symptôme patient
    questions_pertinentes = QUESTION_MAPPING.get(symptom_cat, [])
    for q in questions_pertinentes:
        if q in questions_data:
            # 90% de chances de répondre vrai aux questions corrélées
            questions_data[q] = np.random.choice([0, 1], p=[0.1, 0.9])
            if q.startswith("q_duree") or "localisation" in q or "zone" in q or "repos_effort" in q:
                # Encoder de manière arbitraire de 1 à 3 pour les choix multiples/texte
                questions_data[q] = np.random.randint(1, 4)

    # Patient record
    patient = {
        "id": f"PT-{i:06d}",
        "age": age,
        "sex": sex,
        "temperature": temp,
        "heart_rate": hr,
        "bp_systolic": tas,
        "bp_diastolic": tad,
        "spo2": spo2,
        "respiratory_rate": resp,
        "glucose": glucose,
        "pain_score": pain,
        "chest_pain": chest_pain,
        "dyspnea": dyspnea,
        "loss_of_consciousness": loss_of_consciousness,
        "severe_bleeding": severe_bleeding,
        "neurological_symptoms": neurological_symptoms,
        "abdominal_pain": abdominal_pain,
        "fever": fever,
        "trauma": trauma,
        "symptom_text": symptom_text,
        "esi_level": esi,
        "diagnostic_encode": esi # Simulation
    }
    
    # Intégrer les réponses aux questions
    patient.update(questions_data)
    
    data.append(patient)

# Save to CSV
df = pd.DataFrame(data)
df.to_csv(OUTPUT_PATH, index=False, encoding='utf-8')
print(f"✅ {NUM_PATIENTS} patients générés avec succès : {OUTPUT_PATH}")
print("\nRépartition ESI :")
print(df['esi_level'].value_counts(normalize=True) * 100)
