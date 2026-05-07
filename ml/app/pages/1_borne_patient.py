import streamlit as st
import sys
import os
# Ajouter le dossier courant (ml/app) au sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from components.corps_humain import afficher_corps_humain
from components.constantes_form import formulaire_constantes
from components.questions_ui import afficher_questions
from utils.state import ajouter_patient
from model_trainer import predire_esi
# removed


def afficher_progression(etape, etapes):
    st.progress(etape / len(etapes))
    
def afficher_resultat_triage():
    st.success("Triage complété. Veuillez patienter dans la salle d'attente.")

def page_borne():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from app.utils.styles import injecter_css, afficher_header, afficher_sidebar

    injecter_css()
    afficher_sidebar()
    afficher_header("HealthGate")

    # Initialiser l'état
    if "etape" not in st.session_state:
        st.session_state.etape = 1

    # Barre de progression
    etapes = ["Identité", "Symptômes", "Corps", "Constantes", "Questions", "Résultat"]
    afficher_progression(st.session_state.etape, etapes)

    # ── ÉTAPE 1 — IDENTITÉ (SAISIE MANUELLE) ──────────────────────
    if st.session_state.etape == 1:
        st.markdown("### 👤 Informations du patient")
        st.info("Saisissez les informations directement — le scan de carte sera disponible prochainement.")

        col1, col2 = st.columns(2)
        with col1:
            nom    = st.text_input("Nom de famille", placeholder="Ex : Alaoui")
            age    = st.number_input("Âge", min_value=0, max_value=120, value=30)
        with col2:
            prenom = st.text_input("Prénom", placeholder="Ex : Mohamed")
            sexe   = st.radio("Sexe", ["Homme", "Femme"], horizontal=True)

        if st.button("✅ Confirmer l'identité", use_container_width=True):
            if nom and prenom:
                st.session_state.patient = {
                    "nom": nom, "prenom": prenom,
                    "age": age, "sex": 1 if sexe == "Homme" else 0
                }
                st.session_state.etape = 2
                st.rerun()
            else:
                st.error("Veuillez remplir le nom et le prénom.")

    # ── ÉTAPE 2 — SYMPTÔMES ───────────────────────────────────────
    elif st.session_state.etape == 2:
        st.markdown("### 💬 Comment vous sentez-vous ?")

        methode = st.radio(
            "Comment souhaitez-vous décrire vos symptômes ?",
            ["✍️ Écrire mes symptômes", "🫀 Cliquer sur le corps humain"],
            horizontal=True
        )

        if "✍️" in methode:
            texte = st.text_area(
                "Décrivez vos symptômes en quelques mots",
                placeholder="Ex : J'ai très mal à la poitrine depuis ce matin...",
                height=120
            )
            if st.button("➡️ Continuer", use_container_width=True):
                if texte.strip():
                    st.session_state.symptom_text = texte
                    st.session_state.etape = 3
                    st.rerun()

        else:
            # Corps humain cliquable
            zone_cliquee = afficher_corps_humain()
            if zone_cliquee:
                st.session_state.zone_douloureuse = zone_cliquee
                st.session_state.symptom_text = f"Douleur dans la zone : {zone_cliquee}"
                st.session_state.etape = 3
                st.rerun()

    # ── ÉTAPE 3 — CONSTANTES VITALES (SAISIE MANUELLE) ───────────
    elif st.session_state.etape == 3:
        st.markdown("### 🩺 Constantes vitales")
        st.info("Saisissez les valeurs mesurées. Les capteurs automatiques seront connectés prochainement.")

        constantes = formulaire_constantes()

        if st.button("➡️ Continuer vers les questions", use_container_width=True):
            st.session_state.constantes = constantes
            st.session_state.etape = 4
            st.rerun()

    # ── ÉTAPE 4 — QUESTIONS CIBLÉES ──────────────────────────────
    elif st.session_state.etape == 4:
        st.markdown("### ❓ Questions rapides")
        st.caption("Ces questions nous aident à mieux évaluer votre état.")

        reponses = afficher_questions(
            st.session_state.constantes,
            st.session_state.symptom_text,
            st.session_state.patient["age"],
            st.session_state.patient["sex"]
        )

        if reponses is not None:
            st.session_state.reponses_questions = reponses
            st.session_state.etape = 5
            st.rerun()

    # ── ÉTAPE 5 — RÉSULTAT ───────────────────────────────────────
    elif st.session_state.etape == 5:
        # Build the dictionary for predire_esi
        # Convert responses back to binary flags format required by the model
        features_questions = st.session_state.reponses_questions
        
        # Build dictionary just like the API does
        d = {
            "age": st.session_state.patient["age"],
            "sex": st.session_state.patient["sex"],
            "symptom_text": st.session_state.symptom_text,
            "questions": st.session_state.questions_generees,
            "question_reponses": st.session_state.reponses_questions
        }
        
        # Add the vital signs from the manual inputs properly mapped
        constantes = st.session_state.constantes
        d["temperature"] = constantes.get("temperature", 37.0)
        d["heart_rate"] = constantes.get("heart_rate", 75)
        d["bp_systolic"] = constantes.get("bp_systolic", 120)
        d["bp_diastolic"] = constantes.get("bp_diastolic", 80)
        d["spo2"] = constantes.get("spo2", 98.0)
        
        # Additional features that might be generated directly
        d["douleur"] = 1 if (features_questions.get("q_douleur_repos_effort") or features_questions.get("q_douleur_irradiee_bras") or constantes.get("pain_score", 0)) else 0
        d["dyspnea"] = 1 if (features_questions.get("q_dyspnee_aggrave_effort") or features_questions.get("q_duree_dyspnee")) else 0
        d["dyspnea_aggrave_effort"] = 1 if features_questions.get("q_dyspnee_aggrave_effort") else 0
        d["chest_pain"] = 1 if features_questions.get("q_douleur_irradiee_bras") else 0
        d["loss_of_consciousness"] = 1 if features_questions.get("q_trauma_perte_conscience") else 0
        d["severe_bleeding"] = 1 if features_questions.get("q_trauma_saignement") else 0
        d["neurological_symptoms"] = 1 if (features_questions.get("q_neuro_faiblesse") or features_questions.get("q_neuro_parole") or features_questions.get("q_neuro_confusion")) else 0
        d["abdominal_pain"] = 1 if features_questions.get("q_localisation_abdomen") else 0
        d["fever"] = 1 if features_questions.get("q_duree_fievre") else 0
        d["trauma"] = 1 if features_questions.get("q_trauma_zone") else 0

        with st.spinner("Analyse de votre état par l'IA..."):
            try:
                resultat = predire_esi(d)
                esi = int(resultat.get("esi_predit", 3))
                diagnostic = resultat.get("diagnostic_probable", "Évaluation clinique complémentaire requise")
                confiance = resultat.get("confiance", 0)
                
                niveaux = {
                    1: ("🔴 URGENCE VITALE (ESI 1)", "Prise en charge immédiate en salle de déchocage."),
                    2: ("🟠 TRÈS URGENT (ESI 2)", "Prise en charge rapide requise (moins de 10 min)."),
                    3: ("🟡 URGENT (ESI 3)", "Veuillez patienter en salle d'attente. Un médecin vous recevra dès que possible."),
                    4: ("🟢 SEMI-URGENT (ESI 4)", "Votre état est stable. L'attente peut être prolongée."),
                    5: ("🔵 NON URGENT (ESI 5)", "Votre état ne relève pas de l'urgence immédiate. Vous serez vu selon l'ordre d'arrivée.")
                }
                titre, message = niveaux.get(esi, niveaux[3])

                st.markdown(f"### {titre}")
                st.info(message)
                
                st.markdown("---")
                st.markdown("#### Résumé de l'analyse")
                st.markdown(f"**Niveau d'urgence ESI :** {esi}")
                st.markdown(f"**Diagnostic estimé :** {diagnostic}")
                st.markdown(f"**Indice de confiance :** {confiance}%")
                                # S'assurer d'ajouter le patient en DB seulement la première fois qu'on affiche cette page résultat 
                if "patient_id" not in st.session_state:
                    # Remplir le dict
                    patient_complet = st.session_state.patient.copy()
                    patient_complet.update({
                        "esi_predit": esi,
                        "diagnostic_probable": diagnostic,
                        "confiance": confiance,
                        "symptom_text": st.session_state.symptom_text,
                        "constantes": st.session_state.constantes,
                        "reponses_questions": st.session_state.reponses_questions
                    })
                    # Stocker dans le store global utils.state
                    pid = ajouter_patient(patient_complet)
                    st.session_state.patient_id = pid
                                # Ticket summary
                st.markdown("""
                <div style='background:#F7F9FC;border:2px dashed #00A8E8;border-radius:12px;padding:24px;text-align:center;'>
                <h2>Votre Triage est complet</h2>
                <h4 style='color:#0A2342'>Veuillez prendre un siège en salle d'attente. Votre numéro sera appelé sur l'écran.</h4>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button("Terminer et revenir à l'accueil", use_container_width=True):
                    # Empty the session state essentially simulating a refresh
                    for key in list(st.session_state.keys()):
                        del st.session_state[key]
                    st.rerun()

            except Exception as e:
                st.error(f"Une erreur est survenue lors de l'analyse : {str(e)}")
                st.warning("Veuillez vous adresser directement au personnel d'accueil.")
                if st.button("Recommencer"):
                    for key in list(st.session_state.keys()):
                        del st.session_state[key]
                    st.rerun()

if __name__ == "__main__":
    page_borne()
