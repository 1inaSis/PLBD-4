import streamlit as st

def injecter_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    /* -- BASE ----------------------------------- */
    html, body, [class*="css"], .stApp {
        font-family: 'Sora', sans-serif !important;
        background-color: #F4F7FA !important;
        color: #0B1F3A !important;
    }

    /* Masquer tout ce qui est Streamlit par défaut */
    #MainMenu { visibility: hidden !important; }
    footer    { visibility: hidden !important; }
    header    { visibility: hidden !important; }
    .stDeployButton { display: none !important; }
    [data-testid="stSidebarNav"] { display: none !important; }

    /* Supprimer le padding Streamlit */
    .block-container {
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        max-width: 100% !important;
    }

    /* -- HEADER --------------------------------- */
    .hg-header {
        background: linear-gradient(135deg, #0B1F3A 0%, #132D52 100%);
        padding: 14px 40px;
        display: flex;
        align-items: center;
        gap: 16px;
        box-shadow: 0 4px 24px rgba(11,31,58,0.3);
        margin-bottom: 28px;
        border-radius: 0;
    }
    .hg-logo-icon {
        width: 40px; height: 40px;
        background: #2D9B6F;
        border-radius: 10px;
        display: flex; align-items: center; justify-content: center;
        font-size: 20px;
        flex-shrink: 0;
    }
    .hg-logo-text h1 {
        font-size: 20px !important;
        font-weight: 700 !important;
        color: #FFFFFF !important;
        margin: 0 !important;
        letter-spacing: -0.3px;
    }
    .hg-logo-text span {
        font-size: 11px;
        color: rgba(255,255,255,0.5);
        font-weight: 300;
        letter-spacing: 0.5px;
    }
    .hg-dot-live {
        width: 8px; height: 8px;
        background: #2D9B6F;
        border-radius: 50%;
        display: inline-block;
        animation: pulse-live 2s infinite;
        margin-right: 6px;
    }
    @keyframes pulse-live {
        0%,100% { opacity:1; box-shadow: 0 0 0 0 rgba(45,155,111,0.5); }
        50%      { opacity:0.7; box-shadow: 0 0 0 6px rgba(45,155,111,0); }
    }

    /* -- CARTES --------------------------------- */
    .hg-card {
        background: #FFFFFF;
        border: 1px solid #D8E3EF;
        border-radius: 14px;
        padding: 24px 28px;
        box-shadow: 0 2px 16px rgba(11,31,58,0.07);
        margin-bottom: 16px;
    }
    .hg-card-titre {
        font-size: 13px;
        font-weight: 600;
        color: #4A6080;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-bottom: 16px;
        padding-bottom: 10px;
        border-bottom: 1px solid #EDF2F8;
    }

    /* -- CONSTANTES VITALES --------------------- */
    .constante-card {
        background: #F4F7FA;
        border: 1.5px solid #D8E3EF;
        border-radius: 12px;
        padding: 16px 12px;
        text-align: center;
        transition: all 0.2s;
    }
    .constante-card.normale  { border-color: #9DD5BC; background: #F0FBF6; }
    .constante-card.alerte   { border-color: #E8C84A; background: #FFFCEB; }
    .constante-card.critique { border-color: #E8A0A8; background: #FFF0F2; }

    .constante-val {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 30px !important;
        font-weight: 600 !important;
        line-height: 1.1;
        display: block;
    }
    .constante-val.normale  { color: #2D9B6F; }
    .constante-val.alerte   { color: #B8900A; }
    .constante-val.critique { color: #C8001E; }

    .constante-unite {
        font-size: 12px;
        color: #6A82A0;
        display: block;
        margin-top: 2px;
    }
    .constante-label {
        font-size: 11px;
        font-weight: 600;
        color: #4A6080;
        text-transform: uppercase;
        letter-spacing: 0.7px;
        display: block;
        margin-top: 8px;
    }
    .constante-plage {
        font-size: 9px;
        color: #9AAABF;
        display: block;
        margin-top: 3px;
    }
    .constante-statut {
        font-size: 11px;
        font-weight: 600;
        display: block;
        margin-top: 6px;
        padding: 2px 8px;
        border-radius: 20px;
        display: inline-block;
    }
    .statut-normale  { background: #D4F0E4; color: #1A6B4A; }
    .statut-alerte   { background: #FFF0C4; color: #8A6200; }
    .statut-critique { background: #FFE0E4; color: #8A0015; }

    /* -- BADGES ESI ----------------------------- */
    .esi-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 44px; height: 44px;
        border-radius: 50%;
        font-family: 'Sora', sans-serif;
        font-weight: 800;
        font-size: 18px;
        border: 2.5px solid;
        flex-shrink: 0;
    }
    .esi-badge-lg {
        width: 90px; height: 90px;
        font-size: 38px;
        border-width: 4px;
        border-radius: 50%;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-family: 'Sora', sans-serif;
        font-weight: 800;
    }
    .esi-1 { background:#FCEBEC; color:#C8001E; border-color:#C8001E; }
    .esi-2 { background:#FFF0E6; color:#E05A00; border-color:#E05A00; }
    .esi-3 { background:#FFFBEB; color:#B8900A; border-color:#C49A00; }
    .esi-4 { background:#EDFBF4; color:#2D9B6F; border-color:#2D9B6F; }
    .esi-5 { background:#EBF4FF; color:#1A6BC4; border-color:#1A6BC4; }

    /* -- BOUTONS -------------------------------- */
    .btn-primary {
        background: linear-gradient(135deg, #2D9B6F, #1A6B4A) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 14px 32px !important;
        font-family: 'Sora', sans-serif !important;
        font-weight: 600 !important;
        font-size: 15px !important;
        cursor: pointer !important;
        box-shadow: 0 4px 16px rgba(45,155,111,0.35) !important;
        width: 100% !important;
        transition: all 0.2s !important;
    }
    .btn-oui {
        background: linear-gradient(135deg, #2D9B6F, #1A6B4A);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 20px;
        font-family: 'Sora', sans-serif;
        font-weight: 700;
        font-size: 22px;
        cursor: pointer;
        width: 100%;
        box-shadow: 0 4px 20px rgba(45,155,111,0.35);
        transition: all 0.15s;
        letter-spacing: 1px;
    }
    .btn-oui:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(45,155,111,0.45); }
    .btn-non {
        background: #FFF0F2;
        color: #C8001E;
        border: 2.5px solid #C8001E;
        border-radius: 12px;
        padding: 20px;
        font-family: 'Sora', sans-serif;
        font-weight: 700;
        font-size: 22px;
        cursor: pointer;
        width: 100%;
        transition: all 0.15s;
        letter-spacing: 1px;
    }
    .btn-non:hover { background: #FCEBEC; transform: translateY(-2px); }
    .btn-choix {
        background: white;
        color: #0B1F3A;
        border: 1.5px solid #D8E3EF;
        border-radius: 10px;
        padding: 16px 20px;
        font-family: 'Sora', sans-serif;
        font-weight: 500;
        font-size: 15px;
        cursor: pointer;
        width: 100%;
        text-align: left;
        transition: all 0.15s;
        margin-bottom: 8px;
        display: block;
    }
    .btn-choix:hover { border-color: #2D9B6F; background: #F0FBF6; color: #1A6B4A; }
    .btn-choix.selectionne { border-color: #2D9B6F; background: #EDFBF4; color: #1A6B4A; font-weight: 600; }

    /* -- QUESTION CONTAINER --------------------- */
    .question-container {
        background: white;
        border: 1px solid #D8E3EF;
        border-radius: 16px;
        padding: 32px;
        box-shadow: 0 4px 24px rgba(11,31,58,0.08);
        max-width: 680px;
        margin: 0 auto;
    }
    .question-texte {
        font-size: 22px !important;
        font-weight: 600 !important;
        color: #0B1F3A !important;
        line-height: 1.4 !important;
        margin-bottom: 28px !important;
        text-align: center;
    }
    .question-prog {
        font-size: 12px;
        color: #6A82A0;
        text-align: center;
        margin-bottom: 16px;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }
    .prog-bar-container {
        background: #EDF2F8;
        border-radius: 4px;
        height: 4px;
        margin-bottom: 28px;
        overflow: hidden;
    }
    .prog-bar-fill {
        background: linear-gradient(90deg, #2D9B6F, #1A6BC4);
        height: 100%;
        border-radius: 4px;
        transition: width 0.4s ease;
    }

    /* -- BADGE IA ------------------------------- */
    .badge-ia {
        background: linear-gradient(135deg, #EBF4FF, #F0E8FF);
        border: 1px solid #B8D4F8;
        border-radius: 10px;
        padding: 12px 18px;
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 20px;
    }
    .badge-ia-texte {
        font-size: 13px;
        color: #1A4A8A;
        font-weight: 500;
    }
    .badge-ia-sub {
        font-size: 11px;
        color: #4A70A0;
        margin-top: 2px;
    }

    /* -- TICKET --------------------------------- */
    .ticket-container {
        border: 2.5px dashed #C8D8EC;
        border-radius: 20px;
        padding: 36px 32px;
        text-align: center;
        background: white;
        max-width: 440px;
        margin: 0 auto;
        box-shadow: 0 8px 32px rgba(11,31,58,0.1);
    }
    .ticket-num {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 80px !important;
        font-weight: 700 !important;
        color: #0B1F3A !important;
        letter-spacing: -4px;
        line-height: 1;
        display: block;
        margin: 12px 0;
    }
    .ticket-sep {
        border: none;
        border-top: 2px dashed #D8E3EF;
        margin: 20px 0;
    }
    .ticket-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 0;
        font-size: 14px;
    }
    .ticket-row .label { color: #6A82A0; }
    .ticket-row .value { font-weight: 600; color: #0B1F3A; }

    /* -- SALLE D'ATTENTE ------------------------ */
    .salle-bg {
        background: linear-gradient(160deg, #0B1F3A 0%, #0D2848 60%, #091828 100%) !important;
        min-height: 100vh;
        color: #E8EFF8 !important;
    }
    .salle-titre {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 42px !important;
        font-weight: 600 !important;
        color: #FFFFFF !important;
        letter-spacing: 2px;
    }
    .salle-horloge {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 48px !important;
        font-weight: 600 !important;
        color: #2D9B6F !important;
        letter-spacing: 3px;
    }
    .salle-patient-row {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.08);
        border-left: 5px solid;
        border-radius: 10px;
        padding: 18px 24px;
        margin: 8px 0;
        display: flex;
        align-items: center;
        gap: 20px;
        font-size: 20px;
    }
    .salle-patient-urgent {
        animation: salle-clignoter 1s infinite;
    }
    @keyframes salle-clignoter {
        0%,100% { background: rgba(200,0,30,0.15); border-left-color: #C8001E; }
        50%      { background: rgba(200,0,30,0.05); border-left-color: rgba(200,0,30,0.3); }
    }

    /* -- RAPPORT MÉDECIN ------------------------ */
    .rapport-header {
        background: white;
        border: 1px solid #D8E3EF;
        border-radius: 14px;
        padding: 20px 24px;
        display: flex;
        align-items: center;
        gap: 18px;
        margin-bottom: 16px;
        box-shadow: 0 2px 12px rgba(11,31,58,0.07);
    }
    .rapport-avatar {
        width: 56px; height: 56px;
        border-radius: 50%;
        background: linear-gradient(135deg, #132D52, #1A6BC4);
        display: flex; align-items: center; justify-content: center;
        font-size: 20px; font-weight: 700;
        color: white;
        flex-shrink: 0;
    }
    .rapport-nom {
        font-size: 22px !important;
        font-weight: 700 !important;
        color: #0B1F3A !important;
        margin: 0 !important;
    }
    .rapport-meta {
        font-size: 13px;
        color: #6A82A0;
        margin-top: 3px;
    }
    .btn-prise-en-charge {
        background: linear-gradient(135deg, #2D9B6F, #1A6B4A);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 16px 28px;
        font-family: 'Sora', sans-serif;
        font-weight: 700;
        font-size: 16px;
        cursor: pointer;
        width: 100%;
        box-shadow: 0 4px 20px rgba(45,155,111,0.4);
        transition: all 0.2s;
        letter-spacing: 0.5px;
    }

    /* -- PATIENT CARD LISTE MÉDECIN ------------- */
    .patient-list-card {
        background: white;
        border: 1px solid #D8E3EF;
        border-left: 4px solid;
        border-radius: 10px;
        padding: 14px 16px;
        margin-bottom: 8px;
        cursor: pointer;
        transition: all 0.15s;
    }
    .patient-list-card:hover {
        box-shadow: 0 4px 16px rgba(11,31,58,0.1);
        transform: translateX(3px);
    }
    .patient-list-card.active {
        box-shadow: 0 4px 20px rgba(11,31,58,0.12);
        transform: translateX(4px);
    }
    .patient-list-card.urgent-card {
        animation: card-pulse 1.5s infinite;
    }
    @keyframes card-pulse {
        0%,100% { border-left-color: #C8001E; box-shadow: 0 0 0 0 rgba(200,0,30,0.3); }
        50%      { border-left-color: #FF4060; box-shadow: 0 0 0 6px rgba(200,0,30,0); }
    }

    /* -- ALERTES -------------------------------- */
    .alerte-critique {
        background: linear-gradient(135deg, #C8001E, #A00018);
        color: white;
        border-radius: 12px;
        padding: 16px 24px;
        display: flex;
        align-items: center;
        gap: 14px;
        margin-bottom: 16px;
        animation: alerte-pulse 1s infinite;
        box-shadow: 0 4px 20px rgba(200,0,30,0.4);
    }
    @keyframes alerte-pulse {
        0%,100% { box-shadow: 0 4px 20px rgba(200,0,30,0.4); }
        50%      { box-shadow: 0 4px 32px rgba(200,0,30,0.7); }
    }

    /* -- MÉTRIQUES ------------------------------ */
    .metric-card {
        background: white;
        border: 1px solid #D8E3EF;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 2px 10px rgba(11,31,58,0.06);
    }
    .metric-val {
        font-family: 'JetBrains Mono', monospace;
        font-size: 36px;
        font-weight: 700;
        color: #0B1F3A;
        line-height: 1;
    }
    .metric-label {
        font-size: 12px;
        color: #6A82A0;
        margin-top: 6px;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* -- INPUTS STREAMLIT ----------------------- */
    .stTextInput input,
    .stNumberInput input,
    .stTextArea textarea {
        border: 1.5px solid #D8E3EF !important;
        border-radius: 10px !important;
        font-family: 'Sora', sans-serif !important;
        font-size: 15px !important;
        padding: 12px 16px !important;
        background: white !important;
        color: #0B1F3A !important;
        box-shadow: none !important;
        transition: border-color 0.2s !important;
    }
    .stTextInput input:focus,
    .stNumberInput input:focus,
    .stTextArea textarea:focus {
        border-color: #2D9B6F !important;
        box-shadow: 0 0 0 3px rgba(45,155,111,0.15) !important;
    }
    .stTextInput label,
    .stNumberInput label,
    .stTextArea label,
    .stSlider label,
    .stRadio label {
        font-family: 'Sora', sans-serif !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        color: #4A6080 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
    }

    /* Boutons Streamlit natifs */
    .stButton button {
        font-family: 'Sora', sans-serif !important;
        font-weight: 600 !important;
        font-size: 15px !important;
        border-radius: 10px !important;
        padding: 12px 24px !important;
        transition: all 0.2s !important;
        border: none !important;
        cursor: pointer !important;
    }
    .stButton button[kind="primary"] {
        background: linear-gradient(135deg, #2D9B6F, #1A6B4A) !important;
        color: white !important;
        box-shadow: 0 4px 16px rgba(45,155,111,0.35) !important;
    }
    .stButton button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 20px rgba(11,31,58,0.15) !important;
    }

    /* Tabs Streamlit */
    .stTabs [data-baseweb="tab-list"] {
        background: #EDF2F8 !important;
        border-radius: 10px !important;
        padding: 4px !important;
        gap: 4px !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px !important;
        font-family: 'Sora', sans-serif !important;
        font-weight: 500 !important;
        font-size: 14px !important;
        color: #4A6080 !important;
        padding: 10px 20px !important;
    }
    .stTabs [aria-selected="true"] {
        background: white !important;
        color: #0B1F3A !important;
        font-weight: 600 !important;
        box-shadow: 0 2px 8px rgba(11,31,58,0.08) !important;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0B1F3A 0%, #132D52 100%) !important;
    }
    [data-testid="stSidebar"] * {
        color: rgba(255,255,255,0.85) !important;
    }
    [data-testid="stSidebar"] .stButton button {
        background: rgba(255,255,255,0.1) !important;
        color: white !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        width: 100% !important;
    }
    [data-testid="stSidebar"] .stButton button:hover {
        background: rgba(45,155,111,0.3) !important;
    }

    /* Selectbox */
    .stSelectbox select,
    [data-baseweb="select"] {
        border: 1.5px solid #D8E3EF !important;
        border-radius: 10px !important;
        font-family: 'Sora', sans-serif !important;
    }

    /* Slider */
    .stSlider [data-baseweb="slider"] {
        padding: 0 !important;
    }
    .stSlider [data-testid="stThumbValue"] {
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        background: #2D9B6F !important;
        color: white !important;
        border-radius: 6px !important;
        padding: 2px 8px !important;
    }

    /* Info/Warning/Error boxes */
    .stAlert {
        border-radius: 10px !important;
        border: none !important;
        font-family: 'Sora', sans-serif !important;
    }

    /* Progress bar */
    .stProgress > div > div {
        background: linear-gradient(90deg, #2D9B6F, #1A6BC4) !important;
        border-radius: 4px !important;
    }

    /* Expander */
    .streamlit-expanderHeader {
        font-family: 'Sora', sans-serif !important;
        font-weight: 600 !important;
        color: #0B1F3A !important;
        background: #F4F7FA !important;
        border-radius: 10px !important;
    }

    /* Colonnes séparateur */
    [data-testid="column"] {
        padding: 0 8px !important;
    }

    /* Spinner */
    .stSpinner > div {
        border-top-color: #2D9B6F !important;
    }

    /* Success/Error/Warning */
    .stSuccess { background: #EDFBF4 !important; border-left: 4px solid #2D9B6F !important; }
    .stError   { background: #FFF0F2 !important; border-left: 4px solid #C8001E !important; }
    .stWarning { background: #FFFBEB !important; border-left: 4px solid #C49A00 !important; }
    .stInfo    { background: #EBF4FF !important; border-left: 4px solid #1A6BC4 !important; }

    </style>
    """, unsafe_allow_html=True)


def afficher_header(titre: str, sous_titre: str = "Borne de Triage Médical Intelligent"):
    """Affiche le header HealthGate professionnel."""
    import base64
    import os
    from datetime import datetime
    
    # Encoder le logo
    logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "logo_ecc.webp")
    logo_b64 = ""
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as img_file:
            logo_b64 = base64.b64encode(img_file.read()).decode()
    
    img_tag = f'<img src="data:image/webp;base64,{logo_b64}" style="width: 40px; height: 40px; border-radius: 8px;">' if logo_b64 else "🏥"
    heure_actuelle = datetime.now().strftime("%H:%M:%S")

    st.markdown(f"""
    <div class="hg-header">
        <div class="hg-logo-icon">{img_tag}</div>
        <div class="hg-logo-text">
            <h1>{titre}</h1>
            <span>{sous_titre}</span>
        </div>
        <div style="margin-left:auto;display:flex;align-items:center;gap:20px">
            <div style="display:flex;align-items:center;gap:6px">
                <div class="hg-dot-live"></div>
                <span style="font-size:12px;color:rgba(255,255,255,0.6);font-weight:400">
                    Système actif
                </span>
            </div>
            <div id="hg-horloge"
                 style="font-family:'JetBrains Mono',monospace;font-size:16px;
                        font-weight:500;color:rgba(255,255,255,0.9);letter-spacing:1px">
                {heure_actuelle}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def afficher_constante_card(valeur, unite: str, label: str, plage: str,
                             seuil_critique_min=None, seuil_critique_max=None,
                             seuil_alerte_min=None, seuil_alerte_max=None):
    """Affiche une constante vitale style moniteur médical avec code couleur."""
    try:
        v = float(valeur)
        if ((seuil_critique_min and v < seuil_critique_min) or
            (seuil_critique_max and v > seuil_critique_max)):
            etat = "critique"
            statut_txt = "?? CRITIQUE"
        elif ((seuil_alerte_min and v < seuil_alerte_min) or
              (seuil_alerte_max and v > seuil_alerte_max)):
            etat = "alerte"
            statut_txt = "?? ATTENTION"
        else:
            etat = "normale"
            statut_txt = "?? NORMALE"
    except:
        etat = "normale"
        statut_txt = "? —"

    st.markdown(f"""
    <div class="constante-card {etat}">
        <span class="constante-val {etat}">{valeur}</span>
        <span class="constante-unite">{unite}</span>
        <span class="constante-label">{label}</span>
        <span class="constante-plage">Normale : {plage}</span>
        <span class="constante-statut statut-{etat}">{statut_txt}</span>
    </div>
    """, unsafe_allow_html=True)


def afficher_esi_badge(esi: int, taille: str = "normal"):
    """Affiche un badge ESI coloré."""
    labels = {1:"CRITIQUE",2:"TRÈS URGENT",3:"URGENT",4:"SEMI-URGENT",5:"NON URGENT"}
    classe = "esi-badge-lg" if taille == "large" else "esi-badge"
    st.markdown(f"""
    <div style="text-align:center;margin:16px 0">
        <div class="{classe} esi-{esi}">{esi}</div>
        <div style="font-size:14px;font-weight:600;color:#4A6080;
                    margin-top:8px;letter-spacing:0.5px">
            {labels.get(esi,'')}
        </div>
    </div>
    """, unsafe_allow_html=True)


def couleur_esi(esi: int) -> str:
    couleurs = {1:"#C8001E",2:"#E05A00",3:"#C49A00",4:"#2D9B6F",5:"#1A6BC4"}
    return couleurs.get(esi, "#888")


def libelle_esi(esi: int) -> str:
    labels = {
        1:"CRITIQUE — Prise en charge immédiate",
        2:"TRÈS URGENT — Dans les 15 minutes",
        3:"URGENT — Dans les 30 minutes",
        4:"SEMI-URGENT — Dans l'heure",
        5:"NON URGENT — File ordinaire"
    }
    return labels.get(esi, "")


def afficher_sidebar():
    import base64
    import os
    logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "logo_ecc.webp")
    logo_b64 = ""
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as img_file:
            logo_b64 = base64.b64encode(img_file.read()).decode()
    img_tag = f'<img src="data:image/webp;base64,{logo_b64}" style="width: 60px; height: 60px; border-radius: 12px; margin-bottom: 5px;">' if logo_b64 else "🏥"

    with st.sidebar:
        st.markdown(f"""
        <div style="text-align:center;padding:24px 16px 16px">
            <div>{img_tag}</div>
            <h2 style="color:white;margin:8px 0 4px;font-size:20px;
                       font-family:'Sora',sans-serif;font-weight:700">
                HealthGate
            </h2>
            <p style="color:rgba(255,255,255,0.5);font-size:11px;margin:0;
                      letter-spacing:0.5px">
                TRIAGE MÉDICAL INTELLIGENT
            </p>
        </div>
        <hr style="border-color:rgba(255,255,255,0.1);margin:0 0 16px">
        """, unsafe_allow_html=True)

        pages = [
            ("👤", "Borne Patient",    "pages/1_borne_patient"),
            ("🛋️", "Salle d'attente",  "pages/2_salle_attente"),
            ("👨‍⚕️", "Dr. El Amrani",   "pages/3_medecin_M1"),
            ("👨‍⚕️", "Dr. Bensouda",    "pages/4_medecin_M2"),
        ]
        
        for icone, nom, page in pages:
            if st.button(f"{icone}  {nom}", use_container_width=True):
                st.switch_page(f"{page}.py")
