import re
from pathlib import Path

def fix_salle_attente():
    p = Path("ml/app/pages/2_salle_attente.py")
    c = p.read_text('utf-8')
    
    # We will do a simpler robust manual replace because there are only 4 metrics!
    c = re.sub(r'col1\.markdown\(f\"\"\"[\s\S]*?\"\"\", unsafe_allow_html=True\)\)',
       '''col1.markdown(f\"\"\"
<div class="metric-card">
    <div class="metric-val">{len(file)}</div>
    <div class="metric-label">Patients en attente</div>
</div>
\"\"\", unsafe_allow_html=True)''', c)

    c = re.sub(r'col2\.markdown\(f\"\"\"[\s\S]*?\"\"\", unsafe_allow_html=True\)\)',
       '''col2.markdown(f\"\"\"
<div class="metric-card">
    <div class="metric-val">{len(critiques)}</div>
    <div class="metric-label">?? Niveaux critiques</div>
</div>
\"\"\", unsafe_allow_html=True)''', c)

    c = re.sub(r'col3\.markdown\(f\"\"\"[\s\S]*?\"\"\", unsafe_allow_html=True\} min\"\)',
       '''val3 = f"{calculer_attente_moyenne(file)} min"
    col3.markdown(f\"\"\"
<div class="metric-card">
    <div class="metric-val">{val3}</div>
    <div class="metric-label">Attente moyenne</div>
</div>
\"\"\", unsafe_allow_html=True)''', c)

    c = re.sub(r'col4\.markdown\(f\"\"\"[\s\S]*?\"\"\", unsafe_allow_html=True\)\)',
       '''val4 = time.strftime('%H:%M:%S')
    col4.markdown(f\"\"\"
<div class="metric-card">
    <div class="metric-val">{val4}</div>
    <div class="metric-label">Mise à jour</div>
</div>
\"\"\", unsafe_allow_html=True)''', c)

    p.write_text(c, 'utf-8')

fix_salle_attente()
