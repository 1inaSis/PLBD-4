import json
import os
with open('ml/questions_moteur.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Fix encoding issues created by powershell earlier:
text = text.replace("ÃƒÂ©", "Ã©").replace("ÃƒÂ¨", "Ã¨").replace("ÃƒÂ´", "Ã´").replace("ÃƒÂ§", "Ã§").replace("ÃƒÂ ", "Ã ").replace("ÃƒË†", "Ãˆ")

with open('ml/questions_moteur.py', 'w', encoding='utf-8') as f:
    f.write(text)

