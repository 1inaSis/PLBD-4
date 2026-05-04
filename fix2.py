import json
with open('ml/questions_moteur.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
in_func = False
for line in lines:
    if line.startswith("def generer_questions("):
        in_func = True
        break
    new_lines.append(line)

new_func = '''def generer_questions(constantes: dict, symptom_text: str, age: int, sex: int) -> list:
    api_key = os.environ.get("GROQ_API_KEY", "")
    
    if not api_key:
        print("[AVERTISSEMENT] Pas de GROQ_API_KEY dÃ©finie.")
        return [{"id": "q1", "texte": "Avez-vous des antÃ©cÃ©dents ?", "type": "oui_non", "feature_name": "q_medicaments_generaux"}]

    prompt_system = "Tu es un infirmier d accueil urgentiste (IAO). Agis de faÃ§on TRÃˆS variÃ©e Ã  chaque patient."
    
    prompt_user = f"Le patient a {age} ans, sexe {'Homme' if sex==1 else 'Femme'}.\\n"
    prompt_user += f"Tension et Constantes : {json.dumps(constantes)}\\n"
    prompt_user += f"Motif ou symptÃ´mes actuels : {symptom_text}\\n\\n"
    prompt_user += "GÃ©nÃ¨re exactement 4 questions mÃ©dicales d'urgence pertinentes et directes Ã  poser.\\n"
    prompt_user += "TRES IMPORTANT: POUR NE PAS TOUJOURS POSER LA MEME 1ERE QUESTION (ex: Avez-vous des antecedents?), varie ENORMEMENT le choix de tes questions par rapport aux constantes !\\n"
    prompt_user += "Tu peux poser des questions ouvertes ('texte_libre'), des choix multiples ('choix') ou des 'oui_non'.\\n"
    prompt_user += "TRES IMPORTANT : Pour le champ 'feature_name', tu DOIS OBLIGATOIREMENT ET STRICTEMENT copier-coller une de ces valeurs et aucune autre, sinon le ML plantera :\\n"
    prompt_user += str(FEATURES_QUESTIONS) + "\\n\\n"
    prompt_user += "Donne UNIQUEMENT un tableau JSON natif contenant des objets sous la forme:\\n"
    prompt_user += "[\\n  {\\n"
    prompt_user += '    "id": "q_1",\\n'
    prompt_user += '    "texte": "La question posÃ©e",\\n'
    prompt_user += '    "type": "choix" ou "oui_non" ou "texte_libre",\\n'
    prompt_user += '    "choix": ["Option 1", "Option 2"] (si type="choix"),\\n'
    prompt_user += '    "feature_name": "q_la_feature_exacte"\\n'
    prompt_user += "  }\\n]\\n"
    prompt_user += "Ne met RIEN DEVANT ou APRES le JSON. PUREMENT du JSON formattÃ© valide."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": prompt_system},
            {"role": "user", "content": prompt_user}
        ],
        "temperature": 0.85
    }

    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=8)
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"].strip()
            if content.startswith("`"):
                content = content.replace("`json", "").replace("`", "").strip()
            questions = json.loads(content)
            if isinstance(questions, list):
                return questions
        else:
            print(f"[Erreur API] {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[Exception API] Erreur rÃ©seau ou de parsing JSON : {e}")

    return [{"id": "q_secours", "texte": "Que ressentez-vous?", "type": "texte_libre", "feature_name": "q_premiere_fois"}]
'''
with open('ml/questions_moteur.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
    f.write(new_func)
