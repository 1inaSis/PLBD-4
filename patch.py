import re
from pathlib import Path

def process_file(fpath: Path):
    content = fpath.read_text('utf-8')
    
    # We want to replace st.metric(...) calls in all forms
    def replace_metric(match):
        col_var = match.group(1)
        label = match.group(2)
        value = match.group(3)
        return (f"{col_var}.markdown(f\"\"\"\n"
                f"<div class=\\\"metric-card\\\">\n"
                f"    <div class=\\\"metric-val\\\">{{{value}}}</div>\n"
                f"    <div class=\\\"metric-label\\\">{label}</div>\n"
                f"</div>\n"
                f"\"\"\", unsafe_allow_html=True)")
    
    content = re.sub(r"([a-zA-Z0-9_]+)\.metric\(\s*[\"'](.*?)[\"']\s*,\s*(.*?)\s*\)", replace_metric, content)
    
    # Add injecter_css / afficher_header at the top of the main function
    func_pattern = re.compile(r"(def\s+page_[a-zA-Z0-9_]+\s*\([^)]*\):)")
    match = func_pattern.search(content)
    
    if match:
        original_def = match.group(1)
        # also clear the old calls so we don't duplicate
        content = re.sub(r'^\s*st\.set_page_config\([^)]*\)\n', '', content, flags=re.MULTILINE)
        content = re.sub(r'^\s*injecter_css_medical\(\)\n', '', content, flags=re.MULTILINE)
        
        snippet = """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from app.utils.styles import injecter_css, afficher_header

    st.set_page_config(
        page_title=\"HealthGate\",
        page_icon=\"🏥\",
        layout=\"wide\",
        initial_sidebar_state=\"collapsed\"
    )
    injecter_css()
    afficher_header(\"HealthGate\")
"""
        content = content.replace(original_def, original_def + "\n" + snippet)
        
    fpath.write_text(content, 'utf-8')

import os
print("Patching pages...")
pages_dir = Path("ml/app/pages")
for p in pages_dir.glob("*.py"):
    print(f"Patching {p.name}")
    process_file(p)
print("Done patching.")
