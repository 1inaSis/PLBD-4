import streamlit as st
import os

def main():
    st.set_page_config(
        page_title="HealthGate | ECC",
        page_icon="??",
        layout="wide",
        initial_sidebar_state="collapsed" # App look and feel
    )

    # Custom CSS injection
    try:
        from utils.styles import injecter_css_medical
        injecter_css_medical()
    except Exception as e:
        pass

    # Utilisation du Logo Officiel (si présent)
    logo_path = "assets/logo_ecc.webp"
    if os.path.exists(logo_path):
        try:
            st.logo(logo_path, size="large")
        except AttributeError:
            # Fallback for older Streamlit versions
            st.sidebar.image(logo_path, use_container_width=True)

    # UI Immersive Header
    st.markdown("""
        <div style='text-align: center; margin-top: 20px; margin-bottom: 20px;'>
            <h1 style='color: #0A2342; font-weight: 800; font-size: 50px;'>HealthGate</h1>
            <p style='color: #4A6080; font-size: 20px;'>Système de Triage Médical Intelligent</p>
            <p style='color: #00A8E8; font-weight: bold;'>École Centrale Casablanca | Afrique</p>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 4, 1])
    with col2:
        img_path = "assets/hopital_afrique.webp"
        if os.path.exists(img_path):
            st.image(img_path, use_container_width=True, caption="Solution déployée pour les urgences modernes")
        else:
            st.info("📸 L'image de contextualisation n'est pas encore ajoutée.")

    st.markdown("<hr style='border: 1px solid #D1DCE8; margin: 30px 0;'>", unsafe_allow_html=True)
    
    # Navigation Buttons via page switch
    st.markdown("### ?? Démarrer l'expérience :")
    cols = st.columns(4)
    with cols[0]:
        if st.button("?? Borne Triage Patient", type="primary", use_container_width=True):
            st.switch_page("pages/1_borne_patient.py")
    with cols[1]:
        if st.button("?? Salle d'attente", type="secondary", use_container_width=True):
            st.switch_page("pages/2_salle_attente.py")
    with cols[2]:
        if st.button("????? Espace Médecin 1", use_container_width=True):
            st.switch_page("pages/3_medecin_M1.py")
    with cols[3]:
        if st.button("????? Espace Médecin 2", use_container_width=True):
            st.switch_page("pages/4_medecin_M2.py")

if __name__ == "__main__":
    main()

