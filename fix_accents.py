import os

def fix_accents(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Fix known garbled sequences
        replacements = {
            'Ã©': 'é',
            'Ã¨': 'è',
            'Ãª': 'ê',
            'Ã´': 'ô',
            'Ã': 'à',  # 'Ã ' is 'à' but often followed by space, let's be careful
            'Ã¢': 'â',
            'Ã®': 'î',
            'Ã§': 'ç',
            'Ã»': 'û',
            'Ã¼': 'ü',
            'dÃ©tail': 'détail',
            'symptÃ´mes': 'symptômes',
            'antÃ©cÃ©dents': 'antécédents',
            'mÃ©dicaux': 'médicaux',
            'mÃ©dicales': 'médicales',
            'dÃ©finie': 'définie',
            'GeÃ©nÃ¨re': 'Génère', # fix previous typo
            'GÃ©nÃ¨re': 'Génère',
            'piochÃ©es': 'piochées',
            'Ã ': 'à',
            'ScuritÃ©': 'Sécurité',
            'gÃ©nÃ©rÃ©': 'généré',
            'rÃ©seau': 'réseau',
            'rÃ©ponses': 'réponses',
            'modÃ¨le': 'modèle',
            'mÃ©canisme': 'mécanisme'
        }
        
        for k, v in replacements.items():
            content = content.replace(k, v)
            
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
            
    except Exception as e:
        print(f"Error on {filepath}: {e}")

fix_accents('ml/questions_moteur_new.py')
fix_accents('ml/questions_moteur.py')
fix_accents('ml/app/components/questions_ui.py')
