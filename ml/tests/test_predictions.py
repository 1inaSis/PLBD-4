"""
tests/test_predictions.py — Tests du pipeline HealthGate
Projet HealthGate | Centrale Casablanca | PLBD 4 | 2025-2026

Tests couverts :
  1. Module NLP (extraction de features depuis texte libre)
  2. Modèle Random Forest (prédiction ESI)
  3. File d'attente APQ-h (ajout, tri, dégradation, alertes)
  4. Tests d'intégration (pipeline complet)
"""

import sys
import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

# Ajouter le dossier parent au chemin Python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from nlp_extractor import extraire_features_nlp, normaliser_texte
from model_trainer import predire_esi
from queue_manager import GestionnaireFile, PatientEnFile
from questions_moteur import generer_questions, encoder_reponses
import predict_api


# ─────────────────────────────────────────────────────────────────────────────
# Tests du module NLP
# ─────────────────────────────────────────────────────────────────────────────

class TestNLPExtractor(unittest.TestCase):
    """Tests de l'extracteur de features NLP."""

    def test_detection_douleur_thoracique(self):
        """Doit détecter la douleur thoracique."""
        features = extraire_features_nlp(
            "J'ai très mal à la poitrine depuis ce matin"
        )
        self.assertEqual(features["nlp_chest_pain"], 1,
                         "Douleur thoracique non détectée")

    def test_detection_dyspnee(self):
        """Doit détecter la dyspnée (difficultés à respirer)."""
        features = extraire_features_nlp(
            "J'ai du mal à respirer, je suis essoufflé"
        )
        self.assertEqual(features["nlp_dyspnea"], 1,
                         "Dyspnée non détectée")

    def test_detection_perte_conscience(self):
        """Doit détecter la perte de connaissance."""
        features = extraire_features_nlp(
            "Il est inconscient, ne répond plus du tout"
        )
        self.assertEqual(features["nlp_loss_of_consciousness"], 1,
                         "Perte de connaissance non détectée")
        self.assertEqual(features["nlp_urgence_critique"], 1,
                         "Urgence critique non détectée")

    def test_detection_fievre(self):
        """Doit détecter la fièvre."""
        features = extraire_features_nlp(
            "J'ai de la fièvre à 39 degrés et des frissons"
        )
        self.assertEqual(features["nlp_fever"], 1, "Fièvre non détectée")

    def test_detection_trauma(self):
        """Doit détecter un traumatisme."""
        features = extraire_features_nlp(
            "Accident de voiture, fracture à la jambe"
        )
        self.assertEqual(features["nlp_trauma"], 1, "Trauma non détecté")

    def test_texte_vide(self):
        """Un texte vide ne doit activer aucune feature."""
        features = extraire_features_nlp("")
        for cle, valeur in features.items():
            self.assertEqual(valeur, 0,
                             f"Feature {cle} devrait être 0 pour texte vide")

    def test_texte_non_urgent(self):
        """Un renouvellement d'ordonnance ne doit pas déclencher d'urgence."""
        features = extraire_features_nlp(
            "Je veux renouveler mon ordonnance pour l'hypertension"
        )
        self.assertEqual(features["nlp_urgence_critique"], 0,
                         "Urgence critique ne devrait pas être détectée")
        self.assertEqual(features["nlp_chest_pain"], 0,
                         "Douleur thoracique ne devrait pas être détectée")

    def test_fautes_orthographe(self):
        """Le module doit être robuste aux fautes de frappe courantes."""
        features = extraire_features_nlp(
            "j ai tro mal au ventr depuis hier"
        )
        # Le score de douleur devrait être > 0 malgré les fautes
        self.assertGreater(features["nlp_pain_score"], 0,
                           "Le score de douleur devrait être > 0 malgré les fautes")

    def test_score_douleur_intense(self):
        """Doit estimer un score de douleur élevé pour une douleur intense."""
        features = extraire_features_nlp(
            "Douleur très forte, insupportable, je n'en peux plus"
        )
        self.assertGreaterEqual(features["nlp_pain_score"], 7,
                                "Score de douleur devrait être >= 7 pour douleur intense")

    def test_double_symptome(self):
        """Doit détecter plusieurs symptômes dans une même phrase."""
        features = extraire_features_nlp(
            "J'ai mal à la poitrine et du mal à respirer avec de la fièvre"
        )
        self.assertEqual(features["nlp_chest_pain"], 1)
        self.assertEqual(features["nlp_dyspnea"], 1)
        self.assertEqual(features["nlp_fever"], 1)


# ─────────────────────────────────────────────────────────────────────────────
# Tests du moteur de questions
# ─────────────────────────────────────────────────────────────────────────────

class TestQuestionsMoteur(unittest.TestCase):
    """Tests du générateur de questions ciblées."""

    def test_generation_questions_ciblees(self):
        questions = generer_questions(
            {"temperature": 39.4, "spo2": 91, "heart_rate": 128, "bp_systolic": 170, "bp_diastolic": 100},
            "J'ai très mal à la poitrine et du mal à respirer",
            58,
            1,
        )
        self.assertGreaterEqual(len(questions), 4)
        self.assertLessEqual(len(questions), 6)
        features = {q["feature_name"] for q in questions}
        self.assertTrue(
            bool(
                features.intersection(
                    {
                        "q_douleur_irradiee_bras",
                        "q_antecedent_infarctus",
                        "q_duree_dyspnee",
                        "q_dyspnee_aggrave_effort",
                    }
                )
            ),
            "Les questions devraient être ciblées sur les symptômes principaux",
        )

    def test_encodage_reponses(self):
        questions = [
            {"id": "q1", "texte": "Avez-vous de l'asthme ?", "type": "oui_non", "feature_name": "q_antecedent_asthme"},
            {"id": "q2", "texte": "Depuis combien de temps ?", "type": "choix", "choix": ["Moins de 24h", "1 à 3 jours", "Plus de 3 jours"], "feature_name": "q_duree_fievre"},
        ]
        features = encoder_reponses(questions, {"q1": "Oui", "q2": "1 à 3 jours"})
        self.assertEqual(features["q_antecedent_asthme"], 1)
        self.assertEqual(features["q_duree_fievre"], 1)


# ─────────────────────────────────────────────────────────────────────────────
# Tests du modèle Random Forest
# ─────────────────────────────────────────────────────────────────────────────

class TestModeleESI(unittest.TestCase):
    """Tests de prédiction du modèle Random Forest."""

    def _patient_critique(self) -> dict:
        """Patient avec signes critiques → ESI 1 attendu."""
        return {
            "age": 55, "sex": 1,
            "temperature": 34.5, "heart_rate": 35,
            "bp_systolic": 70, "bp_diastolic": 40,
            "spo2": 78, "respiratory_rate": 6,
            "glucose": 38, "pain_score": 9,
            "chest_pain": 1, "dyspnea": 1,
            "loss_of_consciousness": 1, "severe_bleeding": 0,
            "neurological_symptoms": 0, "abdominal_pain": 0,
            "fever": 0, "trauma": 0,
            "symptom_text": "Inconscient, ne respire plus",
        }

    def _patient_non_urgent(self) -> dict:
        """Patient avec signes normaux → ESI 5 attendu."""
        return {
            "age": 30, "sex": 0,
            "temperature": 36.8, "heart_rate": 72,
            "bp_systolic": 115, "bp_diastolic": 70,
            "spo2": 99, "respiratory_rate": 14,
            "glucose": 90, "pain_score": 0,
            "chest_pain": 0, "dyspnea": 0,
            "loss_of_consciousness": 0, "severe_bleeding": 0,
            "neurological_symptoms": 0, "abdominal_pain": 0,
            "fever": 0, "trauma": 0,
            "symptom_text": "Je veux renouveler mon ordonnance",
        }

    def test_structure_resultat(self):
        """La prédiction doit retourner les champs attendus."""
        resultat = predire_esi(self._patient_non_urgent())
        self.assertIn("esi_predit", resultat)
        self.assertIn("probabilites", resultat)
        self.assertIn("confiance", resultat)

    def test_esi_valide(self):
        """L'ESI prédit doit être compris entre 1 et 5."""
        for patient in [self._patient_critique(), self._patient_non_urgent()]:
            resultat = predire_esi(patient)
            self.assertIn(resultat["esi_predit"], [1, 2, 3, 4, 5],
                          "ESI prédit hors de la plage [1, 5]")

    def test_patient_critique_esi_bas(self):
        """Un patient critique doit avoir ESI 1 ou 2."""
        resultat = predire_esi(self._patient_critique())
        self.assertLessEqual(resultat["esi_predit"], 2,
                             "Patient critique devrait avoir ESI 1 ou 2")

    def test_patient_non_urgent_esi_haut(self):
        """Un patient non urgent doit avoir ESI 4 ou 5."""
        resultat = predire_esi(self._patient_non_urgent())
        self.assertGreaterEqual(resultat["esi_predit"], 4,
                                "Patient non urgent devrait avoir ESI 4 ou 5")

    def test_confiance_valide(self):
        """La confiance doit être entre 0 et 100."""
        resultat = predire_esi(self._patient_non_urgent())
        self.assertGreaterEqual(resultat["confiance"], 0)
        self.assertLessEqual(resultat["confiance"], 100)

    def test_somme_probabilites(self):
        """La somme des probabilités doit être proche de 100%."""
        resultat = predire_esi(self._patient_non_urgent())
        somme = sum(resultat["probabilites"].values())
        self.assertAlmostEqual(somme, 100.0, delta=1.0,
                               msg="La somme des probabilités doit être ~100%")

    def test_sans_symptom_text(self):
        """La prédiction doit fonctionner même sans symptom_text."""
        patient = self._patient_non_urgent()
        del patient["symptom_text"]
        resultat = predire_esi(patient)
        self.assertIn("esi_predit", resultat)


# ─────────────────────────────────────────────────────────────────────────────
# Tests de la file d'attente APQ-h
# ─────────────────────────────────────────────────────────────────────────────

class TestFileAttente(unittest.TestCase):
    """Tests de la file d'attente dynamique APQ-h."""

    def setUp(self):
        """Crée une file vide pour chaque test."""
        self.file = GestionnaireFile()
        self.constantes = {"spo2": 95, "heart_rate": 80}

    def test_ajout_patient(self):
        """L'ajout d'un patient doit l'inclure dans la file."""
        self.file.ajouter_patient("PT001", 3, 35, self.constantes)
        self.assertIn("PT001", self.file.file)

    def test_retrait_patient(self):
        """Le retrait d'un patient doit le supprimer de la file."""
        self.file.ajouter_patient("PT001", 3, 35, self.constantes)
        self.file.retirer_patient("PT001")
        self.assertNotIn("PT001", self.file.file)

    def test_retrait_patient_inexistant(self):
        """Le retrait d'un patient inexistant doit retourner None."""
        resultat = self.file.retirer_patient("PT_INEXISTANT")
        self.assertIsNone(resultat)

    def test_tri_par_priorite(self):
        """La file doit être triée par score décroissant (ESI 1 en premier)."""
        self.file.ajouter_patient("PT_ESI3", 3, 35, self.constantes)
        self.file.ajouter_patient("PT_ESI5", 5, 30, self.constantes)
        self.file.ajouter_patient("PT_ESI1", 1, 40, self.constantes)

        file_triee = self.file.get_file_triee()
        # Le premier doit être ESI 1 (score le plus élevé)
        self.assertEqual(file_triee[0].patient_id, "PT_ESI1")
        # Le dernier doit être ESI 5 (score le plus bas)
        self.assertEqual(file_triee[-1].patient_id, "PT_ESI5")

    def test_position_patient(self):
        """La position d'un patient doit être correcte."""
        self.file.ajouter_patient("PT_ESI3", 3, 35, self.constantes)
        self.file.ajouter_patient("PT_ESI1", 1, 40, self.constantes)

        # ESI 1 doit être en position 1
        self.assertEqual(self.file.get_position_patient("PT_ESI1"), 1)
        # ESI 3 doit être en position 2
        self.assertEqual(self.file.get_position_patient("PT_ESI3"), 2)

    def test_position_patient_inexistant(self):
        """La position d'un patient inexistant doit retourner None."""
        position = self.file.get_position_patient("PT_INEXISTANT")
        self.assertIsNone(position)

    def test_degradation_clinique(self):
        """Une dégradation clinique doit augmenter le score du patient."""
        self.file.ajouter_patient("PT001", 4, 35, self.constantes)
        score_initial = self.file.file["PT001"].score

        self.file.signaler_degradation(
            "PT001",
            nouvelles_constantes={"spo2": 85, "heart_rate": 140},
            nouvel_esi=2
        )

        score_apres = self.file.file["PT001"].score
        self.assertGreater(score_apres, score_initial,
                           "Le score doit augmenter après dégradation")

    def test_degradation_met_a_jour_esi(self):
        """Une dégradation doit mettre à jour l'ESI actuel du patient."""
        self.file.ajouter_patient("PT001", 4, 35, self.constantes)
        self.file.signaler_degradation("PT001", {}, 1)
        self.assertEqual(self.file.file["PT001"].esi_actuel, 1)

    def test_bonus_vulnerabilite_enfant(self):
        """Un enfant de moins de 5 ans doit avoir un bonus de vulnérabilité."""
        self.file.ajouter_patient("PT_ENFANT", 3, 3, self.constantes)   # 3 ans
        self.file.ajouter_patient("PT_ADULTE", 3, 30, self.constantes)  # 30 ans

        score_enfant = self.file.file["PT_ENFANT"].score
        score_adulte = self.file.file["PT_ADULTE"].score
        self.assertGreater(score_enfant, score_adulte,
                           "L'enfant doit avoir un score plus élevé grâce au bonus vulnérabilité")

    def test_bonus_vulnerabilite_senior(self):
        """Un patient de plus de 70 ans doit avoir un bonus de vulnérabilité."""
        self.file.ajouter_patient("PT_SENIOR", 3, 75, self.constantes)  # 75 ans
        self.file.ajouter_patient("PT_ADULTE", 3, 30, self.constantes)  # 30 ans

        score_senior = self.file.file["PT_SENIOR"].score
        score_adulte = self.file.file["PT_ADULTE"].score
        self.assertGreater(score_senior, score_adulte,
                           "Le senior doit avoir un score plus élevé grâce au bonus vulnérabilité")

    def test_alerte_esi1(self):
        """Un patient ESI 1 doit déclencher une alerte immédiatement."""
        self.file.ajouter_patient("PT001", 1, 40, self.constantes)
        self.assertTrue(self.file.file["PT001"].alerte_active,
                        "Alerte ESI 1 doit être active dès l'ajout")

    def test_marquer_alerte_lue(self):
        """L'alerte d'un patient doit pouvoir être marquée comme lue."""
        self.file.ajouter_patient("PT001", 1, 40, self.constantes)
        self.file.marquer_alerte_lue("PT001")
        self.assertTrue(self.file.file["PT001"].alerte_lue,
                        "L'alerte doit être marquée comme lue")

    def test_etat_file_structure(self):
        """L'état de la file doit contenir les champs attendus."""
        self.file.ajouter_patient("PT001", 3, 35, self.constantes)
        etat = self.file.etat_file()

        self.assertIn("horodatage", etat)
        self.assertIn("nb_patients", etat)
        self.assertIn("file_attente", etat)
        self.assertIn("alertes_actives", etat)

    def test_file_vide(self):
        """Une file vide doit retourner un état valide."""
        etat = self.file.etat_file()
        self.assertEqual(etat["nb_patients"], 0)
        self.assertEqual(len(etat["file_attente"]), 0)


# ─────────────────────────────────────────────────────────────────────────────
# Tests d'intégration — Pipeline complet
# ─────────────────────────────────────────────────────────────────────────────

class TestIntegration(unittest.TestCase):
    """Tests d'intégration du pipeline NLP → Modèle → File."""

    def test_pipeline_patient_essoufle(self):
        """Pipeline complet pour un patient avec essoufflement et douleur thoracique."""
        texte = "J'ai très mal à la poitrine depuis ce matin et j'ai du mal à respirer"

        # Étape 1 : NLP
        features_nlp = extraire_features_nlp(texte)
        self.assertEqual(features_nlp["nlp_chest_pain"], 1)
        self.assertEqual(features_nlp["nlp_dyspnea"], 1)

        # Étape 2 : Prédiction ESI
        donnees_patient = {
            "age": 52, "sex": 1,
            "temperature": 37.8, "heart_rate": 110,
            "bp_systolic": 155, "bp_diastolic": 95,
            "spo2": 92, "respiratory_rate": 24,
            "glucose": 130, "pain_score": 7,
            "chest_pain": 1, "dyspnea": 1,
            "loss_of_consciousness": 0, "severe_bleeding": 0,
            "neurological_symptoms": 0, "abdominal_pain": 0,
            "fever": 0, "trauma": 0,
            "symptom_text": texte,
        }
        resultat = predire_esi(donnees_patient)
        self.assertLessEqual(resultat["esi_predit"], 3,
                             "Patient avec douleur thoracique + dyspnée doit être ESI ≤ 3")

    def test_pipeline_patient_mineur(self):
        """Pipeline complet pour un patient non urgent."""
        texte = "Je veux renouveler mon ordonnance"
        features_nlp = extraire_features_nlp(texte)

        donnees_patient = {
            "age": 40, "sex": 0,
            "temperature": 36.8, "heart_rate": 72,
            "bp_systolic": 115, "bp_diastolic": 70,
            "spo2": 99, "respiratory_rate": 14,
            "glucose": 90, "pain_score": 0,
            "chest_pain": 0, "dyspnea": 0,
            "loss_of_consciousness": 0, "severe_bleeding": 0,
            "neurological_symptoms": 0, "abdominal_pain": 0,
            "fever": 0, "trauma": 0,
            "symptom_text": texte,
        }
        resultat = predire_esi(donnees_patient)
        self.assertGreaterEqual(resultat["esi_predit"], 4,
                                "Patient non urgent doit être ESI ≥ 4")


# ─────────────────────────────────────────────────────────────────────────────
# Tests du contrat API Flask
# ─────────────────────────────────────────────────────────────────────────────

class TestAPIContract(unittest.TestCase):
    """Valide les endpoints critiques de l'API HealthGate."""

    def setUp(self):
        self.client = predict_api.app.test_client()
        predict_api.patients_session.clear()
        predict_api.gestionnaire_file.file.clear()
        for med in predict_api.MEDECINS.values():
            med["patients"].clear()

    def test_api_sante_ok(self):
        response = self.client.get("/api/sante")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["statut"], "ok")
        self.assertIn("queue_patients", data)

    @patch("predict_api.scanner_piece_identite")
    @patch("predict_api.lire_toutes_constantes")
    @patch("predict_api.predire_esi")
    def test_parcours_minimal_scan_to_triage(self, mock_predire, mock_constantes, mock_scanner):
        mock_scanner.return_value = {
            "nom": "TEST",
            "prenom": "PATIENT",
            "age": 45,
            "sexe": "M",
        }
        mock_constantes.return_value = {
            "temperature": 37.3,
            "spo2": 96,
            "heart_rate": 86,
            "bp_systolic": 130,
            "bp_diastolic": 82,
            "respiratory_rate": 18,
            "glucose": 95,
        }
        mock_predire.return_value = {
            "esi_predit": 3,
            "confiance": 82.4,
            "diagnostic_probable": "Syndrome infectieux febrile",
            "diagnostic_encode": 0,
            "probabilites": {"ESI_1": 1.0, "ESI_2": 10.0, "ESI_3": 70.0, "ESI_4": 15.0, "ESI_5": 4.0},
        }

        scan_res = self.client.post("/api/scanner", json={})
        self.assertEqual(scan_res.status_code, 200)
        session_id = scan_res.get_json()["session_id"]

        sympt_res = self.client.post(
            "/api/symptomes",
            json={"session_id": session_id, "symptom_text": "fievre et toux"},
        )
        self.assertEqual(sympt_res.status_code, 200)

        q_res = self.client.post(
            "/api/questions",
            json={"session_id": session_id, "constantes": mock_constantes.return_value},
        )
        self.assertEqual(q_res.status_code, 200)

        rep_res = self.client.post(
            "/api/questions/reponses",
            json={"session_id": session_id, "reponses": {}},
        )
        self.assertEqual(rep_res.status_code, 200)

        triage_res = self.client.post(
            "/api/triage",
            json={
                "session_id": session_id,
                "constantes": mock_constantes.return_value,
                "question_reponses": {},
            },
        )
        self.assertEqual(triage_res.status_code, 200)
        triage_data = triage_res.get_json()
        self.assertEqual(triage_data["statut"], "succes")
        self.assertIn("patient_id", triage_data)

        queue_res = self.client.get(f"/api/queue/{triage_data['patient_id']}")
        self.assertEqual(queue_res.status_code, 200)
        self.assertEqual(queue_res.get_json()["statut"], "succes")

    def test_alertes_endpoint(self):
        predict_api.gestionnaire_file.ajouter_patient(
            patient_id="PT-TEST",
            esi_predit=1,
            age=50,
            constantes={"spo2": 90, "heart_rate": 120, "temperature": 38.5},
        )
        predict_api.patients_session["PT-TEST"] = {"nom": "A", "prenom": "B"}

        alertes_res = self.client.get("/api/alertes")
        self.assertEqual(alertes_res.status_code, 200)
        data = alertes_res.get_json()
        self.assertGreaterEqual(data["nb_alertes"], 1)

        lu_res = self.client.post("/api/alertes/PT-TEST/lue")
        self.assertEqual(lu_res.status_code, 200)


# ─────────────────────────────────────────────────────────────────────────────
# Lancement des tests
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 65)
    print("TESTS DU PIPELINE HEALTHGATE")
    print("=" * 65)

    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()

    # Ajout des suites de tests
    suite.addTests(loader.loadTestsFromTestCase(TestNLPExtractor))
    suite.addTests(loader.loadTestsFromTestCase(TestModeleESI))
    suite.addTests(loader.loadTestsFromTestCase(TestFileAttente))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    resultat = runner.run(suite)

    print("\n" + "=" * 65)
    if resultat.wasSuccessful():
        print(f"✅ TOUS LES TESTS RÉUSSIS ({resultat.testsRun} tests)")
    else:
        print(f"❌ ÉCHECS : {len(resultat.failures)} | ERREURS : {len(resultat.errors)}")
    print("=" * 65)
