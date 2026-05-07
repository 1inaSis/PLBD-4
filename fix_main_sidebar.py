import sys
with open('ml/app/main.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re
# remove the with st.sidebar block in main.py
text = re.sub(r'with st\.sidebar:.*?st\.switch_page\(f"app/{page}\.py"\)', '', text, flags=re.DOTALL)

# add afficher_sidebar call
text = text.replace('from utils.styles import injecter_css, afficher_header', 'from utils.styles import injecter_css, afficher_header, afficher_sidebar')
text = text.replace('afficher_header("HealthGate")', 'afficher_header("HealthGate")\nafficher_sidebar()')

with open('ml/app/main.py', 'w', encoding='utf-8') as f:
    f.write(text)
