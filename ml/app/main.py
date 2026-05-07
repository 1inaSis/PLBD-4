import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.styles import injecter_css, afficher_header, afficher_sidebar
import streamlit as st

st.set_page_config(
    page_title="HealthGate",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

injecter_css()
afficher_sidebar()
afficher_header("HealthGate")

# Content of main page
st.markdown("### Bienvenue sur HealthGate")

import os
img_path = r"C:\Users\sanmo\Downloads\Gemini_Generated_Image_8zy4gq8zy4gq8zy4.png"
if os.path.exists(img_path):
    st.image(img_path, use_column_width=True)

st.info("Veuillez sélectionner une interface dans le menu latéral pour commencer.")
