# ?? HealthGate � Borne de Triage M�dical Intelligent

> **Avertissement :** Projet acad�mique � Centrale Casablanca | Groupe PLBD 4 | 2025-2026. 
> Syst�me exp�rimental de triage automatis� pour les urgences.

---

## ?? Description

**HealthGate** est une borne de triage m�dical intelligent con�ue sp�cifiquement pour d�sengorger les salles d'urgences (avec un focus sur le contexte africain). Elle permet d��valuer et de trier automatiquement les patients d�s leur arriv�e, sans intervention humaine, en moins de 2 minutes.

Le syst�me croise les constantes vitales, une analyse de texte naturel (NLP) des sympt�mes et une s�rie de questions interactives intelligentes pour pr�dire le niveau **ESI (Emergency Severity Index)** du patient sur une �chelle de 1 (Critique) � 5 (Non-Urgent). Le patient est ensuite ins�r� dans une file d'attente dynamique g�r�e en temps r�el, visible depuis la salle d'attente et les postes m�decins.

---

## ?? Probl�me r�solu

- Surcharge chronique des urgences.
- Absence de syst�me de triage automatis� rapide.
- Processus administratif et clinique initial long (20 � 45 minutes en moyenne).
- Risque de d�t�rioration de l'�tat clinique du patient faute de priorisation imm�diate.

**Solution : Un triage algorithmique complet en moins de 2 minutes.**

---

## ??? Architecture & Technologies

L'�cosyst�me comprend deux volets principaux communicants :

1. **Le Backend / Frontend IA (PC Serveur ou Cloud)**
   - **Interface Utilisateur :** Streamlit (Python) pour une robustesse et un rendu rapide.
   - **UI/UX :** Design personnalis� en CSS/HTML int�gr�, inspir� du standard mondial m�dical (type *Bamboo Health*), assurant une sobri�t�, une lisibilit� (Sora / JetBrains Mono) et un retour visuel ultra-rapide et clair.
   - **Machine Learning :** Random Forest Classifier entra�n� sur +50 000 dossiers g�n�r�s, int�grant un extracteur NLP pour les requ�tes textuelles.

2. **Le Hardware (Borne Physique - Raspberry Pi 5)**
   - **Capteurs int�gr�s :** Cam�ra (OCR), Thermom�tre DS18B20, Oxym�tre MAX30102 (SpO2/FC), Tensiom�tre (UART).

---

## ?? Flux complet de triage

1. **IDENTIT� & SYMPT�MES :**
   Le patient saisit son identit� (ou scan sa carte) et d�crit ses sympt�mes soit par texte libre (analys� par NLP) soit en touchant un sch�ma corporel interactif.
2. **MESURE DES CONSTANTES :**
   Saisie ou acquisition mat�rielle des donn�es vitales (SpO2, Rythme cardiaque, Temp�rature, Tension). Des alertes visuelles claires informent de l'�tat (Normale, Alerte, Critique).
3. **QUESTIONNAIRE INTELLIGENT (Généré par l'IA) :**
   L'Intelligence Artificielle génère dynamiquement 2 à 5 questions interactives et *uniquement* pertinentes, basées sur les constantes et les mots-clés préalablement analysés.
4. **PR�DICTION ESI (IA) :**
   Agr�gation des donn�es dans le Random Forest ? Pr�diction ESI, calcul du temps d'attente et du m�decin attribu�.
5. **DASHBOARDS TEMPS R�EL :**
   La position du patient remonte sur l'�cran "Salle d'Attente" (file d'attente) et sur l'�cran du "M�decin" alertant d'une prise en charge urgente (ESI 1 ou 2).

---

## ?? Installation & D�marrage

### Pr�requis
- Python 3.10 ou sup�rieur
- Pip et Git

### 1. Cloner le projet et installer les d�pendances

\\\ash
git clone https://github.com/1inaSis/PLBD-4.git
cd PLBD-4/ml
pip install -r requirements.txt
\\\

*(Optionnel pour la reconnaissance de carte : Installer Tesseract OCR sur votre OS)*

### 2. Initialiser le mod�le IA

Avant de lancer l'application, l'Intelligence Artificielle doit �tre entra�n�e sur les donn�es m�dicales locales :

\\\ash
# G�n�rer la base de donn�es synth�tique (50 000 patients)
python data_generator.py

# Entra�ner le classifieur Random Forest
python model_trainer.py
\\\

### 3. Lancer l'application Hub (Streamlit)

Le frontal complet reliant Borne, Salle d'attente et M�decins a �t� migr� sur Streamlit !

\\\ash
# D�marrer le serveur et les interfaces
python -m streamlit run app/main.py
\\\
*L'application sera accessible localement sur \http://localhost:8501\. Utilisez le menu lat�ral pour naviguer entre la Borne Patient, la Salle d'Attente et les profils M�decins.*

---

## ?? Tests

Lancez la batterie de tests pr�dictifs pour valider le comportement du pipeline IA :

\\\ash
python tests/test_predictions.py
\\\

Couverture :
- Moteur NLP et g�n�ration de variables
- Pr�dictions de gravit� (ESI)
- Gestion de la file d'attente APQ-h
- Coh�rence des questions cibl�es

---

## ?? Structure du Projet

\\\	ext
PLBD-4/
+-- ml/
�   +-- app/                       # Application Streamlit principale
�   �   +-- main.py                # Point d'entr�e Web
�   �   +-- pages/                 # Interfaces (Borne, Salle attente, M�decin)
�   �   +-- components/            # Composants UI (Formulaires, Corps humain)
�   �   +-- utils/                 # �tat global et styles
�   +-- models/                    # Mod�les entra�n�s (.pkl)
�   +-- templates/                 # Code source UI Bamboo Health (HTML/CSS/JS)
�   +-- data/                      # Jeux de donn�es (patients_50000.csv)
�   +-- tests/                     # Scripts de validit� CI/CD
�   +-- model_trainer.py           # Algorithme d'entra�nement Machine Learning
�   +-- questions_moteur.py        # Moteur g�n�ration questions cliniques dynamiques
�   +-- nlp_extractor.py           # Extracteur de concepts m�dicaux (Texte)
�   +-- queue_manager.py           # Algorithme APQ-h de gestion de file d'attente
�   +-- requirements.txt           # D�pendances Python
+-- hardware/                      # Code de gestion des capteurs physiques Raspberry Pi
+-- scanner/                       # Code li� � la reconnaissance MRZ et documents
\\\

---

## ?? Cadre & Auteurs

- **Institution :** Centrale Casablanca
- **Ann�e :** 2025-2026
- **Groupe :** PLBD 4

---

## ?? Licence

Projet acad�mique � Centrale Casablanca 2025-2026. Tous droits r�serv�s.
