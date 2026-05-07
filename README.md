  HealthGate une Borne de Triage Médical Intelligent

> Système de triage automatisé pour les urgences africaines
> Centrale Casablanca | Groupe PLBD 4 | 2025-2026

---

  Description

HealthGate est une borne de triage médical intelligent conçue pour
les salles d'urgences africaines. Elle permet de trier automatiquement
les patients dès leur arrivée, sans intervention humaine, en moins de
2 minutes.

Le système prédit le niveau ESI (Emergency Severity Index) du patient
sur une échelle de 1 à 5, puis le place dans une file d'attente
dynamique qui se réajuste en temps réel.

---

  Problème résolu

- Surcharge chronique des urgences africaines
- Absence de système de triage automatisé
- Processus administratif long (20 à 45 minutes)
- Risque de détérioration faute de priorisation rapide

**Solution : Un triage algorithmique complet en moins de 2 minutes.**

---

 🏗️ Architecture

`
RASPBERRY PI 5                    PC SERVEUR (Windows/Mac)
──────────────────                ─────────────────────────
Caméra (OCR carte)   ──WiFi──►   Flask + SocketIO :5000
DS18B20 (temp)                        │
MAX30102 (SpO2/FC)                    ├─ /           Borne patient
Tensiomètre (UART)                    ├─ /salle      Salle d'attente TV
                                      ├─ /medecin/M1 Dr. El Amrani
                                      └─ /medecin/M2 Dr. Bensouda
`

---

 🔄 Flux complet d'un patient

`
1. SCAN CARTE D'IDENTITÉ
   Caméra → OCR Tesseract → nom, prénom, âge, sexe

2. DESCRIPTION DES SYMPTÔMES
   Texte libre en français → NLP extrait les features

3. MESURE AUTOMATIQUE DES CONSTANTES
   Capteurs → température + SpO2 + tension artérielle

4. QUESTIONS CIBLÉES INTELLIGENTES
   3 à 5 questions adaptées aux symptômes détectés
   Jamais de question hors sujet

5. PRÉDICTION ESI (Random Forest)
   Features : constantes + NLP + diagnostic + réponses questions
   → ESI 1 (critique) à ESI 5 (non urgent)

6. FILE D'ATTENTE APQ-h
   Score dynamique → médecin assigné → ticket numéroté
`

---

 🚀 Installation

### Prérequis
- Python 3.10+
- Git

### 1. Cloner le projet
bash
git clone https://github.com/1inaSis/PLBD-4.git
cd PLBD-4/ml
pip install -r requirements.txt
`

### 3. Installer Tesseract OCR

**Windows :**
- Télécharger : https://github.com/UB-Mannheim/tesseract/wiki
- Cocher French + Arabic pendant l'installation
- Décommenter dans scanner_cin.py :
`python
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
`

**Mac :**
bash
brew install tesseract tesseract-lang
`

---

## ▶️ Démarrage rapide

bash
# 1. Générer le dataset
python data_generator.py

# 2. Entraîner le modèle
python model_trainer.py

# 3. Lancer les tests
python tests/test_predictions.py

# 4. Lancer le serveur
python predict_api.py
`

---

## 🌐 Interfaces web

| Interface | URL | Description |
|-----------|-----|-------------|
| Borne patient | http://localhost:5000/ | Interface tactile patient |
| Salle d'attente | http://localhost:5000/salle | Écran TV temps réel |
| Médecin 1 | http://localhost:5000/medecin/M1 | Dr. El Amrani |
| Médecin 2 | http://localhost:5000/medecin/M2 | Dr. Bensouda |

> **Sur le réseau local :** remplacer localhost par l'IP du PC serveur
> Trouver votre IP : ipconfig (Windows) ou ifconfig (Mac)

---

## 🔌 Câblage Raspberry Pi

| Capteur | Broche Pi | Protocole | Librairie Python |
|---------|-----------|-----------|------------------|
| DS18B20 (température) | GPIO 4 | 1-Wire | w1thermsensor |
| MAX30102 (SpO2/FC) | GPIO 2+3 | I2C | max30102 |
| Tensiomètre | USB | UART | pyserial |
| Caméra | CSI | picamera2 | picamera2 |

**Activation sur Raspberry Pi :**
bash
pip install RPi.GPIO w1thermsensor max30102 pyserial picamera2
sudo raspi-config  # Activer I2C et 1-Wire
`

---

## 🧠 Modèle Machine Learning

| Paramètre | Valeur |
|-----------|--------|
| Algorithme | Random Forest |
| Nombre d'arbres | 300 |
| Dataset | 50 000 patients |
| Features | 29+ |
| Cross-validation | 10-fold stratifiée |
| Accuracy | À compléter après entraînement |

### Features du modèle :
- **Constantes vitales :** température, FC, TA, SpO2, FR, glycémie
- **Symptômes binaires :** douleur thoracique, dyspnée, etc.
- **Features NLP :** extraites du texte libre du patient
- **Diagnostic probable :** encodé numériquement
- **Réponses questions ciblées :** features q_*

### Pathologies couvertes :
Paludisme, Typhoïde, Tuberculose, Drépanocytose, Infarctus,
AVC, Méningite, Appendicite, Éclampsie, Pneumonie, et 38 autres.

---

## 📊 API REST

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | /api/scanner | Scan pièce d'identité |
| POST | /api/symptomes | Enregistrer symptômes |
| GET | /api/constantes | Lire capteurs |
| POST | /api/questions | Générer questions |
| POST | /api/triage | Prédire ESI + file |
| GET | /api/file | État file d'attente |
| POST | /api/prise_en_charge | Médecin prend en charge |
| GET | /api/medecin/<id> | Patients du médecin |
| GET | /api/sante | Vérification API |

---

## 🧪 Tests

bash
python tests/test_predictions.py
`

Tests couverts :
- Module NLP (extraction features)
- Modèle Random Forest (prédiction ESI)
- File d'attente APQ-h (ajout, tri, dégradation, alertes)
- Questions ciblées (cohérence, types, nombre)
- Intégration complète (pipeline bout en bout)

---

## 📁 Structure du projet

`
ml/
├── data/
│   └── patients_50000.csv
├── models/
│   ├── random_forest_esi.pkl
│   ├── scaler.pkl
│   ├── feature_names.pkl
│   └── diagnostic_encoder.pkl
├── templates/
│   ├── borne.html
│   ├── salle_attente.html
│   └── medecin.html
├── tests/
│   └── test_predictions.py
├── data_generator.py
├── nlp_extractor.py
├── model_trainer.py
├── questions_moteur.py
├── queue_manager.py
├── predict_api.py
├── scanner_cin.py
├── capteurs_raspberry.py
└── requirements.txt
`
---

## 🏫 Encadrement

| | |
|--|--|
| **École** | Centrale Casablanca |
| **Groupe** | PLBD 4 |
| **Année** | 2025-2026 |


---

## 📄 Licence

Projet académique — Centrale Casablanca 2025-2026. Tous droits réservés.

---

<div align="center">
Fait avec ❤️ pour améliorer les urgences africaines
</div>
