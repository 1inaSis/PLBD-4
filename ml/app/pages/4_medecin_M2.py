import streamlit as st
import sys
import os
# Ajouter le dossier courant (ml/app) au sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import importlib.util
spec = importlib.util.spec_from_file_location("M1", os.path.join(os.path.dirname(__file__), "3_medecin_M1.py"))
m1 = importlib.util.module_from_spec(spec)
sys.modules["M1"] = m1
spec.loader.exec_module(m1)

if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="Dr. Bensouda — HealthGate")
    m1.page_medecin("m2", "Dr. Bensouda")
