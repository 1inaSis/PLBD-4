import streamlit as st

COULEURS = {
    "primaire":        "#0A2342",   # Bleu marine médical
    "accent":          "#00A8E8",   # Bleu électrique
    "fond":            "#F0F4F8",   # Gris bleuté médical
    "surface":         "#FFFFFF",
    "bordure":         "#D1DCE8",
    "texte":           "#0D1B2A",
    "texte_secondaire": "#4A6080",

    "esi_1": "#CC0000",   
    "esi_2": "#FF6600",   
    "esi_3": "#FFB800",   
    "esi_4": "#00A651",   
    "esi_5": "#0072BB",   
}

def injecter_css_medical():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif !important;
    }

    .stApp {
        background-color: #F0F4F8;
    }

    #MainMenu { visibility: hidden; }
    header { visibility: hidden; }
    footer { visibility: hidden; }

    [data-testid="stSidebar"] {
        background-color: #0A2342 !important;
    }
    [data-testid="stSidebar"] * {
        color: #F0F4F8 !important;
    }
    
    /* Boutons géants style tactile pour ESI/Questions */
    div[data-testid="stButton"] > button {
        height: 60px;
        border-radius: 12px;
        font-size: 20px;
        font-weight: 600;
        transition: all 0.2s ease-in-out;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    div[data-testid="stButton"] > button[kind="primary"] {
        background-color: #00A651 !important; /* Vert par défaut primaire */
        color: white !important;
        border: None !important;
    }
    div[data-testid="stButton"] > button[kind="secondary"] {
        background-color: #CC0000 !important; /* Rouge par défaut secondaire (NON) */
        color: white !important;
        border: None !important;
    }
    div[data-testid="stButton"] > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.15);
    }
    
    @keyframes clignoterUrg {
        0% { background-color: #CC0000; box-shadow: 0 0 10px #CC0000; color: white; }
        50% { background-color: rgba(204, 0, 0, 0.2); box-shadow: 0 0 2px rgba(204,0,0,0.4); color: #CC0000; }
        100% { background-color: #CC0000; box-shadow: 0 0 10px #CC0000; color: white; }
    }
    .esi-1-critique {
        animation: clignoterUrg 1s infinite !important;
        border: 2px solid #CC0000;
        border-radius: 8px;
        padding: 5px 12px;
        font-weight: bold;
    }

    .moniteur-vital {
        background-color: #FFFFFF;
        border: 1px solid #D1DCE8;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        box-shadow: inset 0px 0px 4px rgba(0,0,0,0.05);
        margin-bottom: 10px;
    }
    .moniteur-valeur-urgente {
        color: #CC0000;
        font-family: 'JetBrains Mono', monospace;
        font-size: 32px;
        font-weight: 700;
    }
    .moniteur-valeur {
        color: #00A651;
        font-family: 'JetBrains Mono', monospace;
        font-size: 32px;
        font-weight: 700;
    }
    .moniteur-unite {
        font-size: 14px;
        color: #4A6080;
        margin-top: -5px;
    }
    </style>
    """, unsafe_allow_html=True)
