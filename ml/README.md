# HealthGate — Guide de démarrage

**Projet HealthGate** | Centrale Casablanca | PLBD 4 | 2025-2026

---

## 🏗️ Architecture

```
RASPBERRY PI 5                     PC SERVEUR (Windows/Mac)
─────────────────                  ──────────────────────────
Caméra → scan CIN      ──WiFi──►  Flask + SocketIO (port 5000)
DS18B20 (température)             │
MAX30102 (SpO2/FC)                ├─ /           → Borne patient
Tensiomètre (UART)                ├─ /salle      → Écran TV salle d'attente
                                  ├─ /medecin/M1 → Dr. El Amrani
                                  └─ /medecin/M2 → Dr. Bensouda
```

---

## 🚀 Installation et démarrage

### 1. Prérequis

**Windows :** Installer Tesseract OCR
- Télécharger : https://github.com/UB-Mannheim/tesseract/wiki
- Cocher "French" et "Arabic" lors de l'installation
- Décommenter la ligne dans `scanner_cin.py` :
  ```python
  pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
  ```

**Mac :**
```bash
brew install tesseract tesseract-lang
```

### 2. Installer les dépendances Python
```bash
pip install -r requirements.txt
```

### 3. Entraîner le modèle (une seule fois)
```bash
python model_trainer.py
```

### 4. Lancer le serveur
```bash
python predict_api.py
```

### 5. Ouvrir les interfaces

Depuis n'importe quel PC/tablette sur le même WiFi :

| Interface | URL |
|-----------|-----|
| Borne patient | http://IP_DU_PC:5000/ |
| Salle d'attente (TV) | http://IP_DU_PC:5000/salle |
| Médecin 1 | http://IP_DU_PC:5000/medecin/M1 |
| Médecin 2 | http://IP_DU_PC:5000/medecin/M2 |

> **Trouver votre IP :** `ipconfig` (Windows) ou `ifconfig` (Mac/Linux)

---

## 📡 Connexion Raspberry Pi → Serveur

Sur le Raspberry Pi, envoyer les données des capteurs via :

```python
import requests

# Après lecture des capteurs
donnees = {
    "session_id":   "SCAN-ABC123",  # obtenu après le scan CIN
    "constantes": {
        "temperature":   37.2,
        "spo2":          97.5,
        "heart_rate":    78,
        "bp_systolic":   120,
        "bp_diastolic":  80,
    }
}

r = requests.post("http://IP_DU_PC:5000/api/triage", json=donnees)
print(r.json())
```

---

## 🔌 Câblage des capteurs (Raspberry Pi 5)

| Capteur | Connexion | Librairie |
|---------|-----------|-----------|
| DS18B20 (température) | GPIO 4 (1-Wire) + résistance 4.7kΩ vers 3.3V | `w1thermsensor` |
| MAX30102 (SpO2) | SDA=GPIO2, SCL=GPIO3 (I2C) | `max30102` |
| Tensiomètre | /dev/ttyUSB0 (UART via USB) | `pyserial` |

Installation sur Pi :
```bash
pip install RPi.GPIO w1thermsensor max30102 pyserial
sudo raspi-config  # Activer I2C et 1-Wire
```

---

## 🔄 Flux complet d'un patient

```
1. Patient arrive → Scan CIN (caméra)
   → nom, prénom, âge, sexe extraits automatiquement

2. Patient décrit ses symptômes (texte libre en français)
   → NLP extrait les features

3. Capteurs mesurent automatiquement :
   → Température + SpO2 + Tension artérielle

4. Modèle Random Forest prédit le niveau ESI (1 à 5)
   → Patient placé dans la file APQ-h

5. Médecin assigné (le moins chargé)
   → Rapport envoyé instantanément sur son interface

6. Écran salle d'attente mis à jour en temps réel
   → Position, temps d'attente, alertes

7. Médecin clique "Pris en charge"
   → Patient retiré de toutes les files automatiquement
```

---

## 📁 Structure du projet

```
healthgate/
├── predict_api.py          ← Serveur Flask principal
├── scanner_cin.py          ← OCR pièce d'identité
├── capteurs_raspberry.py   ← Lecture capteurs biomédicaux
├── nlp_extractor.py        ← Analyse NLP symptômes
├── model_trainer.py        ← Entraînement Random Forest
├── queue_manager.py        ← File d'attente APQ-h
├── data_generator.py       ← Génération données synthétiques
├── requirements.txt        ← Dépendances Python
├── data/
│   └── patients_50000.csv  ← Dataset d'entraînement
├── models/
│   ├── random_forest_esi.pkl
│   ├── scaler.pkl
│   └── feature_names.pkl
└── templates/
    ├── borne.html          ← Interface patient
    ├── salle_attente.html  ← Écran TV
    └── medecin.html        ← Interface médecin
```
