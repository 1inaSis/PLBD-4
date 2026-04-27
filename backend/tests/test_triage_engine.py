# tests/test_triage_engine.py
from triage_engine import TriageEngine
engine = TriageEngine()

def test_niveau1_spo2_critique():
    assert engine.evaluer({'spo2': 85})['niveau'] == 1

def test_niveau1_hyperthermie():
    assert engine.evaluer({'temperature': 41.5})['niveau'] == 1

def test_niveau2_fievre_elevee():
    assert engine.evaluer({'temperature': 40.2})['niveau'] == 2

def test_niveau3_fievre_moderee():
    assert engine.evaluer({'temperature': 39.0})['niveau'] == 3

def test_degradation_temporelle():
    assert engine.degradation_temporelle(3, 70) == 2
    assert engine.degradation_temporelle(3, 30) == 3

def test_valeurs_normales():
    assert engine.evaluer({'temperature': 37.0, 'spo2': 98})['niveau'] == 5