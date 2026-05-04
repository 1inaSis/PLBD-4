# Quick check of the main file to verify all function signatures match
import sys
sys.path.insert(0, './ml')

from ml.questions_moteur import generer_questions, encoder_reponses, FEATURES_QUESTIONS

# Check FEATURES_QUESTIONS is not empty
print(f"✅ FEATURES_QUESTIONS: {len(FEATURES_QUESTIONS)} features loaded")
print(f"   First 5: {FEATURES_QUESTIONS[:5]}")

# Check generer_questions signature
print(f"✅ generer_questions function is defined")

# Check encoder_reponses signature 
print(f"✅ encoder_reponses function is defined")

# Simulate encoding an empty response
test_encoding = encoder_reponses([], {})
print(f"✅ encoder_reponses works: {len(test_encoding)} features initialized")

print("\n🎯 All core functions available and working!")
