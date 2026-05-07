import streamlit as st
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from questions_moteur import generer_questions

def afficher_questions(constantes: dict, symptom_text: str, age: int, sex: int):
    """
    Affiche la série de questions générée dynamiquement.
    Retourne None tant que le questionnaire n'est pas fini.
    Retourne un dict de réponses quand c'est terminé.
    """
    if "questions_generees" not in st.session_state:
        # Extraire les questions du moteur
        questions_brutes = generer_questions(
            constantes=constantes,
            symptom_text=symptom_text,
            age=age,
            sex=sex
        )
        
        # Filtre de sécurité au cas où le moteur ne renvoie rien
        if not questions_brutes:
            questions_brutes = [{"text": "Avez-vous d'autres symptômes non mentionnés ?", "feature_name": "q_autre"}]
            
        st.session_state.questions_generees = questions_brutes
        st.session_state.index_question = 0
        st.session_state.reponses_temporaires = {}

    questions = st.session_state.questions_generees
    idx = st.session_state.index_question

    if idx < len(questions):
        st.progress((idx) / len(questions))
        st.caption(f"Question {idx + 1} sur {len(questions)}")
        
        q = questions[idx]
        texte = q.get("texte", q.get("text", q.get("question", "Question inconnue ?")))
        feature_name = q.get("feature_name", texte)
        q_type = q.get("type", "oui_non")
        
        st.markdown(f"### {texte}")
        
        if q_type == "oui_non":
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Oui", key=f"oui_{idx}", use_container_width=True, type="primary"):
                    st.session_state.reponses_temporaires[feature_name] = 1
                    st.session_state.index_question += 1
                    st.rerun()
            with col2:
                if st.button("Non", key=f"non_{idx}", use_container_width=True):
                    st.session_state.reponses_temporaires[feature_name] = 0
                    st.session_state.index_question += 1
                    st.rerun()
        
        elif q_type == "choix":
            choix = q.get("choix", [])
            # Eviter l'erreur s'il n'y a pas de choix
            if not choix:
                choix = ["Je ne sais pas"]
                
            cols = st.columns(len(choix))
            for i, c in enumerate(choix):
                with cols[i]:
                    if st.button(c, key=f"choix_{idx}_{i}", use_container_width=True):
                        st.session_state.reponses_temporaires[feature_name] = c
                        st.session_state.index_question += 1
                        st.rerun()
                        
        else: # type == "texte_libre" ou par defaut
            rep = st.text_input("Votre réponse :", key=f"txt_{idx}")
            if st.button("Valider", key=f"val_{idx}", type="primary"):
                st.session_state.reponses_temporaires[feature_name] = rep
                st.session_state.index_question += 1
                st.rerun()
        
        return None
    else:
        # Questionnaire terminé
        reponses = st.session_state.reponses_temporaires.copy()
        return reponses
