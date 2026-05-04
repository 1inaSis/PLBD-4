import streamlit as st

def formulaire_constantes() -> dict:
    """
    Formulaire de saisie manuelle des constantes vitales.
    Style moniteur médical professionnel.
    Affichage code couleur en temps réel.
    """
    st.markdown("""
    <div style='background:#F7F9FC;border:1px solid #D1DCE8;
                border-radius:12px;padding:16px;margin-bottom:16px'>
    <p style='margin:0;font-size:13px;color:#4A6080;font-weight:500'>
    📊 Saisissez les valeurs mesurées par les capteurs ou manuellement
    </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        temperature = st.number_input(
            "🌡️ Température (°C)",
            min_value=30.0, max_value=43.0,
            value=37.0, step=0.1, format="%.1f"
        )
        etat_temp = (
            "🔴 CRITIQUE" if temperature > 40 or temperature < 35.5 else
            "🟠 ÉLEVÉE"   if temperature > 38.5 else
            "🟢 NORMALE"
        )
        st.caption(etat_temp)

    with col2:
        spo2 = st.number_input(
            "💧 SpO2 (%)",
            min_value=50.0, max_value=100.0,
            value=98.0, step=0.1, format="%.1f"
        )
        etat_spo2 = (
            "🔴 CRITIQUE" if spo2 < 88 else
            "🟠 BASSE"    if spo2 < 94 else
            "🟢 NORMALE"
        )
        st.caption(etat_spo2)

    with col3:
        fc = st.number_input(
            "❤️ Fréq. cardiaque (bpm)",
            min_value=20, max_value=250,
            value=75, step=1
        )
        etat_fc = (
            "🔴 CRITIQUE" if fc > 130 or fc < 45 else
            "🟠 ANORMALE" if fc > 110 or fc < 55 else
            "🟢 NORMALE"
        )
        st.caption(etat_fc)

    col4, col5 = st.columns(2)

    with col4:
        ta_sys = st.number_input(
            "🩺 Tension systolique (mmHg)",
            min_value=50, max_value=260,
            value=120, step=1
        )
        ta_dia = st.number_input(
            "🩺 Tension diastolique (mmHg)",
            min_value=30, max_value=160,
            value=80, step=1
        )
        etat_ta = (
            "🔴 CRITIQUE"   if ta_sys > 185 or ta_sys < 85 else
            "🟠 ANORMALE"   if ta_sys > 160 or ta_sys < 95 else
            "🟢 NORMALE"
        )
        st.caption(f"TA : {ta_sys}/{ta_dia} mmHg — {etat_ta}")

    with col5:
        glycemie = st.number_input(
            "🍬 Glycémie (mg/dL)",
            min_value=20, max_value=700,
            value=90, step=1
        )
        douleur = st.slider(
            "😣 Score douleur (0 = aucune, 10 = insupportable)",
            min_value=0, max_value=10, value=0
        )
        etat_gly = (
            "🔴 CRITIQUE"  if glycemie < 50 or glycemie > 400 else
            "🟠 ANORMALE"  if glycemie < 70 or glycemie > 250 else
            "🟢 NORMALE"
        )
        st.caption(f"Glycémie : {etat_gly}")

    return {
        "temperature":      temperature,
        "spo2":             spo2,
        "heart_rate":       fc,
        "bp_systolic":      ta_sys,
        "bp_diastolic":     ta_dia,
        "glucose":          glycemie,
        "pain_score":       douleur,
        "respiratory_rate": 16,
    }
