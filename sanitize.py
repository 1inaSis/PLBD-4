import re
from pathlib import Path

def sanitize_page(fpath):
    content = fpath.read_text('utf-8')
    
    # Let's just find the def page_xxx(): line
    match = re.search(r'(def\s+page_[a-zA-Z0-9_]+\s*\([^)]*\):)', content)
    if not match: return
    
    func_def = match.group(1)
    
    # Split content into before and after func_def
    parts = content.split(func_def)
    if len(parts) != 2: return
    
    before, after = parts
    
    # we want to leave 'before' as is, except maybe stripping out old imports.
    # 'after' is the body of the function. We want to remove all the injected blocks.
    after = re.sub(r'^\s*import sys\n\s*from pathlib import Path\n.*\n.*\n', '', after, flags=re.MULTILINE)
    after = re.sub(r'^\s*st\.set_page_config\([^)]*\)\n', '', after, flags=re.MULTILINE)
    after = re.sub(r'^\s*injecter_css\(\)\n', '', after, flags=re.MULTILINE)
    after = re.sub(r'^\s*afficher_header\([^\)]*\)\n', '', after, flags=re.MULTILINE)
    
    # Just in case some st.set_page_config still survived because windows line endings or different indentation...
    # let's be aggressive:
    def remove_if_exists(text, pattern):
        return re.sub(pattern, '', text, flags=re.MULTILINE)
        
    after = remove_if_exists(after, r'^\s*import sys\s*\n')
    after = remove_if_exists(after, r'^\s*from pathlib import Path\s*\n')
    after = remove_if_exists(after, r'^\s*sys\.path\.insert[^\n]*\n')
    after = remove_if_exists(after, r'^\s*from app\.utils\.styles import injecter_css, afficher_header\s*\n')
    
    # We remove the local def afficher_header in 'before'
    before = re.sub(r'def afficher_header[^\n]*\n\s*[^\n]*\n', '', before)
    
    # Add the single correct injection:
    snippet = """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from app.utils.styles import injecter_css, afficher_header

    injecter_css()
    afficher_header(\"HealthGate\")
"""
    
    new_content = before + func_def + snippet + after
    fpath.write_text(new_content, 'utf-8')

for p in Path('ml/app/pages').glob('*.py'):
    sanitize_page(p)

