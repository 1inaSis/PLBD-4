import streamlit as st
import sys
import os
# Ajouter le dossier courant (ml/app) au sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.styles import injecter_css_medical
from utils.state import obtenir_patients_medecin, obtenir_rapport, retirer_patient

def prise_en_charge(pid):
    retirer_patient(pid)

def page_medecin(medecin_id: str, nom_medecin: str):
    injecter_css_medical()

    # En-tête médecin
    col_info, col_statut = st.columns([3, 1])
    with col_info:
        st.markdown(f"## 👨‍⚕️ {nom_medecin}")
        st.caption("Médecine générale — Interface de triage")
    with col_statut:
        st.markdown("🟢 **En ligne**")

    # Layout 2 colonnes
    col_liste, col_detail = st.columns([1, 2])

    with col_liste:
        st.markdown("### Mes patients")
        patients = obtenir_patients_medecin(medecin_id)
        st.caption(f"{len(patients)} patient(s) assigné(s)")

        for patient in patients:
            esi = patient.get("esi_actuel", 3)
            urgent = esi <= 2
            couleurs_esi = {
                1:"#CC0000", 2:"#FF6600", 3:"#FFB800",
                4:"#00A651", 5:"#0072BB"
            }
            classe = "patient-urgent" if urgent else ""

            if st.button(
                f"ESI {esi} — {patient.get('prenom','')} {patient.get('nom','')[0]}. "
                f"— {patient.get('temps_attente_min',0)} min",
                key=patient["patient_id"],
                use_container_width=True
            ):
                st.session_state.patient_selectionne = patient["patient_id"]

    with col_detail:
        pid = st.session_state.get("patient_selectionne")
        if not pid:
            st.info("👈 Sélectionnez un patient pour voir son rapport")
        else:
            rapport = obtenir_rapport(pid)
            afficher_rapport_medical(rapport, medecin_id)

def afficher_rapport_medical(rapport: dict, medecin_id: str):
    """Affiche le rapport médical complet style dossier médical."""

    esi = rapport.get("esi_predit", 3)
    couleurs_esi = {
        1:"#CC0000",2:"#FF6600",3:"#FFB800",4:"#00A651",5:"#0072BB"
    }
    niveaux_esi = {
        1:"CRITIQUE",2:"TRÈS URGENT",3:"URGENT",4:"SEMI-URGENT",5:"NON URGENT"
    }

    # En-tête patient
    st.markdown(f"""
    <div style="background:white;border:1px solid #D1DCE8;
                border-radius:12px;padding:20px;margin-bottom:16px">
        <div style="display:flex;align-items:center;gap:16px">
            <div style="width:52px;height:52px;border-radius:50%;
                        background:#E3F2FD;display:flex;align-items:center;
                        justify-content:center;font-size:20px;font-weight:600;
                        color:#0A2342">
                {rapport.get('prenom','P')[0]}{rapport.get('nom','X')[0]}
            </div>
            <div>
                <h3 style="margin:0">{rapport.get('prenom','')} {rapport.get('nom','')}</h3>
                <p style="margin:0;color:#4A6080;font-size:13px">
                    {rapport.get('age','?')} ans · {rapport.get('sexe','—')} ·
                    Arrivée {rapport.get('heure_arrivee','—')}
                </p>
                <span style="
                    background:{couleurs_esi[esi]}22;
                    color:{couleurs_esi[esi]};
                    border:1px solid {couleurs_esi[esi]};
                    border-radius:20px;
                    padding:3px 12px;
                    font-size:12px;
                    font-weight:600
                ">
                    ESI {esi} — {niveaux_esi[esi]}
                </span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Constantes vitales style moniteur médical
    st.markdown("#### 📊 Constantes vitales")
    c = rapport.get("constantes", {})

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    afficher_constante(col1, c.get("temperature","—"), "°C", "Température",
                       lambda v: v>40 or v<35.5, lambda v: v>38.5)
    afficher_constante(col2, c.get("spo2","—"), "%", "SpO2",
                       lambda v: v<88, lambda v: v<94)
    afficher_constante(col3, c.get("heart_rate","—"), "bpm", "FC",
                       lambda v: v>130 or v<45, lambda v: v>110 or v<55)
    afficher_constante(col4, c.get("bp_systolic","—"), "mmHg", "TA syst.",
                       lambda v: v>185 or v<85, lambda v: v>160 or v<95)
    afficher_constante(col5, c.get("bp_diastolic","—"), "mmHg", "TA diast.",
                       lambda v: False, lambda v: False)
    afficher_constante(col6, c.get("glucose","—"), "mg/L", "Glycémie",
                       lambda v: v<50 or v>400, lambda v: v<70 or v>250)

    # Symptômes
    st.markdown("#### 💬 Symptômes déclarés")
    st.markdown(f"""
    <div style="background:#F7F9FC;border-left:4px solid #00A8E8;
                border-radius:0 8px 8px 0;padding:14px 18px;font-style:italic">
        "{rapport.get('symptom_text','Non renseigné')}"
    </div>
    """, unsafe_allow_html=True)

    # Réponses questions ciblées
    if rapport.get("reponses_questions"):
        st.markdown("#### ❓ Réponses aux questions ciblées")
        for question, reponse in rapport["reponses_questions"].items():
            couleur = "#00A651" if reponse in ["Oui", True, 1] else "#4A6080"
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;
                        padding:8px 0;border-bottom:1px solid #F0F4F8">
                <span style="font-size:13px;color:#0D1B2A">{question}</span>
                <span style="color:{couleur};font-weight:600;font-size:13px">
                    {reponse}
                </span>
            </div>
            """, unsafe_allow_html=True)

    # Diagnostic
    st.markdown("#### 🔬 Diagnostic et triage")
    col_diag, col_conf = st.columns([2, 1])
    with col_diag:
        st.markdown(f"""
        <div style="background:#F7F9FC;border:1px solid #D1DCE8;
                    border-radius:10px;padding:16px">
            <p style="font-size:18px;font-weight:600;color:#0A2342;margin:0">
                {rapport.get('diagnostic_probable','—')}
            </p>
            <p style="color:#4A6080;font-size:12px;margin:6px 0 0">
                Comorbidités : {rapport.get('comorbidites','Aucune')}
            </p>
        </div>
        """, unsafe_allow_html=True)
    with col_conf:
        st.metric("Confiance modèle", f"{rapport.get('confiance','—')}%")
        st.metric("Position file", f"#{rapport.get('position_file','—')}")

    # Bouton prise en charge
    st.markdown("---")
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button(
            "✅ MARQUER PRIS EN CHARGE",
            use_container_width=True,
            type="primary"
        ):
            prise_en_charge(rapport.get("patient_id"))
            st.success("✅ Patient pris en charge avec succès !")
            st.session_state.patient_selectionne = None
            st.rerun()
    with col_btn2:
        if st.button(
            "⚠️ Signaler dégradation",
            use_container_width=True
        ):
            st.session_state.show_degradation = True

def afficher_constante(col, valeur, unite, label, est_critique, est_alerte):
    """Affiche une constante vitale avec code couleur."""
    try:
        v = float(valeur)
        if est_critique(v):
            couleur = "#CC0000"
            icone = "🔴"
        elif est_alerte(v):
            couleur = "#FFB800"
            icone = "🟠"
        else:
            couleur = "#00A651"
            icone = "🟢"
    except:
        couleur = "#4A6080"
        icone = "⚪"

    col.markdown(f"""
    <div style="background:white;border:1px solid #D1DCE8;
                border-radius:10px;padding:12px;text-align:center">
        <div style="font-family:'JetBrains Mono',monospace;
                    font-size:24px;font-weight:600;color:{couleur}">
            {valeur}
        </div>
        <div style="font-size:11px;color:#4A6080;margin-top:2px">
            {unite}
        </div>
        <div style="font-size:10px;color:#4A6080;margin-top:2px;
                    text-transform:uppercase;letter-spacing:0.5px">
            {label}
        </div>
        <div style="font-size:14px;margin-top:4px">{icone}</div>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="Dr. El Amrani — HealthGate")
    page_medecin("m1", "Dr. El Amrani")
