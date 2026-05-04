import sys
sys.path.insert(0, './ml')
from ml.questions_moteur import generer_questions
print(generer_questions({'temperature': 39, 'heart_rate': 110}, 'J ai tres mal a la poitrine', 40, 1))
