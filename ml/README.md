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
  build_unified_database.py
  capteurs_raspberry.py
  data_generator.py
  question_bank_generator.py
  model_trainer.py
  nlp_extractor.py
  predict_api.py
  questions_moteur.py
  queue_manager.py
  scanner_cin.py
  README.md
  unified_data_store.py
  requirements.txt
  data/
    healthgate_unified.db
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

### 4.1 Base de donnees unifiee (patients + questions)

Construire la base unique depuis les donnees existantes:

```bash
py data_generator.py
```

La base `data/healthgate_unified.db` contient:
- table `patients` (dataset d'entrainement),
- table `question_bank` (banque des 50k questions),
- table `patient_question_responses` (historique exploitable).

Ouvrir rapidement la base avec SQLite CLI:

```bash
sqlite3 data/healthgate_unified.db ".tables"
```

### 4.2 Entrainement modele (si necessaire)

```bash
py model_trainer.py
```

`model_trainer.py` charge en priorite la table `patients` de la base unifiee.

### 4.3 Regeneration de la banque de 50 000 questions

```bash
py build_unified_database.py --patients-csv data/patients_50000.csv --question-count 50000 --db-out data/healthgate_unified.db
```

Cette commande est utile si vous avez un CSV patient externe a convertir vers la base unifiee.

### 4.4 Lien avec l'entrainement du modele

Le modele ESI est entraine sur des features structurees (constantes, NLP, reponses encodees),
pas directement sur le texte brut des questions. La banque de 50 000 questions ameliore la
diversite du dialogue patient et la qualite des reponses, puis `encoder_reponses()` transforme
ces reponses en features exploitables par `model_trainer.py`.

### 4.5 Demarrage serveur

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
- `questions_moteur.py` charge en priorite `question_bank` depuis `data/healthgate_unified.db`.
- Les pages HTML sont dans `templates/` et consomment les APIs Flask + Socket.IO.

## 9. Systeme de questions ciblees intelligentes

Après la mesure des constantes vitales, la borne pose entre 3 et 5 questions adaptées uniquement aux symptômes décrits par le patient.

### Logique de fonctionnement
1. Analyse du texte libre du patient par mots-clés.
2. Analyse des constantes vitales anormales.
3. Prise en compte de l'âge et du sexe.
4. Sélection des catégories réellement liées au cas.
5. Retour de questions cohérentes avec leur type de réponse.

### Types de questions
- `oui_non` pour les questions fermées de type confirmation ou présence de signe.
- `choix` pour les durées, localisations, mécanismes ou niveaux d'intensité.
- Aucune question ouverte n'est affichée avec une réponse `oui_non`.

### Exemples
Patient avec douleur thoracique:
- La douleur irradie-t-elle vers le bras gauche ou la mâchoire ? [OUI/NON]
- La douleur est-elle apparue au repos ou pendant un effort ? [CHOIX]
- Avez-vous déjà eu un infarctus ou une maladie du coeur ? [OUI/NON]

Patient avec trauma au pied:
- Avez-vous entendu un craquement au moment de la blessure ? [OUI/NON]
- Pouvez-vous poser le pied par terre ou bouger la partie blessée ? [OUI/NON]
- Le membre est-il gonflé ou déformé ? [OUI/NON]

### Règles jamais transgressées
- Pas de question grossesse pour un homme.
- Pas de question pédiatrie pour un adulte sans contexte enfant.
- Pas de question cardiaque pour une chute simple sans symptôme associé.
- Pas de question ouverte avec une réponse oui/non.

### Données et diversité
- Le moteur peut s'appuyer sur la banque de questions unifiée dans `healthgate_unified.db` pour diversifier les formulations.
- Le socle métier reste la banque stricte de catégories cliniques dans `questions_moteur.py`.

## 10. Verification finale executee
- `py -m unittest discover -s tests -p "test_*.py"` -> OK
- `py predict_api.py` -> demarrage serveur valide (sans crash au boot)
