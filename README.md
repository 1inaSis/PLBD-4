
# HealthGate – Plateforme de Triage Intelligent

HealthGate est une solution de pré-triage médical pour fluidifier la prise en charge aux urgences. Elle combine OCR, NLP, collecte de constantes vitales, prédiction ESI (1 à 5), file d’attente dynamique et synchronisation temps réel entre borne patient, salle d’attente et interfaces médecin.

## Architecture du projet

- **ml/** : Serveur principal (Flask + Socket.IO), moteur de questions, modèle ESI, interfaces HTML
- **backend/** : API Python alternative (séparée du serveur principal ML)
- **frontend/** : Structure React (non connectée en production)
- **scanner/** : Pipeline OCR documentaire
- **hardware/** : Gestion des capteurs Raspberry Pi

## Installation et démarrage

### Prérequis
- Python 3.10+
- pip
- (Optionnel) Tesseract OCR pour le scan de documents

### Installation du module principal
```bash
cd ml
pip install -r requirements.txt
```

### Lancement du serveur principal
```bash
python predict_api.py
```

### Interfaces disponibles
- Borne patient : http://localhost:5000/
- Salle d’attente : http://localhost:5000/salle
- Médecin M1 : http://localhost:5000/medecin/M1
- Médecin M2 : http://localhost:5000/medecin/M2
- API santé : http://localhost:5000/api/sante

## API principale (module ml)
Voir le code pour la liste complète des endpoints REST et événements Socket.IO.

## Tests

Depuis `ml/` :
```bash
python -m unittest discover -s tests -p "test_*.py"
```
Autres suites :
- backend/tests/
- scanner/tests/

## Notes
- Les écrans borne/salle/médecin sont dans `ml/templates/`.
- Le dossier `frontend/` existe mais n’est pas encore branché comme interface principale.
- Le serveur fonctionne en mémoire pour la session patient et la gestion de file locale.

## Roadmap
1. Unifier backend et ml en une seule API de production
2. Brancher une base persistante unique
3. Connecter le frontend React comme UI officielle
4. Industrialiser la supervision (logs, auth, CI)

---
Pour aller plus loin : normalisation des endpoints, robustesse réseau, et script unique de lancement global.