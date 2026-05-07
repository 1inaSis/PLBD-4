import re

with open('ml/app/utils/styles.py', 'r', encoding='utf-8') as f:
    style_text = f.read()

# Replace header
start_h = style_text.find('def afficher_header(')
if start_h != -1:
    end_h = style_text.find('def afficher_constante_card(', start_h)
    new_h = '''def afficher_header(titre: str, sous_titre: str = "Borne de Triage Médical Intelligent"):
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
                 style="font-family:\\'JetBrains Mono\\',monospace;font-size:16px;
                        font-weight:500;color:rgba(255,255,255,0.9);letter-spacing:1px">
                {heure_actuelle}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

'''
    if end_h != -1:
        style_text = style_text[:start_h] + new_h + style_text[end_h:]

# Replace sidebar
start_s = style_text.find('def afficher_sidebar()')
if start_s != -1:
    new_s = '''def afficher_sidebar():
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
        import streamlit as st
        for icone, nom, page in pages:
            if st.button(f"{icone}  {nom}", use_container_width=True):
                st.switch_page(f"app/{page}.py")\n
'''
    style_text = style_text[:start_s] + new_s

# Clean up status emojis
style_text = style_text.replace('statut_txt = "?? CRITIQUE"', 'statut_txt = "🚨 CRITIQUE"')
style_text = style_text.replace('statut_txt = "?? ATTENTION"', 'statut_txt = "⚠️ ATTENTION"')
style_text = style_text.replace('statut_txt = "?? NORMALE"', 'statut_txt = "✅ NORMALE"')

with open('ml/app/utils/styles.py', 'w', encoding='utf-8') as f:
    f.write(style_text)
