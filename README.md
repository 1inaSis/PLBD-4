# 🏥 HealthGate — Borne de Triage Médical Intelligent

> **Avertissement :** Projet académique — Centrale Casablanca | Groupe PLBD 4 | 2025-2026. 
> Système expérimental de triage automatisé pour les urgences.

---

## 📋 Description

**HealthGate** est une borne de triage médical intelligent conçue spécifiquement pour désengorger les salles d'urgences (avec un focus sur le contexte africain). Elle permet d’évaluer et de trier automatiquement les patients dès leur arrivée, sans intervention humaine, en moins de 2 minutes.

Le système croise les constantes vitales, une analyse de texte naturel (NLP) des symptômes et une série de questions interactives intelligentes pour prédire le niveau **ESI (Emergency Severity Index)** du patient sur une échelle de 1 (Critique) à 5 (Non-Urgent). Le patient est ensuite inséré dans une file d'attente dynamique gérée en temps réel, visible depuis la salle d'attente et les postes médecins.

---

## 🎯 Problème résolu

- Surcharge chronique des urgences.
- Absence de système de triage automatisé rapide.
- Processus administratif et clinique initial long (20 à 45 minutes en moyenne).
- Risque de détérioration de l'état clinique du patient faute de priorisation immédiate.

**Solution : Un triage algorithmique complet en moins de 2 minutes.**

---

## 🏗️ Architecture & Technologies

L'écosystème comprend deux volets principaux communicants :

1. **Le Backend / Frontend IA (PC Serveur ou Cloud)**
   - **Interface Utilisateur :** Streamlit (Python) pour une robustesse et un rendu rapide.
   - **UI/UX :** Design personnalisé en CSS/HTML intégré, inspiré du standard mondial médical (type *Bamboo Health*), assurant une sobriété, une lisibilité (Sora / JetBrains Mono) et un retour visuel ultra-rapide et clair.
   - **Machine Learning :** Random Forest Classifier entraîné sur +50 000 dossiers générés, intégrant un extracteur NLP pour les requêtes textuelles.

2. **Le Hardware (Borne Physique - Raspberry Pi 5)**
   - **Capteurs intégrés :** Caméra (OCR), Thermomètre DS18B20, Oxymètre MAX30102 (SpO2/FC), Tensiomètre (UART).

---

## 🔄 Flux complet de triage

1. **IDENTITÉ & SYMPTÔMES :**
   Le patient saisit son identité (ou scan sa carte) et décrit ses symptômes soit par texte libre (analysé par NLP) soit en touchant un schéma corporel interactif.
2. **MESURE DES CONSTANTES :**
   Saisie ou acquisition matérielle des données vitales (SpO2, Rythme cardiaque, Température, Tension). Des alertes visuelles claires informent de l'état (Normale, Alerte, Critique).
3. **QUESTIONNAIRE INTELLIGENT (Généré par l'IA) :**
   L'Intelligence Artificielle génère dynamiquement 2 à 5 questions interactives et *uniquement* pertinentes, basées sur les constantes et les mots-clés préalablement analysés.
4. **PRÉDICTION ESI (IA) :**
   Agrégation des données dans le Random Forest → Prédiction ESI, calcul du temps d'attente et du médecin attribué.
5. **DASHBOARDS TEMPS RÉEL :**
   La position du patient remonte sur l'écran "Salle d'Attente" (file d'attente) et sur l'écran du "Médecin" alertant d'une prise en charge urgente (ESI 1 ou 2).

---

## 🚀 Installation & Démarrage

### Prérequis
- Python 3.10 ou supérieur
- Pip et Git

### 1. Cloner le projet et installer les dépendances

```bash
git clone https://github.com/1inaSis/PLBD-4.git
cd PLBD-4/ml
pip install -r requirements.txt
```

*(Optionnel pour la reconnaissance de carte : Installer Tesseract OCR sur votre OS)*

### 2. Initialiser le modèle IA

Avant de lancer l'application, l'Intelligence Artificielle doit être entraînée sur les données médicales locales :

```bash
# Générer la base de données synthétique (50 000 patients)
python data_generator.py

# Entraîner le classifieur Random Forest
python model_trainer.py
```

### 3. Lancer l'application Hub (Streamlit)

Le frontal complet reliant Borne, Salle d'attente et Médecins a été migré sur Streamlit !

```bash
# Démarrer le serveur et les interfaces
python -m streamlit run app/main.py
```
*L'application sera accessible localement sur `http://localhost:8501`. Utilisez le menu latéral pour naviguer entre la Borne Patient, la Salle d'Attente et les profils Médecins.*

---

## 🧪 Tests

Lancez la batterie de tests prédictifs pour valider le comportement du pipeline IA :

```bash
python tests/test_predictions.py
```

Couverture :
- Moteur NLP et génération de variables
- Prédictions de gravité (ESI)
- Gestion de la file d'attente APQ-h
- Cohérence des questions ciblées

---

## 📁 Structure du Projet

```text
PLBD-4/
├── ml/
│   ├── app/                       # Application Streamlit principale
│   │   ├── main.py                # Point d'entrée Web
│   │   ├── pages/                 # Interfaces (Borne, Salle attente, Médecin)
│   │   ├── components/            # Composants UI (Formulaires, Corps humain)
│   │   └── utils/                 # État global et styles
│   ├── models/                    # Modèles entraînés (.pkl)
│   ├── templates/                 # Code source UI Bamboo Health (HTML/CSS/JS)
│   ├── data/                      # Jeux de données (patients_50000.csv)
│   ├── tests/                     # Scripts de validité CI/CD
│   ├── model_trainer.py           # Algorithme d'entraînement Machine Learning
│   ├── questions_moteur.py        # Moteur génération questions cliniques dynamiques
│   ├── nlp_extractor.py           # Extracteur de concepts médicaux (Texte)
│   ├── queue_manager.py           # Algorithme APQ-h de gestion de file d'attente
│   └── requirements.txt           # Dépendances Python
├── hardware/                      # Code de gestion des capteurs physiques Raspberry Pi
└── scanner/                       # Code lié à la reconnaissance MRZ et documents
```

---

## 🏫 Cadre & Auteurs

- **Institution :** Centrale Casablanca
- **Année :** 2025-2026
- **Groupe :** PLBD 4

---

## 📄 Licence

Projet académique — Centrale Casablanca 2025-2026. Tous droits réservés.
