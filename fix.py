import sys

with open('ml/questions_moteur.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace block
import re

old_block = '''    prompt_user = f"Le patient a {age} ans, sexe {'Homme' if sex==1 else 'Femme'}.\\n"
    prompt_user += f"Tension et Constantes : {json.dumps(constantes)}\\n"
    prompt_user += f"Motif ou symptÃ´mes actuels : {symptom_text}\\n\\n"
    prompt_user += "GÃ©nÃ¨re exactement 4 questions mÃ©dicales d'urgence pertinentes et directes Ã  poser Ã  ce patient "
    prompt_user += "pour analyser l'urgence ou prÃ©ciser son symptÃ´me principal.\\n"
    prompt_user += "Tu peux poser des questions ouvertes, des choix multiples ou des oui/non.\\n"
    prompt_user += "Donne UNIQUEMENT un tableau JSON natif contenant des objets sous la forme:\\n"
    prompt_user += "[\\n  {\\n"
    prompt_user += '    "id": "q_id_unique",\\n'
    prompt_user += '    "texte": "La question naturelle posÃ©e",\\n'
    prompt_user += '    "type": "choix" ou "oui_non" ou "texte_libre",\\n'
    prompt_user += '    "choix": ["Option 1", "Option 2"] (si type="choix"),\\n'
    prompt_user += '    "feature_name": "le_nom_de_la_feature"\\n'
    prompt_user += "  }\\n]\\n"
    prompt_user += "Ne met RIEN DEVANT ou APRES le JSON. MÃªme pas de '`json' ou de texte."'''


new_block = '''    prompt_user = f"Le patient a {age} ans, sexe {'Homme' if sex==1 else 'Femme'}.\\n"
    prompt_user += f"Tension et Constantes : {json.dumps(constantes)}\\n"
    prompt_user += f"Motif ou symptÃ´mes actuels : {symptom_text}\\n\\n"
    prompt_user += "GÃ©nÃ¨re exactement 4 questions mÃ©dicales d'urgence pertinentes, directes et variables Ã  poser Ã  ce patient "
    prompt_user += "pour analyser l'urgence ou prÃ©ciser son symptÃ´me principal. Varie la premiere question par rapport a d'habitude!\\n"
    prompt_user += "Tu peux poser des questions ouvertes, des choix multiples ou des oui/non.\\n"
    prompt_user += "TRES IMPORTANT : Pour le champ 'feature_name', tu DOIS OBLIGATOIREMENT choisir une seule option pertinente PARMI CETTE LISTE EXACTE et aucune autre (sinon crash) :\\n"
    prompt_user += str(FEATURES_QUESTIONS) + "\\n\\n"
    prompt_user += "Donne UNIQUEMENT un tableau JSON natif contenant des objets sous la forme:\\n"
    prompt_user += "[\\n  {\\n"
    prompt_user += '    "id": "q_id_unique",\\n'
    prompt_user += '    "texte": "La question naturelle posÃ©e",\\n'
    prompt_user += '    "type": "choix" ou "oui_non" ou "texte_libre",\\n'
    prompt_user += '    "choix": ["Option 1", "Option 2"] (si type="choix"),\\n'
    prompt_user += '    "feature_name": "q_la_feature_exacte_choisie_dans_la_liste"\\n'
    prompt_user += "  }\\n]\\n"
    prompt_user += "Ne met RIEN DEVANT ou APRES le JSON. MÃªme pas de markdown."'''

text = text.replace(old_block, new_block).replace("valid_features = \", \".join(FEATURES_QUESTIONS[:15]) + \"... (et d'autres)\"", "")

with open('ml/questions_moteur.py', 'w', encoding='utf-8') as f:
    f.write(text)

