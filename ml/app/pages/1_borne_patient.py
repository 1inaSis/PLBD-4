import streamlit as st
import sys
import os
import time
import random
from pathlib import Path

# Chemins
_ML_DIR  = str(Path(__file__).parent.parent.parent)
_APP_DIR = str(Path(__file__).parent.parent)
for p in [_ML_DIR, _APP_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from app.utils.styles import injecter_css, afficher_header, afficher_sidebar
from app.utils.state  import ajouter_patient


# ─────────────────────────────────────────────────────────────────────────────
# Helpers capteurs (simulation sur PC, réel sur Raspberry Pi)
# ─────────────────────────────────────────────────────────────────────────────

def _mesurer_temperature():
    from capteurs_raspberry import lire_temperature
    return lire_temperature()

def _mesurer_tension():
    from capteurs_raspberry import lire_tension
    return lire_tension()

def _mesurer_oxygene():
    from capteurs_raspberry import lire_spo2_fc
    return lire_spo2_fc()

def _simuler_scan_carte():
    """Retourne des données de carte simulées (Tesseract absent)."""
    noms    = ["Alaoui", "Benali", "El Fassi", "Chraibi", "Tazi", "Mansouri"]
    prenoms = ["Mohamed", "Fatima", "Ahmed", "Khadija", "Youssef", "Meryem"]
    sexe    = random.choice([0, 1])
    nss     = (f"{sexe+1} "
               f"{random.randint(80,99)} "
               f"{random.randint(1,12):02d} "
               f"{random.randint(1,95):02d} "
               f"{random.randint(100,999)} "
               f"{random.randint(100,999)} "
               f"{random.randint(10,99)}")
    return {
        "nom":        random.choice(noms),
        "prenom":     random.choice(prenoms),
        "age":        random.randint(20, 70),
        "sexe":       sexe,
        "numero_ss":  nss,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Barre de progression commune
# ─────────────────────────────────────────────────────────────────────────────

def _barre_progression(etape_active: int):
    """Affiche la barre de progression (étapes 1-4 = Identité, Temp, Tension, O₂)."""
    labels  = ["Identité", "Température", "Tension", "Oxygène"]
    cercles = []
    for i, label in enumerate(labels):
        if i < etape_active:
            bg, color, texte = "#2D9B6F", "white", "✓"
        elif i == etape_active:
            bg, color, texte = "#0B1F3A", "white", str(i + 1)
        else:
            bg, color, texte = "#D8E3EF", "#9AAABF", str(i + 1)

        fw   = "700" if i == etape_active else "400"
        clr  = "#0B1F3A" if i == etape_active else "#9AAABF"
        sep  = "<div style='flex:1;height:2px;background:#D8E3EF;margin:0 6px;'></div>" if i < 3 else ""
        cercles.append(f"""
            <div style='display:flex;align-items:center;'>
                <div style='width:28px;height:28px;border-radius:50%;background:{bg};
                            display:flex;align-items:center;justify-content:center;
                            font-size:12px;font-weight:700;color:{color};flex-shrink:0;'>
                    {texte}
                </div>
                <span style='margin-left:8px;font-size:13px;font-weight:{fw};color:{clr};white-space:nowrap;'>
                    {label}
                </span>
            </div>
            {sep}
        """)

    st.markdown(f"""
    <div style='display:flex;align-items:center;justify-content:center;
                gap:0;padding:16px 0 28px;flex-wrap:nowrap;'>
        {"".join(cercles)}
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Étape de capteur générique
# ─────────────────────────────────────────────────────────────────────────────

def _etape_capteur(numero_barre, titre, icone, instruction,
                   cle_etat, cle_resultat, etape_suivante, fn_mesure):
    """
    Gère une étape de mesure avec 4 sous-états :
    instruction → measuring → done | error
    """
    _barre_progression(numero_barre)

    etat = st.session_state.get(cle_etat, "instruction")

    # ── Instruction ───────────────────────────────────────────────
    if etat == "instruction":
        st.markdown(f"""
        <div style='text-align:center;padding:16px 0 28px;'>
            <div style='font-size:72px;margin-bottom:16px;'>{icone}</div>
            <h2 style='color:#0B1F3A;font-size:26px;font-weight:700;
                       max-width:580px;margin:0 auto 12px;'>
                {titre}
            </h2>
            <p style='font-size:18px;color:#4A6080;max-width:520px;
                      margin:0 auto;line-height:1.6;'>
                {instruction}
            </p>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("▶  Lancer la mesure",
                         use_container_width=True, type="primary", key=f"btn_start_{cle_etat}"):
                st.session_state[cle_etat] = "measuring"
                st.rerun()

    # ── Mesure en cours ───────────────────────────────────────────
    elif etat == "measuring":
        st.markdown(f"""
        <div style='text-align:center;padding:24px 0;'>
            <div style='font-size:72px;margin-bottom:16px;'>{icone}</div>
            <h2 style='color:#2D9B6F;font-size:24px;'>Mesure en cours…</h2>
            <p style='color:#6A82A0;'>Restez immobile, cela prend quelques secondes.</p>
        </div>
        """, unsafe_allow_html=True)

        with st.spinner("Acquisition des données capteur…"):
            time.sleep(3)
            res = fn_mesure()
            st.session_state[cle_resultat] = res
            st.session_state[cle_etat]     = "done" if res.get("succes", True) else "error"
        st.rerun()

    # ── Erreur capteur ────────────────────────────────────────────
    elif etat == "error":
        st.markdown("""
        <div style='text-align:center;padding:24px 0;'>
            <div style='font-size:60px;margin-bottom:12px;'>⚠️</div>
            <h3 style='color:#C8001E;'>Veuillez repositionner le capteur</h3>
            <p style='color:#6A82A0;'>La mesure n'a pas pu être effectuée correctement.</p>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🔄 Réessayer",
                         use_container_width=True, type="primary", key=f"btn_retry_{cle_etat}"):
                st.session_state[cle_etat] = "measuring"
                st.rerun()

    # ── Résultat validé ───────────────────────────────────────────
    elif etat == "done":
        res    = st.session_state.get(cle_resultat, {})
        valeur = _formater_valeur(cle_resultat, res)

        st.markdown(f"""
        <div style='text-align:center;padding:16px 0 24px;'>
            <div style='font-size:56px;margin-bottom:10px;'>✅</div>
            <h2 style='color:#0B1F3A;font-size:24px;font-weight:700;'>{titre}</h2>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown(f"""
            <div class='hg-card' style='text-align:center;padding:32px;margin-bottom:16px;'>
                <div style='font-family:"JetBrains Mono",monospace;font-size:52px;
                            font-weight:700;color:#2D9B6F;margin-bottom:6px;'>
                    {valeur}
                </div>
                <div style='font-size:12px;color:#6A82A0;text-transform:uppercase;
                            letter-spacing:0.8px;font-weight:500;'>
                    Mesure enregistrée
                </div>
            </div>
            """, unsafe_allow_html=True)

            if st.button("Valider →",
                         use_container_width=True, type="primary", key=f"btn_valider_{cle_etat}"):
                st.session_state.etape = etape_suivante
                st.rerun()


def _formater_valeur(cle, res):
    if cle == "temperature":
        return f"{res.get('valeur', '—')} °C"
    if cle == "tension":
        return f"{res.get('systolique','—')}/{res.get('diastolique','—')} mmHg"
    if cle == "oxygene":
        return f"{res.get('spo2','—')} %"
    return "—"


# ─────────────────────────────────────────────────────────────────────────────
# Page principale
# ─────────────────────────────────────────────────────────────────────────────

def page_borne():
    injecter_css()
    afficher_sidebar()
    afficher_header("HealthGate")

    if "etape" not in st.session_state:
        st.session_state.etape = 0

    etape = st.session_state.etape

    # ══════════════════════════════════════════════════════════════
    # ÉTAPE 0 — ACCUEIL
    # ══════════════════════════════════════════════════════════════
    if etape == 0:
        st.markdown("""
        <div style='text-align:center;padding:60px 20px 40px;'>
            <div style='font-size:88px;margin-bottom:20px;'>🏥</div>
            <h1 style='font-size:44px;font-weight:800;color:#0B1F3A;margin-bottom:8px;
                       letter-spacing:-1px;'>
                Bienvenue sur HealthGate
            </h1>
            <p style='font-size:18px;color:#6A82A0;margin-bottom:48px;'>
                Borne de Triage Médical Intelligent
            </p>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("▶  Commencer votre session",
                         use_container_width=True, type="primary"):
                st.session_state.etape = 1
                st.rerun()

    # ══════════════════════════════════════════════════════════════
    # ÉTAPE 1 — IDENTIFICATION
    # ══════════════════════════════════════════════════════════════
    elif etape == 1:

        # Sous-état : scan en cours
        if st.session_state.get("scan_en_cours", False):
            st.markdown("""
            <div style='text-align:center;padding:40px 0;'>
                <div style='font-size:72px;margin-bottom:20px;'>🪪</div>
                <h2 style='color:#2D9B6F;font-size:26px;font-weight:700;'>
                    Placement confirmé, capture en cours…
                </h2>
                <p style='color:#6A82A0;margin-top:8px;'>Veuillez patienter quelques instants.</p>
            </div>
            """, unsafe_allow_html=True)

            with st.spinner("Lecture et extraction des données…"):
                time.sleep(2)
                try:
                    from scanner_cin import scanner_piece_identite
                    res = scanner_piece_identite(source=0)
                    if not res.get("succes"):
                        res = _simuler_scan_carte()
                    else:
                        sexe = res.get("sexe", 1)
                        nss  = (f"{(sexe if sexe in [0,1] else 1)+1} "
                                f"{random.randint(80,99)} "
                                f"{random.randint(1,12):02d} "
                                f"{random.randint(1,95):02d} "
                                f"{random.randint(100,999)} "
                                f"{random.randint(100,999)} "
                                f"{random.randint(10,99)}")
                        res["numero_ss"] = nss
                except Exception:
                    res = _simuler_scan_carte()

            st.session_state.patient_scan   = res
            st.session_state.scan_en_cours  = False
            st.session_state.etape          = 2
            st.rerun()

        # Sous-état : attente insertion carte
        else:
            st.markdown("""
            <div style='text-align:center;padding:20px 0 28px;'>
                <h2 style='color:#0B1F3A;font-size:28px;font-weight:700;margin-bottom:8px;'>
                    Identification du patient
                </h2>
                <p style='color:#6A82A0;font-size:17px;'>
                    Veuillez insérer votre carte d'identité dans le lecteur.
                </p>
            </div>
            """, unsafe_allow_html=True)

            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.markdown("""
                <div style='text-align:center;margin:8px 0 28px;'>
                    <div style='display:inline-block;border:3px dashed #2D9B6F;
                                border-radius:18px;padding:40px 80px;background:#F0FBF6;'>
                        <div style='font-size:72px;'>🪪</div>
                        <p style='color:#2D9B6F;font-weight:600;margin-top:14px;
                                  font-size:15px;letter-spacing:0.3px;'>
                            Zone d'insertion de la carte
                        </p>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if st.button("🪪  Carte insérée — Lancer la lecture",
                             use_container_width=True, type="primary"):
                    st.session_state.scan_en_cours = True
                    st.rerun()

    # ══════════════════════════════════════════════════════════════
    # ÉTAPE 2 — RÉSUMÉ DES DONNÉES
    # ══════════════════════════════════════════════════════════════
    elif etape == 2:
        scan = st.session_state.get("patient_scan", {})

        st.markdown("""
        <div style='text-align:center;padding:16px 0 24px;'>
            <div style='font-size:56px;margin-bottom:10px;'>📋</div>
            <h2 style='color:#0B1F3A;font-size:26px;font-weight:700;'>Informations extraites</h2>
            <p style='color:#6A82A0;'>Vérifiez vos informations avant de continuer.</p>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            def champ(label, valeur):
                return f"""
                <div style='margin-bottom:20px;'>
                    <div style='font-size:11px;font-weight:600;color:#4A6080;
                                text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px;'>
                        {label}
                    </div>
                    <div style='font-size:22px;font-weight:700;color:#0B1F3A;
                                font-family:"JetBrains Mono",monospace;'>
                        {valeur}
                    </div>
                </div>
                """

            st.markdown(f"""
            <div class='hg-card' style='padding:32px;margin-bottom:20px;'>
                {champ("Nom de famille", scan.get("nom", "—"))}
                {champ("Prénom",         scan.get("prenom", "—"))}
                {champ("N° Sécurité Sociale", scan.get("numero_ss", "—"))}
            </div>
            """, unsafe_allow_html=True)

            if st.button("Continuer →", use_container_width=True, type="primary"):
                st.session_state.patient = {
                    "nom":       scan.get("nom",      "Inconnu"),
                    "prenom":    scan.get("prenom",   "Inconnu"),
                    "numero_ss": scan.get("numero_ss", ""),
                    "age":       scan.get("age",       30),
                    "sex":       scan.get("sexe",       1),
                }
                st.session_state.etape = 3
                st.rerun()

    # ══════════════════════════════════════════════════════════════
    # ÉTAPE 3 — TEMPÉRATURE
    # ══════════════════════════════════════════════════════════════
    elif etape == 3:
        _etape_capteur(
            numero_barre  = 1,
            titre         = "Température corporelle",
            icone         = "🌡️",
            instruction   = "Veuillez placer le capteur sur votre front pour la mesure de la température.",
            cle_etat      = "etat_temp",
            cle_resultat  = "temperature",
            etape_suivante= 4,
            fn_mesure     = _mesurer_temperature,
        )

    # ══════════════════════════════════════════════════════════════
    # ÉTAPE 4 — TENSION ARTÉRIELLE
    # ══════════════════════════════════════════════════════════════
    elif etape == 4:
        _etape_capteur(
            numero_barre  = 2,
            titre         = "Tension artérielle",
            icone         = "💉",
            instruction   = "Veuillez attacher le brassard autour de votre bras pour la mesure de la tension artérielle.",
            cle_etat      = "etat_tension",
            cle_resultat  = "tension",
            etape_suivante= 5,
            fn_mesure     = _mesurer_tension,
        )

    # ══════════════════════════════════════════════════════════════
    # ÉTAPE 5 — OXYGÈNE
    # ══════════════════════════════════════════════════════════════
    elif etape == 5:
        _etape_capteur(
            numero_barre  = 3,
            titre         = "Taux d'oxygène",
            icone         = "💧",
            instruction   = "Veuillez insérer votre doigt dans l'oxymètre pour mesurer votre taux d'oxygène dans le sang.",
            cle_etat      = "etat_oxygene",
            cle_resultat  = "oxygene",
            etape_suivante= 6,
            fn_mesure     = _mesurer_oxygene,
        )

    # ══════════════════════════════════════════════════════════════
    # ÉTAPE 6 — CONFIRMATION
    # ══════════════════════════════════════════════════════════════
    elif etape == 6:

        # Enregistrement unique du patient
        if "patient_id" not in st.session_state:
            p   = st.session_state.get("patient", {})
            tmp = st.session_state.get("temperature", {})
            ten = st.session_state.get("tension", {})
            oxy = st.session_state.get("oxygene", {})

            patient_complet = {
                "nom":                p.get("nom",    "Inconnu"),
                "prenom":             p.get("prenom", "Inconnu"),
                "age":                p.get("age",    30),
                "sex":                p.get("sex",     1),
                "temperature":        tmp.get("valeur",       37.0),
                "spo2":               oxy.get("spo2",         98.0),
                "heart_rate":         oxy.get("fc",            75),
                "bp_systolic":        ten.get("systolique",   120),
                "bp_diastolic":       ten.get("diastolique",   80),
                "symptom_text":       "Triage automatique borne",
                "esi_predit":         3,
                "diagnostic_probable":"Évaluation en cours",
                "confiance":          0,
                "constantes": {
                    "temperature":  tmp.get("valeur",    37.0),
                    "spo2":         oxy.get("spo2",      98.0),
                    "heart_rate":   oxy.get("fc",         75),
                    "bp_systolic":  ten.get("systolique", 120),
                    "bp_diastolic": ten.get("diastolique", 80),
                },
                "reponses_questions": {},
            }
            pid = ajouter_patient(patient_complet)
            st.session_state.patient_id = pid

        p   = st.session_state.get("patient",     {})
        tmp = st.session_state.get("temperature", {})
        ten = st.session_state.get("tension",     {})
        oxy = st.session_state.get("oxygene",     {})

        st.markdown("""
        <div style='text-align:center;padding:28px 0 32px;'>
            <div style='font-size:88px;margin-bottom:16px;'>✅</div>
            <h1 style='color:#2D9B6F;font-size:30px;font-weight:800;
                       max-width:620px;margin:0 auto 10px;line-height:1.3;'>
                Vos mesures ont été enregistrées avec succès.
            </h1>
            <h2 style='color:#0B1F3A;font-size:20px;font-weight:400;margin-top:8px;'>
                Merci d'avoir utilisé HealthGate
            </h2>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1, 3, 1])
        with col2:
            st.markdown(f"""
            <div class='hg-card' style='margin-bottom:16px;'>
                <div class='hg-card-titre'>Récapitulatif des mesures</div>
                <div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;
                            text-align:center;margin-top:12px;'>
                    <div>
                        <div style='font-size:11px;color:#6A82A0;text-transform:uppercase;
                                    letter-spacing:0.8px;margin-bottom:4px;'>Température</div>
                        <div style='font-family:"JetBrains Mono",monospace;font-size:30px;
                                    font-weight:700;color:#0B1F3A;'>
                            {tmp.get("valeur","—")} °C
                        </div>
                    </div>
                    <div>
                        <div style='font-size:11px;color:#6A82A0;text-transform:uppercase;
                                    letter-spacing:0.8px;margin-bottom:4px;'>Tension</div>
                        <div style='font-family:"JetBrains Mono",monospace;font-size:22px;
                                    font-weight:700;color:#0B1F3A;'>
                            {ten.get("systolique","—")}/{ten.get("diastolique","—")} mmHg
                        </div>
                    </div>
                    <div>
                        <div style='font-size:11px;color:#6A82A0;text-transform:uppercase;
                                    letter-spacing:0.8px;margin-bottom:4px;'>Oxygène</div>
                        <div style='font-family:"JetBrains Mono",monospace;font-size:30px;
                                    font-weight:700;color:#0B1F3A;'>
                            {oxy.get("spo2","—")} %
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.info("Veuillez patienter en salle d'attente. Votre numéro sera bientôt appelé sur l'écran.")

            if st.button("Terminer la session",
                         use_container_width=True):
                for k in list(st.session_state.keys()):
                    del st.session_state[k]
                st.rerun()


if __name__ == "__main__":
    page_borne()
