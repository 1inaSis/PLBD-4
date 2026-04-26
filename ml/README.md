# HealthGate ML/API - README final

Projet HealthGate - Centrale Casablanca - PLBD 4 - 2025-2026

## 1. Objectif
HealthGate automatise le pre-triage des urgences avec:
- scan d'identite,
- capture des symptomes en texte libre,
- lecture des constantes vitales,
- prediction ESI (1 a 5),
- file d'attente dynamique APQ-h,
- synchronisation temps reel borne/salle/medecins.

## 2. Arborescence finale

```text
ml/
  capteurs_raspberry.py
  data_generator.py
  model_trainer.py
  nlp_extractor.py
  predict_api.py
  questions_moteur.py
  queue_manager.py
  scanner_cin.py
  README.md
  requirements.txt
  data/
    patients_50000.csv
  models/
    diagnostic_encoder.pkl
    feature_names.pkl
    random_forest_esi.pkl
    scaler.pkl
  templates/
    borne.html
    medecin.html
    salle_attente.html
  tests/
    test_predictions.py
```

## 3. Installation

### 3.1 Prerequis
- Python 3.10+
- pip
- (optionnel) Tesseract OCR pour le scan reel de CIN

### 3.2 Dependances
Depuis le dossier `ml`:

```bash
py -m pip install -r requirements.txt
```

## 4. Lancement

### 4.1 Entrainement modele (si necessaire)

```bash
py model_trainer.py
```

### 4.2 Demarrage serveur

```bash
py predict_api.py
```

Le serveur expose:
- borne patient: http://localhost:5000/
- salle d'attente: http://localhost:5000/salle
- medecin M1: http://localhost:5000/medecin/M1
- medecin M2: http://localhost:5000/medecin/M2
- sante API: http://localhost:5000/api/sante

## 5. API principale

### 5.1 Sante
- `GET /api/sante`

### 5.2 Parcours patient
- `POST /api/scanner`
- `POST /api/symptomes`
- `GET /api/constantes`
- `POST /api/constantes_from_pi`
- `POST /api/questions`
- `POST /api/questions_adaptatif`
- `POST /api/questions/reponses`
- `POST /api/triage`

### 5.3 File et suivi
- `GET /api/file`
- `GET /api/queue/<patient_id>`
- `GET /api/rapport/<patient_id>`
- `GET /api/alertes`
- `POST /api/alertes/<patient_id>/lue`

### 5.4 Actions medecin
- `GET /api/medecin/<medecin_id>`
- `POST /api/prise_en_charge`
- `POST /api/degradation`

## 6. WebSocket (Socket.IO)

Evenements emis par le serveur:
- `file_mise_a_jour`
- `alerte_critique`
- `triage_complete`
- `question_suivante`
- `constantes_recu`

Evenements recus cote serveur:
- `rejoindre_borne`
- `rejoindre_medecin`

## 7. Tests

Execution:

```bash
py -m unittest discover -s tests -p "test_*.py"
```

Couverture actuelle:
- extraction NLP,
- generation/encodage des questions,
- prediction ESI,
- file APQ-h,
- pipelines d'integration.

## 8. Notes implementation
- `model_trainer.py` expose aussi les alias requis par contrat: `charger_donnees`, `preparer_features`, `sauvegarder`.
- `questions_moteur.py` expose `detecter_flags` pour le pre-filtrage clinique.
- Les pages HTML sont dans `templates/` et consomment les APIs Flask + Socket.IO.

## 9. Verification finale executee
- `py -m unittest discover -s tests -p "test_*.py"` -> OK
- `py predict_api.py` -> demarrage serveur valide (sans crash au boot)
