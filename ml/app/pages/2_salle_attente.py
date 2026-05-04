import streamlit as st
import time
import sys
import os
# Ajouter le dossier courant (ml/app) au sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.styles import injecter_css_medical
from utils.state import obtenir_file_attente, calculer_attente_moyenne

def page_salle_attente():
    st.set_page_config(layout="wide", page_title="Salle d'attente — HealthGate")
    injecter_css_medical()

    # CSS spécifique fond sombre
    st.markdown("""
    <style>
    .main { background: #0D1B2A !important; color: #F0F4F8 !important; }
    .block-container { background: #0D1B2A !important; }
    </style>
    """, unsafe_allow_html=True)

    # En-tête avec horloge
    col_logo, col_titre, col_heure = st.columns([1, 3, 1])
    with col_logo:
        st.markdown("🏥")
    with col_titre:
        st.markdown("## FILE D'ATTENTE — URGENCES")
    with col_heure:
        st.markdown(
            f"### {time.strftime('%H:%M:%S')}",
            help="Heure actuelle"
        )

    # Statistiques
    file = obtenir_file_attente()
    critiques = [p for p in file if p["esi_actuel"] <= 2]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Patients en attente", len(file))
    col2.metric("🚨 Niveaux critiques", len(critiques))
    col3.metric("Attente moyenne", f"{calculer_attente_moyenne(file)} min")
    col4.metric("Mise à jour", time.strftime('%H:%M:%S'))

    # Alertes clignotantes pour ESI 1 et 2
    for patient in critiques:
        st.markdown(f"""
        <div class="patient-urgent" style="
            background:#FCEBEB;
            border:2px solid #CC0000;
            border-radius:10px;
            padding:12px 20px;
            margin:8px 0;
            display:flex;
            align-items:center;
            gap:16px;
        ">
            <span style="font-size:24px">🚨</span>
            <strong style="color:#CC0000;font-size:16px">
                URGENT — {patient['prenom']} {patient['nom']}
            </strong>
            <span style="color:#CC0000">ESI {patient['esi_actuel']}</span>
            <span>Attente : {patient['temps_attente_min']} min</span>
        </div>
        """, unsafe_allow_html=True)

    # Table file d'attente
    if file:
        st.markdown("---")
        for i, patient in enumerate(file, 1):
            esi = patient["esi_actuel"]
            urgent = esi <= 2

            couleurs_esi = {
                1: "#CC0000", 2: "#FF6600", 3: "#FFB800",
                4: "#00A651", 5: "#0072BB"
            }
            couleur = couleurs_esi.get(esi, "#888")

            classe_css = "patient-urgent" if urgent else ""

            st.markdown(f"""
            <div class="{classe_css}" style="
                background:{'#1A2A3A' if not urgent else '#2A1010'};
                border:1px solid {'#2A3A4A' if not urgent else '#CC0000'};
                border-left: 6px solid {couleur};
                border-radius:10px;
                padding:16px 20px;
                margin:6px 0;
                display:flex;
                align-items:center;
                gap:20px;
                color:#F0F4F8;
            ">
                <span style="font-size:22px;color:#4A6080;font-family:monospace;width:30px">
                    {i}
                </span>
                <div style="
                    width:44px;height:44px;border-radius:50%;
                    background:{couleur}22;
                    border:3px solid {couleur};
                    display:flex;align-items:center;justify-content:center;
                    font-size:18px;font-weight:700;color:{couleur};
                ">{esi}</div>
                <div style="flex:1">
                    <div style="font-size:16px;font-weight:600">
                        {patient.get('prenom','Patient')} {patient.get('nom','')[0]}.
                    </div>
                    <div style="font-size:12px;color:#8A9BB0;margin-top:2px">
                        {patient.get('symptom_text','—')[:60]}...
                    </div>
                </div>
                <div style="text-align:right">
                    <div style="font-size:20px;font-family:monospace;
                                color:{'#CC0000' if patient['temps_attente_min']>60 else '#FFB800' if patient['temps_attente_min']>30 else '#00A651'}">
                        {patient['temps_attente_min']} min
                    </div>
                    <div style="font-size:11px;color:#4A6080">temps d'attente</div>
                </div>
                <div style="font-size:12px;color:#4A6080;text-align:right">
                    Arrivée<br>{patient.get('heure_arrivee','—')}
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("✅ Aucun patient en attente actuellement.")

    # Auto-refresh toutes les 30 secondes
    st.markdown("---")
    st.caption(f"Dernière mise à jour : {time.strftime('%H:%M:%S')} — Actualisation automatique toutes les 30s")
    time.sleep(30)
    st.rerun()

if __name__ == "__main__":
    page_salle_attente()
