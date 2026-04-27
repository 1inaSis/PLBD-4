# 🏥 HealthGate – Système Intelligent de Triage et de Gestion de Flux Patient

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![React](https://img.shields.io/badge/React-18-61dafb.svg)
![Architecture](https://img.shields.io/badge/Architecture-Hybride-success.svg)
![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED.svg)

> **Projet d'Ingénierie**
> 
> Une solution cyber-physique intégrée combinant **Intelligence Artificielle (NLP & Machine Learning)**, **Edge Computing** et **Architecture Web** pour automatiser l'accueil, pré-diagnostiquer les urgences et optimiser le flux des patients en milieu hospitalier.

## 🌟 Présentation et Impact

La congestion des urgences est un enjeu critique de santé publique. **HealthGate** adresse cette problématique à travers un kiosque d'accueil autonome permettant :
- **Identification instantanée** via la lecture et l'extraction de documents officiels (Scanner MRZ / OCR).
- **Acquisition de données vitales** en temps réel grâce à l'intégration de capteurs biomédicaux (IoT).
- **Pré-triage intelligent (IA)** analysant les symptômes déclarés (NLP) et les biométries pour inférer un niveau d'urgence médical (Score ESI de 1 à 5).
- **Routage et priorisation dynamiques** des files d'attente vers les terminaux du personnel soignant.

## 🏗️ Architecture Système 

Le système repose sur une architecture modulaire (Microservices) garantissant une séparation claire entre les composants physiques et logiciels. Le projet est divisé en 5 modules principaux :

- 🖥️ **rontend/** : L'interface utilisateur de la borne et des écrans d'affichage développée en **React**.
- ⚙️ **ackend/** : Le cerveau central en **Python** exposant des API REST et gérant la synchronisation WebSocket.
- 🧠 **ml/** : Le moteur d'Intelligence Artificielle de prédiction d'urgence et ses modèles d'apprentissage.
- 📸 **scanner/** : Le module de vision par ordinateur pour l'extraction OCR des pièces d'identité (MRZ).
- 🔌 **hardware/** : Le code embarqué (Raspberry Pi, Capteurs, Écran HMI Nextion) pilotant la borne physique.

`mermaid
graph TD
    subgraph Kiosque / Edge Computing
        A[Borne Interactive React] 
        C[Capteurs Biomédicaux & IoT] 
        D[Scanner d'Identité OCR]
    end
    
    subgraph Cœur du Système
        B(Backend Python / API & WebSockets)
        E[Moteur de Triage IA & NLP]
        DB[(Base de Données Unifiée)]
    end
    
    subgraph Vues & Terminaux
        F[Écran File d'Attente]
        G[Dashboards Médicaux]
    end

    A <-->|REST / WebSockets| B
    C -->|GPIO / I2C / API| B
    D -->|HTTP REST| B
    B <-->|Requêtes de prédiction| E
    B <--> DB
    B -->|Temps Réel| F
    B -->|Temps Réel| G
`

## 🛠️ Prérequis Techniques

Pour déployer le système en environnement de développement ou de production :
- **Python** (v3.10+) avec pip
- **Node.js** (v16+) et 
pm (pour le frontend React)
- **Docker** et **Docker Compose** (pour un déploiement orchestré)
- **Tesseract OCR** (installé sur la machine hôte pour le module de scan)
- Périphériques matériels optionnels pour le workflow complet (Raspberry Pi, Capteurs).

## 🚀 Démarrage Rapide

### Option 1 : Déploiement via Docker (Recommandé pour la prod)
L'ensemble de la stack peut être monté facilement via Docker Compose :
`ash
git clone https://github.com/votre-organisation/PLBD-4.git
cd PLBD-4
docker-compose up --build -d
`

### Option 2 : Lancement Local (Développement)

**1. Lancer le Backend & ML :**
`ash
# Dans un premier terminal
cd backend
pip install -r requirements.txt
python app.py

# Dans un second terminal, lancer l'API ML
cd ../ml
pip install -r requirements.txt
python predict_api.py
`

**2. Lancer le Frontend (React) :**
`ash
# Dans un troisième terminal
cd frontend
npm install
npm run dev
`

## 🧪 Tests et Assurance Qualité

Le projet intègre des suites de tests automatisés pour valider les composants critiques.

`ash
# Tests du backend et moteur de triage
pytest backend/tests/

# Tests du moteur de prédiction ML
cd ml && python -m unittest discover -s tests -p "test_*.py"

# Tests du pipeline de scan de documents
pytest scanner/tests/
`

## 🛣️ Roadmap Évolutive
1. **Unification Backend :** Consolidation finale du Backend transactionnel et de l'API ML prédictive.
2. **Dashboard Analytics :** Ajout de statistiques avancées pour les administrateurs de l'hôpital.
3. **Déploiement Continu :** Mise en place d'une pipeline CI/CD complète.
