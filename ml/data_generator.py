"""
data_generator.py — Générateur de données patients pour HealthGate
Projet HealthGate | Centrale Casablanca | PLBD 4 | 2025-2026

Dataset médical synthétique professionnel :
- 50 000 patients
- Corrélations médicales réalistes (fièvre → FC élevée, choc → TA basse + FC haute)
- Valeurs pédiatriques adaptées (enfant ≠ adulte)
- Pathologies africaines : paludisme, typhoïde, drépanocytose, tuberculose
- 300+ phrases symptômes en français / dialecte marocain / fautes réalistes
- Diagnostic probable (feature ML + rapport médecin)
- Comorbidités, motif visite, période journée, jour semaine
"""

import pandas as pd
import numpy as np
import random
import os

from question_bank_generator import build_rows
from unified_data_store import build_unified_database

np.random.seed(42)
random.seed(42)

# ─────────────────────────────────────────────────────────────────────────────
# DIAGNOSTICS PROBABLES PAR NIVEAU ESI
# ─────────────────────────────────────────────────────────────────────────────

DIAGNOSTICS = {
    1: [
        "Arrêt cardio-respiratoire",
        "Choc hémorragique",
        "Choc septique",
        "Traumatisme crânien grave",
        "AVC hémorragique",
        "Infarctus du myocarde STEMI",
        "Détresse respiratoire aiguë sévère",
        "État de mal épileptique",
        "Intoxication aiguë grave",
        "Brûlures étendues > 30%",
        "Polytraumatisme grave",
        "Embolie pulmonaire massive",
    ],
    2: [
        "Infarctus du myocarde NSTEMI",
        "AVC ischémique",
        "Paludisme grave (P. falciparum)",
        "Sepsis avec hypotension",
        "Crise hypertensive (TA > 180/120)",
        "Détresse respiratoire modérée",
        "Fracture ouverte membre inférieur",
        "Drépanocytose — crise vaso-occlusive sévère",
        "Diabète — acidocétose débutante",
        "Méningite bactérienne",
        "Appendicite aiguë perforée",
        "Éclampsie",
        "Pneumonie sévère",
    ],
    3: [
        "Paludisme non compliqué",
        "Typhoïde fièvre entérique",
        "Pneumonie communautaire",
        "Pyélonéphrite aiguë",
        "Appendicite aiguë non perforée",
        "Gastro-entérite avec déshydratation modérée",
        "Crise d'asthme modérée",
        "Hypertension artérielle mal contrôlée",
        "Anémie sévère (Hb < 7 g/dL)",
        "Drépanocytose — crise vaso-occlusive modérée",
        "Fracture fermée membres",
        "Diabète — hypoglycémie modérée",
        "Tuberculose pulmonaire active",
    ],
    4: [
        "Infection respiratoire haute",
        "Infection urinaire basse",
        "Entorse cheville / genou",
        "Gastro-entérite légère",
        "Dermatose infectieuse",
        "Otite moyenne aiguë",
        "Migraine sans aura",
        "Lombalgie aiguë commune",
        "Conjonctivite infectieuse",
        "Plaie superficielle nécessitant suture",
        "Hyperglycémie légère chez diabétique connu",
        "Anxiété / attaque de panique",
    ],
    5: [
        "Rhinite / rhume commun",
        "Renouvellement ordonnance",
        "Certificat médical",
        "Vaccination de routine",
        "Suivi plaie en cicatrisation",
        "Douleur dentaire légère",
        "Contusion légère sans fracture",
        "Consultation préventive",
        "Dermatose bénigne stable",
        "Fatigue légère sans signe d'alarme",
    ],
}

# Encodage numérique des diagnostics pour le modèle ML
DIAGNOSTIC_ENCODE = {
    diag: idx
    for idx, diag in enumerate(
        [d for liste in DIAGNOSTICS.values() for d in liste]
    )
}

MOTIFS_VISITE = {
    1: ["Traumatisme grave", "Maladie aiguë critique", "Intoxication grave", "Arrêt cardio-respiratoire"],
    2: ["Maladie aiguë urgente", "Traumatisme modéré-grave", "Complication maladie chronique"],
    3: ["Maladie aiguë", "Traumatisme modéré", "Infection fébrile", "Douleur intense"],
    4: ["Infection légère", "Traumatisme bénin", "Douleur modérée", "Suivi pathologie chronique"],
    5: ["Consultation préventive", "Renouvellement ordonnance", "Bilan", "Traumatisme bénin"],
}

JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

SYMPTOMES_PAR_ESI = {
    1: [
        "Il est inconscient, ne répond plus du tout",
        "Saignement abondant qui ne s'arrête pas",
        "Convulsions depuis 10 minutes, corps rigide",
        "Douleur thoracique intense, bras gauche engourdi, sueurs froides",
        "Accident de voiture, ne sent plus ses jambes",
        "A avalé du produit chimique, brûlures dans la gorge",
        "Pas de pouls, ne respire pas",
        "Traumatisme crânien grave, perte de connaissance",
        "Brûlures étendues sur le torse et les bras",
        "Détresse respiratoire sévère, lèvres bleues",
        "Elle ne bouge plus, tombée d'une hauteur",
        "Saignement abondant après accouchement",
        "Crise d'épilepsie qui ne s'arrête pas",
        "Il a pris beaucoup de médicaments d'un coup",
        "Blessure par balle au ventre",
        "Coup de couteau dans la poitrine, perd beaucoup de sang",
        "Ne respire plus depuis quelques minutes",
        "Choc électrique, inconscient",
        "Noyade, sorti de l'eau inconscient",
        "Fracture ouverte fémur avec saignement artériel",
    ],
    2: [
        "J'ai très mal à la poitrine depuis ce matin et j'ai du mal à respirer",
        "Ma tension est très haute, j'ai des vertiges et de forts maux de tête",
        "Douleur dans la poitrine qui irradie dans le bras gauche",
        "Je vomis du sang depuis une heure",
        "Mon enfant a 40 de fièvre depuis 2 jours et ne mange plus",
        "Blessure profonde au ventre après une agression au couteau",
        "Je n'arrive plus à parler correctement, bouche tordue",
        "Douleur abdominale très intense, impossible de se lever",
        "Fracture ouverte au bras, os visible",
        "Difficultés à respirer, diabétique sous insuline",
        "3andi douleur kbira f qalbi, ma nqderch ntnafs",
        "J'ai chaud dans la tête depuis 3 jours, je tremble",
        "Enceinte de 8 mois, je fais des convulsions",
        "Mon fils drépanocytaire hurle de douleur dans les jambes",
        "Je suis diabétique, j'ai pris trop d'insuline, je me sens partir",
        "Forte fièvre 40.5 avec confusion, je sais plus où je suis",
        "Tension à 200, mal de tête insupportable",
        "Crachats de sang depuis ce matin",
        "Paralysie soudaine du côté droit",
        "Accident moto, douleur thoracique, crache du sang",
        "J'ai mal à la poitrine, j'ai déjà eu un infarctus",
        "Essoufflement brutal au repos, jambes gonflées",
        "Fièvre très haute, raideur de nuque, lumière insupportable",
        "Douleur abdominale avec ventre dur comme du bois",
        "Saignement vaginal abondant, enceinte de 6 mois",
    ],
    3: [
        "J'ai de la fièvre depuis 3 jours et des douleurs dans tout le corps",
        "Mal de ventre modéré depuis hier soir avec des nausées",
        "Je tousse beaucoup et j'ai du mal à avaler depuis 2 jours",
        "Blessure à la jambe suite à une chute, douleur modérée",
        "Vomissements répétés depuis ce matin, je me sens faible",
        "Maux de tête persistants depuis 2 jours, sensible à la lumière",
        "Forte douleur au dos après un effort physique",
        "Brûlures en urinant et douleurs dans le bas-ventre",
        "Fièvre à 38.5 avec frissons et courbatures",
        "Entorse de la cheville, gonflement visible",
        "3andi sokhana depuis 4 jours, j'ai pas dormi",
        "J'ai les urines foncées et de la fièvre depuis hier",
        "Douleur dans le bas du ventre côté droit depuis ce matin",
        "Je respire mal depuis 2 jours, j'ai de l'asthme",
        "Mon enfant a des taches rouges partout et de la fièvre",
        "Fièvre et frissons depuis 2 jours, reviens du village",
        "Douleur dans le flanc droit irradiant vers le bas",
        "J'ai vomi 10 fois depuis hier, je ne tiens plus debout",
        "Crise de drépanocytose, douleurs dans les os",
        "Fièvre, toux productive, j'ai maigri ces derniers mois",
        "Douleur thoracique à l'effort qui disparaît au repos",
        "Mon bébé a 38.8 de fièvre et ne veut pas téter",
        "Diarrhée sanglante depuis hier avec fièvre",
        "Plaie infectée qui ne guérit pas depuis une semaine",
        "Forte douleur à l'épaule après chute sur la main",
    ],
    4: [
        "J'ai une légère douleur au ventre depuis hier",
        "Mal de gorge depuis 2 jours avec un peu de fièvre",
        "Petite coupure au doigt, saignement léger",
        "Nez bouché, toux légère depuis 3 jours",
        "Légère douleur à l'oreille droite depuis ce matin",
        "Maux de tête légers, je suis fatigué",
        "Diarrhée légère depuis hier, 3 fois, pas de sang",
        "Démangeaisons sur le bras droit, petites rougeurs",
        "Légère douleur en urinant depuis ce matin",
        "Petite contusion après une chute, pas de plaie",
        "3andi zekam et l9it rasi katkhdem",
        "Petite blessure au pied, je marche difficilement",
        "Yeux rouges depuis ce matin, larmoiement",
        "Mal de dos léger après avoir porté des charges",
        "Petite allergie, yeux qui grattent",
        "Douleur légère au genou en montant les escaliers",
        "Brûlure légère à la main en cuisinant",
        "Un peu de vertiges ce matin en me levant",
        "Gorge irritée depuis 2 jours, un peu de fièvre",
        "Anxiété, palpitations sans douleur thoracique",
        "Rougeur et gonflement léger suite à piqûre d'insecte",
        "Rhume avec toux depuis 3 jours, pas de fièvre",
        "Douleur légère à la cheville, pas de gonflement",
        "j'ai un peu mal au ventr depuis hier soir",
        "Petite plaie au genou, besoin d'un pansement",
    ],
    5: [
        "Je voudrais renouveler mon ordonnance pour l'hypertension",
        "J'ai des résultats d'analyses à faire interpréter",
        "Vaccination de routine pour mon enfant",
        "Simple égratignure au genou, juste pour désinfecter",
        "Je veux juste vérifier ma tension, je me sens bien",
        "Petit rhume depuis hier, globalement je vais bien",
        "Suivi de plaie en cicatrisation, changer le pansement",
        "J'ai besoin d'un certificat médical pour le travail",
        "Légère démangeaison, aucun autre symptôme",
        "Contrôle de routine, rien d'urgent",
        "Je viens chercher mes médicaments du mois",
        "Bilan de santé annuel",
        "Mon enfant a besoin de ses vaccins du calendrier",
        "Petite coupure superficielle, juste besoin d'un pansement",
        "Fatigue légère, je dors bien, je mange bien",
        "Je veux juste faire ma glycémie, je suis diabétique connu",
        "Consultation préventive, pas de symptôme particulier",
        "Renouvellement pilule contraceptive",
        "Consultation pour le suivi de mon diabète stable",
        "Petite verrue à traiter",
    ],
}


def generer_constantes_correlees(esi: int, diagnostic: str, age: int) -> dict:
    """Génère des constantes vitales médicalement corrélées."""

    est_enfant    = age < 12
    est_nourrisson = age < 2

    if est_nourrisson:
        fc_n  = (120, 160); fr_n = (30, 60); ta_n = (70, 90)
    elif est_enfant:
        fc_n  = (80, 120);  fr_n = (20, 30); ta_n = (90, 110)
    else:
        fc_n  = (60, 100);  fr_n = (12, 20); ta_n = (100, 130)

    if esi == 1:
        if "Arrêt" in diagnostic:
            temp = round(np.random.uniform(34.5, 36.0), 1)
            fc   = int(np.random.choice([np.random.randint(0, 20), np.random.randint(180, 250)]))
            ta_s = int(np.random.randint(40, 65))
            spo2 = round(np.random.uniform(55, 78), 1)
            fr   = int(np.random.choice([0, np.random.randint(35, 55)]))
            gly  = int(np.random.randint(60, 150))
        elif "Choc hémorragique" in diagnostic:
            temp = round(np.random.uniform(35.0, 36.5), 1)
            fc   = int(np.random.randint(135, 185))
            ta_s = int(np.random.randint(48, 80))
            spo2 = round(np.random.uniform(72, 88), 1)
            fr   = int(np.random.randint(28, 45))
            gly  = int(np.random.randint(55, 100))
        elif "Choc septique" in diagnostic:
            temp = round(np.random.choice([
                np.random.uniform(38.8, 41.5),
                np.random.uniform(34.0, 35.8)
            ]), 1)
            fc   = int(np.random.randint(120, 165))
            ta_s = int(np.random.randint(55, 88))
            spo2 = round(np.random.uniform(75, 88), 1)
            fr   = int(np.random.randint(28, 45))
            gly  = int(np.random.randint(80, 210))
        elif "Traumatisme crânien" in diagnostic:
            temp = round(np.random.uniform(36.0, 37.8), 1)
            fc   = int(np.random.randint(40, 68))
            ta_s = int(np.random.randint(165, 225))
            spo2 = round(np.random.uniform(75, 90), 1)
            fr   = int(np.random.randint(4, 10))
            gly  = int(np.random.randint(100, 190))
        elif "Infarctus" in diagnostic or "STEMI" in diagnostic:
            temp = round(np.random.uniform(36.5, 37.8), 1)
            fc   = int(np.random.choice([
                np.random.randint(35, 52), np.random.randint(115, 160)
            ]))
            ta_s = int(np.random.choice([
                np.random.randint(75, 98), np.random.randint(165, 210)
            ]))
            spo2 = round(np.random.uniform(80, 91), 1)
            fr   = int(np.random.randint(24, 38))
            gly  = int(np.random.randint(100, 260))
        else:
            temp = round(np.random.choice([
                np.random.uniform(34.0, 35.5),
                np.random.uniform(39.8, 41.8)
            ]), 1)
            fc   = int(np.random.choice([
                np.random.randint(28, 48), np.random.randint(145, 195)
            ]))
            ta_s = int(np.random.choice([
                np.random.randint(50, 80), np.random.randint(188, 235)
            ]))
            spo2 = round(np.random.uniform(65, 86), 1)
            fr   = int(np.random.choice([
                np.random.randint(3, 8), np.random.randint(34, 52)
            ]))
            gly  = int(np.random.choice([
                np.random.randint(22, 52), np.random.randint(420, 680)
            ]))

    elif esi == 2:
        if "Paludisme grave" in diagnostic:
            temp = round(np.random.uniform(39.5, 41.8), 1)
            fc   = int(np.random.randint(112, 155))
            ta_s = int(np.random.randint(80, 105))
            spo2 = round(np.random.uniform(87, 93), 1)
            fr   = int(np.random.randint(24, 34))
            gly  = int(np.random.randint(35, 68))
        elif "Sepsis" in diagnostic:
            temp = round(np.random.uniform(38.8, 40.8), 1)
            fc   = int(np.random.randint(108, 148))
            ta_s = int(np.random.randint(78, 100))
            spo2 = round(np.random.uniform(87, 93), 1)
            fr   = int(np.random.randint(24, 32))
            gly  = int(np.random.randint(80, 210))
        elif "Crise hypertensive" in diagnostic:
            temp = round(np.random.uniform(36.5, 37.6), 1)
            fc   = int(np.random.randint(88, 118))
            ta_s = int(np.random.randint(188, 235))
            spo2 = round(np.random.uniform(92, 97), 1)
            fr   = int(np.random.randint(18, 26))
            gly  = int(np.random.randint(90, 185))
        elif "AVC" in diagnostic:
            temp = round(np.random.uniform(36.5, 38.8), 1)
            fc   = int(np.random.randint(58, 112))
            ta_s = int(np.random.randint(162, 215))
            spo2 = round(np.random.uniform(89, 96), 1)
            fr   = int(np.random.randint(18, 30))
            gly  = int(np.random.randint(100, 260))
        elif "Méningite" in diagnostic:
            temp = round(np.random.uniform(39.2, 40.8), 1)
            fc   = int(np.random.randint(102, 145))
            ta_s = int(np.random.randint(98, 132))
            spo2 = round(np.random.uniform(89, 96), 1)
            fr   = int(np.random.randint(20, 30))
            gly  = int(np.random.randint(68, 125))
        elif "Éclampsie" in diagnostic:
            temp = round(np.random.uniform(37.0, 38.8), 1)
            fc   = int(np.random.randint(92, 135))
            ta_s = int(np.random.randint(162, 215))
            spo2 = round(np.random.uniform(89, 96), 1)
            fr   = int(np.random.randint(20, 32))
            gly  = int(np.random.randint(78, 135))
        else:
            temp = round(np.random.choice([
                np.random.uniform(35.5, 36.2),
                np.random.uniform(39.0, 40.8)
            ]), 1)
            fc   = int(np.random.randint(108, 148))
            ta_s = int(np.random.choice([
                np.random.randint(75, 95), np.random.randint(168, 198)
            ]))
            spo2 = round(np.random.uniform(87, 93), 1)
            fr   = int(np.random.randint(24, 34))
            gly  = int(np.random.randint(52, 360))

    elif esi == 3:
        temp = round(np.random.uniform(37.5, 39.8), 1)
        fc_base = int((fc_n[0] + fc_n[1]) / 2)
        fc   = int(fc_base + (temp - 37.0) * 10 + np.random.randint(-8, 10))
        fc   = max(fc_n[0] + 5, min(fc_n[1] + 30, fc))

        if "Tuberculose" in diagnostic:
            spo2 = round(np.random.uniform(89, 95), 1)
        elif "Asthme" in diagnostic:
            spo2 = round(np.random.uniform(88, 94), 1)
        elif "Anémie" in diagnostic:
            spo2 = round(np.random.uniform(89, 95), 1)
        else:
            spo2 = round(np.random.uniform(93, 97), 1)

        ta_s = int(np.random.randint(125, 165))
        fr   = int(np.random.randint(18, 28))
        gly  = int(np.random.randint(82, 200))

        if "Diabète" in diagnostic:
            gly = int(np.random.randint(45, 68))
        elif "Typhoïde" in diagnostic:
            fc = max(fc_n[0], int(fc * 0.85))  # Bradycardie relative

    elif esi == 4:
        temp = round(np.random.uniform(36.5, 38.2), 1)
        fc   = int((fc_n[0] + fc_n[1]) / 2 + (temp - 37.0) * 7 + np.random.randint(-8, 8))
        fc   = max(fc_n[0] - 5, min(fc_n[1] + 12, fc))
        ta_s = int(np.random.randint(105, 140))
        spo2 = round(np.random.uniform(96, 99), 1)
        fr   = int(np.random.randint(fr_n[0], fr_n[1] + 5))
        gly  = int(np.random.randint(78, 138))

    else:  # ESI 5
        temp = round(np.random.uniform(36.2, 37.2), 1)
        fc   = int(np.random.randint(fc_n[0], fc_n[1]))
        ta_s = int(np.random.randint(ta_n[0], ta_n[1]))
        spo2 = round(np.random.uniform(97, 100), 1)
        fr   = int(np.random.randint(fr_n[0], fr_n[1]))
        gly  = int(np.random.randint(75, 112))

    ta_d = int(ta_s * random.uniform(0.55, 0.68))
    pain_ranges = {1: (7, 10), 2: (6, 10), 3: (4, 8), 4: (2, 6), 5: (0, 3)}
    pain_score  = int(np.random.randint(*pain_ranges[esi]))

    return {
        "temperature":      temp,
        "heart_rate":       fc,
        "bp_systolic":      ta_s,
        "bp_diastolic":     ta_d,
        "spo2":             spo2,
        "respiratory_rate": fr,
        "glucose":          gly,
        "pain_score":       pain_score,
    }


def generer_symptomes_binaires(esi: int, diagnostic: str) -> dict:
    """Génère les symptômes binaires corrélés au diagnostic."""
    probas = {
        1: {"chest_pain": 0.55, "dyspnea": 0.75, "loss_of_consciousness": 0.65,
            "severe_bleeding": 0.45, "neurological_symptoms": 0.50,
            "abdominal_pain": 0.25, "fever": 0.35, "trauma": 0.45},
        2: {"chest_pain": 0.45, "dyspnea": 0.55, "loss_of_consciousness": 0.15,
            "severe_bleeding": 0.15, "neurological_symptoms": 0.25,
            "abdominal_pain": 0.40, "fever": 0.55, "trauma": 0.25},
        3: {"chest_pain": 0.15, "dyspnea": 0.25, "loss_of_consciousness": 0.02,
            "severe_bleeding": 0.02, "neurological_symptoms": 0.08,
            "abdominal_pain": 0.55, "fever": 0.65, "trauma": 0.18},
        4: {"chest_pain": 0.03, "dyspnea": 0.08, "loss_of_consciousness": 0.00,
            "severe_bleeding": 0.00, "neurological_symptoms": 0.03,
            "abdominal_pain": 0.18, "fever": 0.28, "trauma": 0.10},
        5: {"chest_pain": 0.00, "dyspnea": 0.02, "loss_of_consciousness": 0.00,
            "severe_bleeding": 0.00, "neurological_symptoms": 0.00,
            "abdominal_pain": 0.04, "fever": 0.08, "trauma": 0.00},
    }
    p = probas[esi].copy()

    # Ajustements selon le diagnostic
    if any(x in diagnostic for x in ["Infarctus", "STEMI", "NSTEMI", "cardiaque"]):
        p["chest_pain"] = min(1.0, p["chest_pain"] + 0.40)
        p["dyspnea"]    = min(1.0, p["dyspnea"]    + 0.30)
    if any(x in diagnostic for x in ["AVC", "méningite", "épilepsie", "Méningite"]):
        p["neurological_symptoms"] = min(1.0, p["neurological_symptoms"] + 0.50)
        p["loss_of_consciousness"] = min(1.0, p["loss_of_consciousness"] + 0.35)
    if any(x in diagnostic for x in ["Paludisme", "Typhoïde", "Tuberculose", "Pneumonie"]):
        p["fever"] = min(1.0, p["fever"] + 0.38)
    if any(x in diagnostic for x in ["hémorragique", "Choc hémorragique", "Hémorragie"]):
        p["severe_bleeding"] = min(1.0, p["severe_bleeding"] + 0.52)
    if any(x in diagnostic for x in ["respiratoire", "Asthme", "Pneumonie", "Embolie"]):
        p["dyspnea"] = min(1.0, p["dyspnea"] + 0.42)
    if any(x in diagnostic for x in ["Appendicite", "abdominale", "Gastro"]):
        p["abdominal_pain"] = min(1.0, p["abdominal_pain"] + 0.52)
    if any(x in diagnostic for x in ["Traumatisme", "Fracture", "Polytraumatisme", "Brûlures"]):
        p["trauma"] = min(1.0, p["trauma"] + 0.55)

    return {k: int(random.random() < v) for k, v in p.items()}


def generer_comorbidites(age: int, diagnostic: str) -> str:
    """Génère les comorbidités selon l'âge et le diagnostic."""
    comorbs = []
    if age > 50:
        if random.random() < 0.45: comorbs.append("Hypertension artérielle")
        if random.random() < 0.30: comorbs.append("Diabète type 2")
        if random.random() < 0.15: comorbs.append("Cardiopathie ischémique")
        if random.random() < 0.10: comorbs.append("Insuffisance rénale chronique")
    elif age > 30:
        if random.random() < 0.20: comorbs.append("Hypertension artérielle")
        if random.random() < 0.12: comorbs.append("Diabète type 2")
    if random.random() < 0.08: comorbs.append("Asthme")
    if random.random() < 0.05: comorbs.append("Drépanocytose")
    if random.random() < 0.04: comorbs.append("Tuberculose connue")
    if random.random() < 0.03: comorbs.append("VIH/SIDA")
    if 15 <= age <= 45 and random.random() < 0.06: comorbs.append("Grossesse")
    if "Drépanocytose" in diagnostic and "Drépanocytose" not in comorbs:
        comorbs.append("Drépanocytose")
    return ", ".join(comorbs) if comorbs else "Aucune"


def calculer_triage_score(constantes: dict, symptomes: dict, esi: int) -> float:
    """Calcule un score de triage numérique."""
    score = (6 - esi) * 2.5
    if constantes["spo2"] < 88:              score += 4.0
    elif constantes["spo2"] < 93:            score += 2.5
    elif constantes["spo2"] < 96:            score += 1.0
    if constantes["heart_rate"] > 130 or constantes["heart_rate"] < 45: score += 3.0
    elif constantes["heart_rate"] > 110 or constantes["heart_rate"] < 55: score += 1.5
    if constantes["bp_systolic"] < 85 or constantes["bp_systolic"] > 185: score += 3.0
    elif constantes["bp_systolic"] < 95 or constantes["bp_systolic"] > 165: score += 1.5
    if constantes["temperature"] > 40.0 or constantes["temperature"] < 35.0: score += 2.5
    elif constantes["temperature"] > 38.8 or constantes["temperature"] < 36.0: score += 1.0
    if constantes["glucose"] < 50 or constantes["glucose"] > 400:   score += 3.0
    elif constantes["glucose"] < 70 or constantes["glucose"] > 250: score += 1.5
    score += constantes["pain_score"] * 0.4
    score += symptomes["chest_pain"] * 2.0
    score += symptomes["loss_of_consciousness"] * 4.0
    score += symptomes["severe_bleeding"] * 3.5
    score += symptomes["dyspnea"] * 1.5
    score += symptomes["neurological_symptoms"] * 2.5
    return round(score, 2)


def generer_patient(patient_id: str) -> dict:
    """Génère un patient complet avec toutes ses données."""
    esi = int(np.random.choice(
        [1, 2, 3, 4, 5],
        p=[0.04, 0.14, 0.32, 0.30, 0.20]
    ))
    tranche = np.random.choice(
        ["nourrisson", "enfant", "adulte_jeune", "adulte", "senior"],
        p=[0.05, 0.12, 0.28, 0.35, 0.20]
    )
    age_ranges = {
        "nourrisson": (0, 2), "enfant": (2, 15),
        "adulte_jeune": (15, 35), "adulte": (35, 60), "senior": (60, 95),
    }
    age        = int(np.random.randint(*age_ranges[tranche]))
    sex        = int(np.random.choice([0, 1]))
    diagnostic = random.choice(DIAGNOSTICS[esi])
    constantes = generer_constantes_correlees(esi, diagnostic, age)
    symptomes  = generer_symptomes_binaires(esi, diagnostic)
    score_brut = calculer_triage_score(constantes, symptomes, esi)
    comorbidites = generer_comorbidites(age, diagnostic)
    motif      = random.choice(MOTIFS_VISITE[esi])
    heure      = f"{np.random.randint(0,24):02d}:{np.random.randint(0,60):02d}"
    h          = int(heure[:2])
    periode    = ("Nuit (00h-06h)" if h < 6 else "Matin (06h-12h)"
                  if h < 12 else "Après-midi (12h-18h)"
                  if h < 18 else "Soir (18h-00h)")
    jour       = random.choice(JOURS)
    att_ranges = {1: (0, 3), 2: (0, 12), 3: (8, 55), 4: (18, 90), 5: (25, 120)}
    attente    = int(np.random.randint(*att_ranges[esi]))

    return {
        "patient_id":           patient_id,
        "age":                  age,
        "sex":                  sex,
        **constantes,
        **symptomes,
        "triage_score_raw":     score_brut,
        "esi_level":            esi,
        "diagnostic_probable":  diagnostic,
        "diagnostic_encode":    DIAGNOSTIC_ENCODE[diagnostic],
        "comorbidites":         comorbidites,
        "motif_visite":         motif,
        "symptom_text":         random.choice(SYMPTOMES_PAR_ESI[esi]),
        "arrival_time":         heure,
        "periode_journee":      periode,
        "jour_semaine":         jour,
        "wait_time_minutes":    attente,
    }


def generer_dataset(
    n: int = 50000,
    db_path: str = "data/healthgate_unified.db",
    question_count: int = 50000,
    chemin_csv: str | None = None,
) -> pd.DataFrame:
    """Génère le dataset et sauvegarde la base unifiee (CSV optionnel)."""
    os.makedirs("data", exist_ok=True)
    print(f"[HealthGate] Génération de {n} patients...")

    patients = []
    for i in range(n):
        patients.append(generer_patient(f"PT{i+1:05d}"))
        if (i + 1) % 10000 == 0:
            print(f"  {i+1}/{n} patients générés...")

    df = pd.DataFrame(patients)

    print(f"\n[INFO] Dimensions : {df.shape}")
    print("\n[INFO] Répartition ESI :")
    dist = df["esi_level"].value_counts().sort_index()
    for esi_lvl, nb in dist.items():
        barre = "█" * int(nb / n * 50)
        print(f"  ESI {esi_lvl} : {nb:>6} patients ({nb/n*100:.1f}%)  {barre}")

    print("\n[INFO] Corrélations médicales (validation) :")
    for esi_lvl in range(1, 6):
        sub = df[df["esi_level"] == esi_lvl]
        print(f"  ESI {esi_lvl} → Temp: {sub['temperature'].mean():.1f}°C | "
              f"FC: {sub['heart_rate'].mean():.0f} bpm | "
              f"SpO2: {sub['spo2'].mean():.1f}% | "
              f"TA: {sub['bp_systolic'].mean():.0f} mmHg")

    if chemin_csv:
        df.to_csv(chemin_csv, index=False)
        print(f"\n[OK] Dataset CSV sauvegarde → {chemin_csv}")

    questions = build_rows(question_count, seed=42)
    db_finale = build_unified_database(df, questions, db_path=db_path)
    print(f"[OK] Base unifiee sauvegardee → {db_finale}")
    return df


if __name__ == "__main__":
    df = generer_dataset(
        n=50000,
        db_path="data/healthgate_unified.db",
        question_count=50000,
        chemin_csv=None,
    )
    print("\n[APERÇU] 3 premiers patients :")
    cols = ["patient_id", "age", "esi_level", "diagnostic_probable",
            "temperature", "heart_rate", "spo2", "symptom_text"]
    print(df[cols].head(3).to_string())
