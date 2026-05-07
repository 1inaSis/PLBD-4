import os
import glob

def refactor_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # We want to import afficher_sidebar
    content = content.replace('from utils.styles import injecter_css, afficher_header', 'from utils.styles import injecter_css, afficher_header, afficher_sidebar')
    content = content.replace('from app.utils.styles import injecter_css, afficher_header', 'from app.utils.styles import injecter_css, afficher_header, afficher_sidebar')
    
    # Then we call it after afficher_header
    content = content.replace('afficher_header("HealthGate")\n', 'afficher_header("HealthGate")\n    afficher_sidebar()\n')
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

for p in glob.glob('ml/app/pages/*.py'):
    refactor_file(p)
