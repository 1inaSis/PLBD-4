import re
from pathlib import Path

def fix_salle_attente():
    p = Path("ml/app/pages/3_medecin_M1.py")
    c = p.read_text('utf-8')
    
    # We will do a simpler robust manual replace
    c = re.sub(r'st\.markdown\(f\"\"\"[\s\S]*?\"\"\", unsafe_allow_html=True\}\"\)',
       '''val = f"{rapport.get('confiance', '—')}"
        st.markdown(f\"\"\"
<div class="metric-card">
    <div class="metric-val">{val}</div>
    <div class="metric-label">Indice de confiance</div>
</div>
\"\"\", unsafe_allow_html=True)''', c)

    c = re.sub(r'st\.markdown\(f\"\"\"[\s\S]*?\"\"\", unsafe_allow_html=True\)\)',
       '''val = f"{len([1 for q in rapport.get('features', {}).values() if q == 1])}"
        st.markdown(f\"\"\"
<div class="metric-card">
    <div class="metric-val">{val}</div>
    <div class="metric-label">Symptômes identifiés</div>
</div>
\"\"\", unsafe_allow_html=True)''', c)

    p.write_text(c, 'utf-8')

fix_salle_attente()
