"""
data_generator.py — Générateur de données patients pour HealthGate
Projet HealthGate | Centrale Casablanca | PLBD 4 | 2025-2026

Génère un dataset synthétique de 1000 patients avec :
- Constantes vitales (température, FC, TA, SpO2, FR, glycémie)
- Symptômes binaires (douleur thoracique, dyspnée, etc.)
- Niveau ESI (1 à 5)
- [NOUVEAU] symptom_text       : phrase libre en français
- [NOUVEAU] arrival_time       : heure d'arrivée simulée
- [NOUVEAU] wait_time_minutes  : temps d'attente simulé (0-120 min)
"""

import pandas as pd
import numpy as np
import random

np.random.seed(42)
random.seed(42)

# ─────────────────────────────────────────────────────────────────────────────
# Phrases de symptômes réalistes par niveau ESI (contexte africain, français)
# ─────────────────────────────────────────────────────────────────────────────
SYMPTOMES_PAR_ESI = {
    1: [
        "Il est inconscient, ne répond plus du tout",
        "Saignement abondant qui ne s'arrête pas, beaucoup de sang",
        "Convulsions depuis 10 minutes, corps rigide",
        "Douleur thoracique intense, bras gauche engourdi, sueurs froides",
        "Accident de voiture, ne sent plus ses jambes",
        "A avalé du produit chimique, brûlures dans la gorge",
        "Pas de pouls, ne respire pas",
        "Traumatisme crânien grave suite à une chute, perte de connaissance",
        "Brûlures étendues sur le torse et les bras",
        "Détresse respiratoire sévère, lèvres bleues",
    ],
    2: [
        "J'ai très mal à la poitrine depuis ce matin et j'ai du mal à respirer",
        "Ma tension est très haute, j'ai des vertiges et de forts maux de tête",
        "Douleur dans la poitrine qui irradie dans le bras gauche",
        "Je vomis du sang depuis une heure, je me sens très faible",
        "Mon enfant a 40 de fièvre depuis 2 jours et ne mange plus",
        "Blessure profonde au ventre après une agression au couteau",
        "Je n'arrive plus à parler correctement depuis une heure, bouche tordue",
        "Douleur abdominale très intense, impossible de se lever",
        "Fracture ouverte au bras après une chute, os visible",
        "Difficultés à respirer, diabétique sous insuline",
    ],
    3: [
        "J'ai de la fièvre depuis 3 jours et des douleurs dans tout le corps",
        "Mal de ventre modéré depuis hier soir avec des nausées",
        "Je tousse beaucoup et j'ai du mal à avaler depuis 2 jours",
        "Blessure à la jambe suite à une chute, douleur modérée, gonflement",
        "Vomissements répétés depuis ce matin, je me sens faible et étourdi",
        "Maux de tête persistants depuis 2 jours, sensible à la lumière",
        "Forte douleur au dos après un effort physique",
        "Brûlures en urinant et douleurs dans le bas-ventre depuis hier",
        "Fièvre à 38.5 avec frissons et courbatures",
        "Entorse de la cheville, gonflement visible, douleur à la marche",
    ],
    4: [
        "J'ai une légère douleur au ventre depuis hier, ça va un peu mieux",
        "Mal de gorge depuis 2 jours avec un peu de fièvre",
        "Petite coupure au doigt, saignement léger, besoin de soins",
        "Nez bouché, toux légère depuis 3 jours, pas de fièvre",
        "Légère douleur à l'oreille droite depuis ce matin",
        "Maux de tête légers, je suis fatigué mais je marche bien",
        "Diarrhée légère depuis hier, 3 ou 4 fois, pas de sang",
        "Démangeaisons sur le bras droit, petites rougeurs",
        "Légère douleur en urinant depuis ce matin",
        "Petite contusion après une chute, pas de plaie ouverte",
    ],
    5: [
        "Je voudrais renouveler mon ordonnance pour l'hypertension",
        "J'ai des résultats d'analyses à faire interpréter par un médecin",
        "Vaccination de routine pour mon enfant de 6 mois",
        "Simple égratignure au genou, juste pour désinfecter",
        "Je veux juste vérifier ma tension, je me sens bien",
        "Petit rhume depuis hier, globalement je vais bien",
        "Suivi de plaie en cicatrisation, changer le pansement",
        "J'ai besoin d'un certificat médical pour le travail",
        "Légère démangeaison, aucun autre symptôme",
        "Contrôle de routine, rien d'urgent du tout",
    ],
}


def generer_constantes_vitales(esi_level: int) -> dict:
    """Génère des constantes vitales cohérentes avec le niveau ESI."""
    if esi_level == 1:
        temperature = round(random.choice([
            np.random.uniform(34.0, 35.5),
            np.random.uniform(39.8, 41.5)
        ]), 1)
        heart_rate = int(random.choice([
            np.random.randint(30, 50),
            np.random.randint(130, 180)
        ]))
        bp_systolic = int(random.choice([
            np.random.randint(60, 85),
            np.random.randint(180, 220)
        ]))
        spo2 = round(np.random.uniform(70, 88), 1)
        respiratory_rate = int(random.choice([
            np.random.randint(4, 8),
            np.random.randint(30, 45)
        ]))
        glucose = int(random.choice([
            np.random.randint(30, 55),
            np.random.randint(400, 600)
        ]))
        pain_score = int(np.random.randint(8, 11))

    elif esi_level == 2:
        temperature = round(random.choice([
            np.random.uniform(35.5, 36.2),
            np.random.uniform(39.0, 40.5)
        ]), 1)
        heart_rate = int(random.choice([
            np.random.randint(50, 60),
            np.random.randint(110, 140)
        ]))
        bp_systolic = int(random.choice([
            np.random.randint(80, 95),
            np.random.randint(165, 190)
        ]))
        spo2 = round(np.random.uniform(88, 93), 1)
        respiratory_rate = int(np.random.randint(22, 30))
        glucose = int(random.choice([
            np.random.randint(55, 70),
            np.random.randint(300, 420)
        ]))
        pain_score = int(np.random.randint(6, 9))

    elif esi_level == 3:
        temperature = round(np.random.uniform(37.5, 39.5), 1)
        heart_rate = int(np.random.randint(90, 115))
        bp_systolic = int(np.random.randint(130, 165))
        spo2 = round(np.random.uniform(93, 96), 1)
        respiratory_rate = int(np.random.randint(18, 24))
        glucose = int(np.random.randint(90, 200))
        pain_score = int(np.random.randint(4, 7))

    elif esi_level == 4:
        temperature = round(np.random.uniform(36.5, 38.0), 1)
        heart_rate = int(np.random.randint(70, 95))
        bp_systolic = int(np.random.randint(110, 135))
        spo2 = round(np.random.uniform(96, 99), 1)
        respiratory_rate = int(np.random.randint(14, 20))
        glucose = int(np.random.randint(80, 130))
        pain_score = int(np.random.randint(2, 5))

    else:  # ESI 5
        temperature = round(np.random.uniform(36.2, 37.2), 1)
        heart_rate = int(np.random.randint(60, 85))
        bp_systolic = int(np.random.randint(105, 125))
        spo2 = round(np.random.uniform(97, 100), 1)
        respiratory_rate = int(np.random.randint(12, 16))
        glucose = int(np.random.randint(75, 110))
        pain_score = int(np.random.randint(0, 3))

    bp_diastolic = int(bp_systolic * random.uniform(0.55, 0.65))

    return {
        "temperature":      temperature,
        "heart_rate":       heart_rate,
        "bp_systolic":      bp_systolic,
        "bp_diastolic":     bp_diastolic,
        "spo2":             spo2,
        "respiratory_rate": respiratory_rate,
        "glucose":          glucose,
        "pain_score":       pain_score,
    }


def generer_symptomes_binaires(esi_level: int) -> dict:
    """Génère les symptômes binaires selon les probabilités par niveau ESI."""
    probas = {
        # (chest_pain, dyspnea, loss_of_consciousness, severe_bleeding,
        #  neurological_symptoms, abdominal_pain, fever, trauma)
        1: (0.60, 0.80, 0.70, 0.50, 0.50, 0.30, 0.40, 0.50),
        2: (0.50, 0.60, 0.20, 0.20, 0.30, 0.40, 0.50, 0.30),
        3: (0.20, 0.30, 0.05, 0.05, 0.10, 0.50, 0.60, 0.20),
        4: (0.05, 0.10, 0.00, 0.00, 0.05, 0.20, 0.30, 0.10),
        5: (0.00, 0.05, 0.00, 0.00, 0.00, 0.05, 0.10, 0.00),
    }
    p = probas[esi_level]
    return {
        "chest_pain":            int(random.random() < p[0]),
        "dyspnea":               int(random.random() < p[1]),
        "loss_of_consciousness": int(random.random() < p[2]),
        "severe_bleeding":       int(random.random() < p[3]),
        "neurological_symptoms": int(random.random() < p[4]),
        "abdominal_pain":        int(random.random() < p[5]),
        "fever":                 int(random.random() < p[6]),
        "trauma":                int(random.random() < p[7]),
    }


def calculer_triage_score(constantes: dict, symptomes: dict, esi_level: int) -> float:
    """Calcule un score de triage brut numérique."""
    score = (6 - esi_level) * 2.0
    if constantes["spo2"] < 90:
        score += 3.0
    if constantes["heart_rate"] > 120 or constantes["heart_rate"] < 50:
        score += 2.0
    if constantes["bp_systolic"] < 90 or constantes["bp_systolic"] > 180:
        score += 2.0
    if constantes["temperature"] > 39.5 or constantes["temperature"] < 35.5:
        score += 1.0
    score += constantes["pain_score"] * 0.3
    score += symptomes["chest_pain"] * 1.5
    score += symptomes["loss_of_consciousness"] * 3.0
    score += symptomes["severe_bleeding"] * 2.5
    return round(score, 2)


def generer_heure_arrivee() -> str:
    """Génère une heure d'arrivée aléatoire dans la journée (HH:MM)."""
    heure  = np.random.randint(0, 24)
    minute = np.random.randint(0, 60)
    return f"{heure:02d}:{minute:02d}"


def generer_temps_attente(esi_level: int) -> int:
    """
    Génère un temps d'attente simulé (en minutes) selon l'ESI.
    ESI 1 = quasi immédiat | ESI 5 = longue attente possible.
    """
    plages = {
        1: (0, 5),
        2: (0, 15),
        3: (10, 60),
        4: (20, 90),
        5: (30, 120),
    }
    mini, maxi = plages[esi_level]
    return int(np.random.randint(mini, maxi + 1))


def generer_patient(patient_id: str) -> dict:
    """Génère un patient complet avec toutes ses données."""
    # Répartition ESI réaliste pour urgences africaines
    esi_level = int(np.random.choice(
        [1, 2, 3, 4, 5],
        p=[0.05, 0.15, 0.30, 0.30, 0.20]
    ))

    # Distribution d'âge réaliste
    age = int(np.random.choice([
        np.random.randint(1, 14),    # enfant
        np.random.randint(14, 60),   # adulte
        np.random.randint(60, 95),   # senior
    ], p=[0.15, 0.65, 0.20]))

    sex = int(np.random.choice([0, 1]))  # 0 = femme, 1 = homme

    constantes = generer_constantes_vitales(esi_level)
    symptomes  = generer_symptomes_binaires(esi_level)
    score_brut = calculer_triage_score(constantes, symptomes, esi_level)

    return {
        "patient_id":         patient_id,
        "age":                age,
        "sex":                sex,
        **constantes,
        **symptomes,
        "triage_score_raw":   score_brut,
        "esi_level":          esi_level,
        # ── Nouvelles colonnes pour queue_manager ──
        "symptom_text":       random.choice(SYMPTOMES_PAR_ESI[esi_level]),
        "arrival_time":       generer_heure_arrivee(),
        "wait_time_minutes":  generer_temps_attente(esi_level),
    }


def generer_dataset(n: int = 1000, chemin_sortie: str = "data/patients_1000.csv") -> pd.DataFrame:
    """Génère et sauvegarde le dataset complet."""
    print(f"[HealthGate] Génération de {n} patients en cours...")
    patients = [generer_patient(f"PT{i+1:04d}") for i in range(n)]
    df = pd.DataFrame(patients)

    print("\n[INFO] Répartition des niveaux ESI :")
    print(df["esi_level"].value_counts().sort_index().to_string())
    print(f"\n[INFO] Colonnes : {list(df.columns)}")
    print(f"[INFO] Dimensions : {df.shape}")

    df.to_csv(chemin_sortie, index=False)
    print(f"\n[OK] Dataset sauvegardé → {chemin_sortie}")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    df = generer_dataset(n=1000, chemin_sortie="data/patients_1000.csv")
    print("\n[APERÇU] 3 premiers patients :")
    cols_apercu = ["patient_id", "age", "esi_level",
                   "symptom_text", "arrival_time", "wait_time_minutes"]
    print(df[cols_apercu].head(3).to_string())
