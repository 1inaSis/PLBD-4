# HealthGate - Plateforme de Triage Intelligent

HealthGate est un systeme de pre-triage medical concu pour fluidifier la prise en charge aux urgences.
Le projet combine OCR, NLP, collecte de constantes vitales, prediction ESI (1 a 5), file d'attente dynamique,
et synchronisation temps reel entre borne patient, salle d'attente et interfaces medecin.

## 1. Etat du projet

- Statut: prototype fonctionnel multi-modules
- Annee: PLBD4 2025-2026
- Coeur runtime actuel: `ml/predict_api.py` (Flask + Socket.IO + templates HTML)

## 2. Architecture du depot

Le depot contient plusieurs briques, dont certaines sont alternatives ou experimentales:

- `ml/`: serveur principal, moteur questions, modele ESI, interfaces HTML actives
- `backend/`: API Python alternative (separee du serveur principal ML)
- `frontend/`: structure React (actuellement non alimentee dans ce depot)
- `scanner/`: pipeline OCR documentaire plus detaille
- `hardware/`: gestion capteurs Raspberry Pi

En pratique, pour demontrer le flux complet de triage, utilisez d'abord `ml/`.

## 3. Demarrage rapide (voie recommandee)

### 3.1 Prerequis

- Python 3.10+
- pip
- Optionnel: Tesseract OCR (scan reel des documents)

### 3.2 Installation

```bash
cd ml
py -m pip install -r requirements.txt
```

### 3.3 Lancement serveur

```bash
py predict_api.py
```

### 3.4 Interfaces disponibles

- Borne patient: http://localhost:5000/
- Salle d'attente: http://localhost:5000/salle
- Medecin M1: http://localhost:5000/medecin/M1
- Medecin M2: http://localhost:5000/medecin/M2
- Sante API: http://localhost:5000/api/sante

## 4. Flux fonctionnel

1. Scan identite (ou mode manuel)
2. Saisie symptomes en texte libre
3. Lecture constantes vitales
4. Generation de questions ciblees
5. Soumission des reponses
6. Prediction ESI et attribution medecin
7. Publication dans file d'attente avec mise a jour temps reel

## 5. API principale (module ml)

### 5.1 Systeme

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

### 5.3 Queue et supervision

- `GET /api/file`
- `GET /api/queue/<patient_id>`
- `GET /api/rapport/<patient_id>`
- `GET /api/alertes`
- `POST /api/alertes/<patient_id>/lue`

### 5.4 Actions medecin

- `GET /api/medecin/<medecin_id>`
- `POST /api/prise_en_charge`
- `POST /api/degradation`

## 6. Evenements Socket.IO

### 6.1 Evenements emis par le serveur

- `file_mise_a_jour`
- `alerte_critique`
- `triage_complete`
- `question_suivante`
- `constantes_recu`

### 6.2 Evenements recus cote serveur

- `rejoindre_borne`
- `rejoindre_medecin`

## 7. Donnees et modele

- Modele de prediction ESI entraine via `ml/model_trainer.py`
- Banque de questions medicales via `ml/questions_moteur.py`
- Base unifiee possible via `ml/build_unified_database.py`

Fichiers de modele attendus dans `ml/models/`:

- `random_forest_esi.pkl`
- `scaler.pkl`
- `feature_names.pkl`

## 8. Tests

Depuis `ml/`:

```bash
py -m unittest discover -s tests -p "test_*.py"
```

Autres suites presentes:

- `backend/tests/`
- `scanner/tests/`

## 9. Notes importantes

- Les ecrans borne/salle/medecin utilises en execution sont les templates HTML de `ml/templates/`.
- Le dossier `frontend/` existe mais n'est pas encore branche comme interface runtime principale.
- Le serveur actuel fonctionne en memoire pour la session patient (`patients_session`) et en gestion de file locale.

## 10. Roadmap de consolidation

1. Unifier `backend/` et `ml/` en une seule API de production.
2. Brancher une base persistante unique pour sessions, file et rapports.
3. Connecter le frontend React comme UI officielle.
4. Industrialiser la supervision (logs, auth, traces, CI).

---

Si vous souhaitez, la prochaine etape peut etre un vrai "hardening" de fin de projet:
normalisation des endpoints, checks de robustesse reseau, et script unique de lancement global.