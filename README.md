# ðŸ¥ HealthGate â€“ SystÃ¨me Intelligent de Triage et de Gestion de Flux Patient

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![React](https://img.shields.io/badge/React-18-61dafb.svg)
![Architecture](https://img.shields.io/badge/Architecture-Hybride-success.svg)
![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED.svg)

> **Projet d'IngÃ©nierie**
> 
> Une solution cyber-physique intÃ©grÃ©e combinant **Intelligence Artificielle (NLP & Machine Learning)**, **Edge Computing** et **Architecture Web** pour automatiser l'accueil, prÃ©-diagnostiquer les urgences et optimiser le flux des patients en milieu hospitalier.

## ðŸŒŸ PrÃ©sentation et Impact

La congestion des urgences est un enjeu critique de santÃ© publique. **HealthGate** adresse cette problÃ©matique Ã  travers un kiosque d'accueil autonome permettant :
- **Identification instantanÃ©e** via la lecture et l'extraction de documents officiels (Scanner MRZ / OCR).
- **Acquisition de donnÃ©es vitales** en temps rÃ©el grÃ¢ce Ã  l'intÃ©gration de capteurs biomÃ©dicaux (IoT).
- **PrÃ©-triage intelligent (IA)** analysant les symptÃ´mes dÃ©clarÃ©s (NLP) pour infÃ©rer un niveau d'urgence mÃ©dical (Score ESI de 1 Ã  5).
- **Routage et priorisation dynamiques** des files d'attente vers les terminaux du personnel soignant.

## ðŸ›ï¸ Architecture SystÃ¨me (Globale)

Le systÃ¨me repose sur une architecture distribuÃ©e (Microservices orientÃ©e Ã©vÃ©nements) garantissant une sÃ©paration claire entre les terminaux physiques, l'orchestration et le Machine Learning.

### 1. Composants SpÃ©cifiques

Le projet est divisÃ© en 5 modules principaux fonctionnant en synergie :

- ðŸ–¥ï¸ **`frontend/` (Vue Patient & Terminaux)** : L'interface utilisateur dÃ©veloppÃ©e en **React**.
- âš™ï¸ **`backend/` (CÅ“ur Serveur & API REST/WebSockets)** : Le cerveau de routage en **Python (Flask)**.
- ðŸ§  **`ml/` (Moteur Diagnostique IA)** : ModÃ¨le prÃ©dictif qui gÃ©nÃ¨re le score d'urgence (ESI) via **Scikit-Learn & NLTK (NLP)**. 
- ðŸ“¸ **`scanner/` (Identification OCR/Vision)** : Module de vision par ordinateur pour extraction de piÃ¨ces d'identitÃ© via reconnaissance MRZ.
- ðŸ”Œ **`hardware/` (Acquisition IOT Edge)** : Code embarquÃ© (Daemon Pi, Capteurs, Ã‰cran Nextion) pilotant la borne physique.

### 2. Architecture des Flux et Diagramme

Le parcours de donnÃ©es est le suivant :
1. **Identification et BiomÃ©trie** : Le hardware et le scanner remontent les donnÃ©es au backend central via API.
2. **Interaction Patient** : Le frontend (Kiosque) collecte les symptÃ´mes (texte / NLP) du patient.
3. **InfÃ©rence ML (Triage)** : Le backend envoie ces donnÃ©es au modÃ¨le ML qui retourne un score calculÃ© ESI.
4. **Mise Ã  Jour CentralisÃ©e** : Le systÃ¨me route le patient dans la base de donnÃ©es et synchronise les tableaux de bord temps rÃ©el (Files d'attente et Interface MÃ©decin).

```mermaid
graph TD
    subgraph Kiosque / Edge Computing
        A[Borne Interactive React] 
        C[Capteurs BiomÃ©dicaux & IoT] 
        D[Scanner d'IdentitÃ© OCR]
    end
    
    subgraph Infrastructure Centrale
        B(Backend Python / API & WebSockets)
        E[Moteur de Triage ESI & NLP]
        DB[(Base de DonnÃ©es UnifiÃ©e)]
    end
    
    subgraph Vues & Terminaux Web
        F[File d'Attente Dynamique]
        G[Dashboards MÃ©decins]
    end

    A <-->|REST / WebSockets| B
    C -->|GPIO / I2C / API| B
    D -->|RequÃªtes HTTP| B
    B <-->|RequÃªtes de prÃ©diction| E
    B <--> DB
    B -->|Temps RÃ©el| F
    B -->|Temps RÃ©el| G
```

## ðŸ› ï¸ PrÃ©requis Techniques

Pour dÃ©ployer le systÃ¨me en environnement :
- **Python** (v3.10+) avec `pip`
- **Node.js** (v16+) et `npm` (pour le frontend React)
- **Docker** et **Docker Compose**
- **Tesseract OCR** (module scan)
- PÃ©riphÃ©riques matÃ©riels optionnels pour le workflow complet (Pi, Capteurs).

## ðŸš€ DÃ©marrage Rapide

### Option 1 : DÃ©ploiement via Docker (RecommandÃ©)
L'ensemble de la stack peut Ãªtre montÃ© facilement via Docker Compose :
```bash
git clone https://github.com/votre-organisation/PLBD-4.git
cd PLBD-4
docker-compose up --build -d
```

### Option 2 : Lancement Local (DÃ©veloppement)

**1. Lancer le Backend & ML :**
```bash
cd backend
pip install -r requirements.txt
python app.py

cd ../ml
pip install -r requirements.txt
python predict_api.py
```

**2. Lancer le Frontend (React) :**
```bash
cd ../frontend
npm install
npm run dev
```

## ðŸ§ª Tests QA

```bash
pytest backend/tests/
cd ml && python -m unittest discover -s tests -p "test_*.py"
pytest scanner/tests/
```

