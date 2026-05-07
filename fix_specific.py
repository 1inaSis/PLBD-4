import re
from pathlib import Path

def process_file_no_metric(fpath: Path):
    content = fpath.read_text('utf-8')
    
    # Add injecter_css / afficher_header at the top of the main function
    func_pattern = re.compile(r"(def\s+page_[a-zA-Z0-9_]+\s*\([^)]*\):)")
    match = func_pattern.search(content)
    
    if match:
        original_def = match.group(1)
        content = re.sub(r'^\s*st\.set_page_config\([^)]*\)\n', '', content, flags=re.MULTILINE)
        content = re.sub(r'^\s*injecter_css_medical\(\)\n', '', content, flags=re.MULTILINE)
        
        snippet = """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from app.utils.styles import injecter_css, afficher_header

    st.set_page_config(
        page_title=\"HealthGate\",
        page_icon=\"??\",
        layout=\"wide\",
        initial_sidebar_state=\"collapsed\"
    )
    injecter_css()
    afficher_header(\"HealthGate\")
"""
        content = content.replace(original_def, original_def + "\n" + snippet)
    
    fpath.write_text(content, 'utf-8')

for p in ["ml/app/pages/2_salle_attente.py", "ml/app/pages/3_medecin_M1.py"]:
    process_file_no_metric(Path(p))
