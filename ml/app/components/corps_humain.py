import streamlit as st
import streamlit.components.v1 as components
import os

_frontend_dir = os.path.join(os.path.dirname(__file__), "corps_humain_frontend")
os.makedirs(_frontend_dir, exist_ok=True)
_index_path = os.path.join(_frontend_dir, "index.html")

ZONES_CORPS = {
    "tete":           {"label": "Tête / Visage",     "cx": 200, "cy": 50,  "r": 35},
    "cou":            {"label": "Cou / Gorge",        "cx": 200, "cy": 100, "r": 18},
    "poitrine":       {"label": "Poitrine / Cœur",    "cx": 200, "cy": 155, "r": 40},
    "ventre":         {"label": "Ventre / Abdomen",   "cx": 200, "cy": 220, "r": 38},
    "bas_ventre":     {"label": "Bas-ventre",          "cx": 200, "cy": 275, "r": 28},
    "epaule_gauche":  {"label": "Épaule gauche",      "cx": 135, "cy": 140, "r": 22},
    "epaule_droite":  {"label": "Épaule droite",      "cx": 265, "cy": 140, "r": 22},
    "bras_gauche":    {"label": "Bras gauche",         "cx": 110, "cy": 195, "r": 18},
    "bras_droit":     {"label": "Bras droit",          "cx": 290, "cy": 195, "r": 18},
    "hanche_gauche":  {"label": "Hanche / Dos gauche","cx": 160, "cy": 270, "r": 22},
    "hanche_droite":  {"label": "Hanche / Dos droit", "cx": 240, "cy": 270, "r": 22},
    "jambe_gauche":   {"label": "Jambe gauche",        "cx": 175, "cy": 350, "r": 20},
    "jambe_droite":   {"label": "Jambe droite",        "cx": 225, "cy": 350, "r": 20},
    "pied_gauche":    {"label": "Pied / Cheville gauche","cx": 170,"cy": 430,"r": 18},
    "pied_droit":     {"label": "Pied / Cheville droit","cx": 230,"cy": 430,"r": 18},
}

zones_svg = ""
for zone_id, zone in ZONES_CORPS.items():
    zones_svg += f"""
    <circle
        id="{zone_id}"
        cx="{zone['cx']}" cy="{zone['cy']}" r="{zone['r']}"
        fill="rgba(0,168,232,0.15)" stroke="#00A8E8" stroke-width="2"
        style="cursor:pointer; transition: all 0.2s;"
        onmouseover="this.style.fill='rgba(0,168,232,0.4)'"
        onmouseout="this.style.fill='rgba(0,168,232,0.15)'"
        onclick="selectionnerZone('{zone_id}', '{zone['label']}')"
    />
    <text x="{zone['cx']}" y="{zone['cy'] + 4}" text-anchor="middle" font-size="9" font-family="Inter" fill="#0A2342" pointer-events="none" style="font-weight:500">{zone['label'][:8]}</text>
    """

html_corps = f"""
<!DOCTYPE html>
<html>
<head>
<style>
    body {{ margin:0; padding:0; background:transparent; font-family:Inter,sans-serif; overflow:hidden; }}
    #zone-selectionnee {{ margin-top:12px; padding:10px 16px; background:#E8F7FD; border:1px solid #00A8E8; border-radius:8px; font-size:14px; color:#0A2342; font-weight:500; display:none; text-align:center; }}
    .titre {{ text-align:center; font-size:14px; color:#4A6080; margin-bottom:8px; }}
</style>
</head>
<body>
<p class="titre">👆 Cliquez sur la partie du corps qui vous fait mal</p>
<div style="display:flex; justify-content:center;">
<svg width="400" height="480" viewBox="0 0 400 480" xmlns="http://www.w3.org/2000/svg" style="background:#F7F9FC; border-radius:12px; border:1px solid #D1DCE8;">
    <ellipse cx="200" cy="52" rx="32" ry="38" fill="#E8EFF7" stroke="#C5D0DC" stroke-width="1.5"/>
    <rect x="188" y="85" width="24" height="22" fill="#E8EFF7" stroke="#C5D0DC" stroke-width="1.5"/>
    <ellipse cx="200" cy="175" rx="55" ry="65" fill="#E8EFF7" stroke="#C5D0DC" stroke-width="1.5"/>
    <ellipse cx="200" cy="268" rx="48" ry="28" fill="#E8EFF7" stroke="#C5D0DC" stroke-width="1.5"/>
    <ellipse cx="112" cy="195" rx="16" ry="52" fill="#E8EFF7" stroke="#C5D0DC" stroke-width="1.5"/>
    <ellipse cx="288" cy="195" rx="16" ry="52" fill="#E8EFF7" stroke="#C5D0DC" stroke-width="1.5"/>
    <ellipse cx="178" cy="360" rx="20" ry="68" fill="#E8EFF7" stroke="#C5D0DC" stroke-width="1.5"/>
    <ellipse cx="222" cy="360" rx="20" ry="68" fill="#E8EFF7" stroke="#C5D0DC" stroke-width="1.5"/>
    <ellipse cx="172" cy="433" rx="22" ry="10" fill="#E8EFF7" stroke="#C5D0DC" stroke-width="1.5"/>
    <ellipse cx="228" cy="433" rx="22" ry="10" fill="#E8EFF7" stroke="#C5D0DC" stroke-width="1.5"/>
    <rect x="193" y="148" width="14" height="40" rx="3" fill="rgba(204,0,0,0.2)"/>
    <rect x="182" y="160" width="36" height="14" rx="3" fill="rgba(204,0,0,0.2)"/>
    {zones_svg}
</svg>
</div>
<div id="zone-selectionnee">✅ Zone sélectionnée : <span id="zone-nom"></span></div>

<script>
function sendToStreamlit(type, data) {{
    window.parent.postMessage({{
        isStreamlitMessage: true,
        type: type,
        ...data
    }}, '*');
}}

function selectionnerZone(id, label) {{
    document.querySelectorAll('circle').forEach(c => {{
        c.style.fill = 'rgba(0,168,232,0.15)';
    }});
    document.getElementById(id).style.fill = 'rgba(204,0,0,0.4)';
    document.getElementById('zone-selectionnee').style.display = 'block';
    document.getElementById('zone-nom').textContent = label;

    sendToStreamlit('streamlit:setComponentValue', {{value: {{zone_id: id, zone_label: label}}}});
}}

sendToStreamlit('streamlit:componentReady', {{apiVersion: 1}});
sendToStreamlit('streamlit:setFrameHeight', {{height: 580}});
</script>
</body>
</html>
"""

# Re-write the file unconditionally
with open(_index_path, "w", encoding="utf-8") as f:
    f.write(html_corps)

_corps_humain_component = components.declare_component("corps_humain", path=_frontend_dir)

def afficher_corps_humain() -> str:
    zone = _corps_humain_component(key="svg_corps_humain")
    return zone.get("zone_label") if isinstance(zone, dict) else None

