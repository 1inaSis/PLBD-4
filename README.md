# ?? HealthGate – Système Intelligent de Triage et de Gestion de Flux Patient

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![React](https://img.shields.io/badge/React-18-61dafb.svg)
![Architecture](https://img.shields.io/badge/Architecture-Hybride-success.svg)
![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED.svg)

> **Projet d'Ingénierie - École Centrale Casablanca**
> 
> Une solution cyber-physique intégrée combinant **Intelligence Artificielle (NLP & Machine Learning)**, **Edge Computing** et **Architecture Web** pour automatiser l'accueil, pré-diagnostiquer les urgences et optimiser le flux des patients en milieu hospitalier.

## ?? Présentation et Impact

La congestion des urgences est un enjeu critique de santé publique. **HealthGate** adresse cette problématique à travers un kiosque d'accueil autonome permettant :
- **Identification instantanée** via la lecture et l'extraction de documents officiels (Scanner MRZ / OCR).
- **Acquisition de données vitales** en temps réel grâce à l'intégration de capteurs biomédicaux matériels.
- **Pré-triage intelligent (IA)** analysant les symptômes déclarés (NLP) et les biométries pour inférer un niveau d'urgence médical (ESI 1 à 5).
- **Routage et priorisation dynamiques** des files d'attente vers les terminaux du personnel soignant (médecins M1, M2).

## ??? Architecture Système 

Le système repose sur une architecture modulaire garantissant un couplage lâche entre les composants physiques et logiciels.

\\\mermaid
graph TD
    subgraph Edge Computing / Hardware
        A[Borne Interactive & Interfaces HTML] 
        C[Capteurs Biomédicaux Pi] 
        D[Pipeline OCR Documentaire]
    end
    
    subgraph Core & Intelligence Artificielle
        B(Serveur Principal ML / Backend - Flask & Socket.IO)
        E[Moteur Inférence ESI & NLP]
    end
    
    subgraph Vues & Terminaux
        F[Salle d'attente dynamique]
        G[Dashboards Médecins]
    end

    A -->|REST/WebSockets| B
    C -->|GPIO/I2C| B
    D -->|HTTP| B
    B <--> E
    B -->|Temps Réel| F
    B -->|Temps Réel| G
\\\

## ?? Prérequis Techniques

Pour déployer le système en environnement de développement ou de production :
- **Python** (v3.10+) avec \pip\
- **Docker** et **Docker Compose** (pour un déploiement orchestré)
- **Tesseract OCR** (pour le module de scan de documents)
- Périphériques matériels optionnels pour le workflow complet (Raspberry Pi, Capteurs).

## ?? Quick Start

Le flux principal est actuellement orchestré autour du moteur ML intelligent.

### Option 1 : Déploiement Docker (Recommandé)
\\\ash
git clone https://github.com/votre-organisation/PLBD-4.git
cd PLBD-4
docker-compose up --build -d
\\\

### Option 2 : Lancement Local (Environnement Virtuel)
\\\ash
cd ml
pip install -r requirements.txt
python predict_api.py
\\\

**Interfaces disponibles via le serveur principal :**
- **Borne Patient** : [http://localhost:5000/](http://localhost:5000/)
- **Dashboard Salle d'attente** : [http://localhost:5000/salle](http://localhost:5000/salle)
- **Interface Médecin M1** : [http://localhost:5000/medecin/M1](http://localhost:5000/medecin/M1)

## ?? Tests et Assurance Qualité

Le projet intègre des suites de tests unitaires pour valider les composants critiques.

\\\ash
# Tests du moteur de prédiction et de l'orchestrateur ML
cd ml && python -m unittest discover -s tests -p "test_*.py"

# Autres suites disponibles
pytest backend/tests/
pytest scanner/tests/
\\\

## ??? Roadmap Évolutive
Dans une optique d'industrialisation continue (Clean Architecture) :
1. Unification complète du *Backend* transactionnel et de l'*API ML* prédictive.
2. Bascule complète de la présentation sur la stack **React** (\rontend/\).
3. Déploiement continu (CI/CD) et intégration d'une persistance de données distribuée.

---
*Conçu avec rigueur et ingéniosité dans le cadre des cursus d'ingénierie de l'École Centrale Casablanca.*
