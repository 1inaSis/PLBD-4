"""
predict_api.py — Serveur principal HealthGate
Projet HealthGate | Centrale Casablanca | PLBD 4 | 2025-2026

Endpoints :
  POST /api/scanner          → Scanner pièce d'identité
  POST /api/symptomes        → Enregistrer symptômes
  GET  /api/constantes       → Lire capteurs (déclenché côté Pi)
  POST /api/triage           → Prédire ESI + ajouter file
  GET  /api/file             → État file d'attente
  POST /api/prise_en_charge  → Médecin prend en charge un patient
  GET  /api/medecin/<id>     → Patients du médecin <id>
  POST /api/degradation      → Signaler dégradation

WebSocket events (temps réel) :
  file_mise_a_jour    → envoyé à tous quand la file change
  alerte_critique     → envoyé aux médecins pour ESI 1/2
"""

import os
import uuid
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
from model_trainer import predire_esi
from queue_manager import gestionnaire_file
from nlp_extractor import extraire_features_nlp
from scanner_cin import scanner_piece_identite
from capteurs_raspberry import lire_toutes_constantes

# ─────────────────────────────────────────────────────────────────────────────
# Initialisation Flask + SocketIO
# ─────────────────────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder='.')
app.config['SECRET_KEY'] = 'healthgate-secret-2026'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Démarrer la mise à jour automatique de la file
gestionnaire_file.demarrer_mise_a_jour_auto(intervalle=60)

# ─────────────────────────────────────────────────────────────────────────────
# Base de données en mémoire (simple pour prototype)
# ─────────────────────────────────────────────────────────────────────────────

# Patients en cours de saisie (avant triage complet)
patients_session = {}

# Médecins disponibles
MEDECINS = {
    "M1": {
        "id":        "M1",
        "nom":       "Dr. El Amrani",
        "specialite": "Médecine générale — Urgences adultes",
        "patients":  [],
    },
    "M2": {
        "id":        "M2",
        "nom":       "Dr. Bensouda",
        "specialite": "Médecine générale — Pédiatrie & gériatrie",
        "patients":  [],
    },
}

# Historique des patients pris en charge
historique_patients = []


# ─────────────────────────────────────────────────────────────────────────────
# Fonctions utilitaires
# ─────────────────────────────────────────────────────────────────────────────

def attribuer_medecin(age: int) -> str:
    """
    Attribue un médecin selon :
    1. Le médecin avec le moins de patients actifs
    2. En cas d'égalité : Dr. Bensouda pour enfants (<15) et seniors (>65)
    """
    nb_m1 = len(MEDECINS["M1"]["patients"])
    nb_m2 = len(MEDECINS["M2"]["patients"])

    if nb_m1 == nb_m2:
        # Égalité → spécialité
        if age < 15 or age > 65:
            return "M2"  # Bensouda : pédiatrie/gériatrie
        return "M1"

    return "M1" if nb_m1 < nb_m2 else "M2"


def emettre_mise_a_jour_file():
    """Envoie l'état de la file à tous les clients connectés."""
    etat = construire_etat_global()
    socketio.emit('file_mise_a_jour', etat)


def construire_etat_global() -> dict:
    """Construit l'état complet pour diffusion WebSocket."""
    file_triee = gestionnaire_file.get_file_triee()

    return {
        "horodatage":   datetime.now().strftime("%H:%M:%S"),
        "nb_patients":  len(file_triee),
        "file": [
            {
                **p.to_dict(),
                "position":    i + 1,
                "medecin_id":  patients_session.get(p.patient_id, {}).get("medecin_id", ""),
                "nom":         patients_session.get(p.patient_id, {}).get("nom", "Patient"),
                "prenom":      patients_session.get(p.patient_id, {}).get("prenom", ""),
                "symptom_text": patients_session.get(p.patient_id, {}).get("symptom_text", ""),
            }
            for i, p in enumerate(file_triee)
        ],
        "medecins": {
            mid: {
                **info,
                "nb_patients": len(info["patients"]),
            }
            for mid, info in MEDECINS.items()
        },
        "alertes": [
            {
                **p.to_dict(),
                "nom":    patients_session.get(p.patient_id, {}).get("nom", "Patient"),
                "prenom": patients_session.get(p.patient_id, {}).get("prenom", ""),
            }
            for p in gestionnaire_file.get_alertes_actives()
        ],
    }


def construire_rapport_patient(patient_id: str) -> dict:
    """Génère le rapport médical d'un patient."""
    session     = patients_session.get(patient_id, {})
    en_file     = gestionnaire_file.file.get(patient_id)
    constantes  = session.get("constantes", {})
    features_nlp = extraire_features_nlp(session.get("symptom_text", ""))

    rapport = {
        "patient_id":      patient_id,
        "nom":             session.get("nom", "Inconnu"),
        "prenom":          session.get("prenom", "Inconnu"),
        "age":             session.get("age", "?"),
        "sexe":            "Homme" if session.get("sex", -1) == 1 else "Femme",
        "heure_arrivee":   session.get("heure_arrivee", "?"),
        "symptom_text":    session.get("symptom_text", ""),
        "constantes":      constantes,
        "esi_predit":      session.get("esi_predit", "?"),
        "niveau_urgence":  session.get("niveau_urgence", "?"),
        "confiance_modele": session.get("confiance", "?"),
        "features_nlp_actives": {
            k: v for k, v in features_nlp.items() if v > 0
        },
        "score_priorite":  round(en_file.score, 1) if en_file else "?",
        "temps_attente_min": round(en_file.temps_attente_minutes(), 1) if en_file else "?",
        "medecin_assigne": MEDECINS.get(session.get("medecin_id", ""), {}).get("nom", "?"),
        "horodatage_rapport": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }

    return rapport


# ─────────────────────────────────────────────────────────────────────────────
# Routes pages HTML
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('borne.html')

@app.route('/salle')
def salle_attente():
    return render_template('salle_attente.html')

@app.route('/medecin/<medecin_id>')
def interface_medecin(medecin_id):
    if medecin_id not in MEDECINS:
        return "Médecin non trouvé", 404
    medecin = MEDECINS[medecin_id]
    return render_template('medecin.html', medecin=medecin)

@app.route('/admin')
def admin():
    return render_template('admin.html')


# ─────────────────────────────────────────────────────────────────────────────
# API — Étape 1 : Scanner la pièce d'identité
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/scanner', methods=['POST'])
def api_scanner():
    """
    Scanne la pièce d'identité.
    Accepte : image base64 ou déclenche la caméra si aucune image.
    """
    donnees = request.get_json() or {}
    image_b64 = donnees.get('image_base64')

    if image_b64:
        import base64
        resultat = scanner_piece_identite(
            source=base64.b64decode(image_b64.encode())
        )
    else:
        # Déclencher la caméra (Raspberry Pi)
        resultat = scanner_piece_identite(source=0)

    # Créer une session pour ce patient
    session_id = str(uuid.uuid4())[:8].upper()
    patients_session[session_id] = {
        "session_id":   session_id,
        "nom":          resultat.get("nom", "Inconnu"),
        "prenom":       resultat.get("prenom", "Inconnu"),
        "age":          resultat.get("age", 30),
        "sex":          resultat.get("sexe", -1),
        "heure_arrivee": datetime.now().strftime("%H:%M"),
        "etape":        "scan_ok",
    }

    return jsonify({
        "statut":     "succès",
        "session_id": session_id,
        **resultat,
    })


# ─────────────────────────────────────────────────────────────────────────────
# API — Étape 2 : Enregistrer les symptômes
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/symptomes', methods=['POST'])
def api_symptomes():
    """Enregistre la phrase de symptômes du patient."""
    donnees = request.get_json()
    if not donnees:
        return jsonify({"statut": "erreur", "message": "Corps JSON manquant"}), 400

    session_id   = donnees.get("session_id")
    symptom_text = donnees.get("symptom_text", "").strip()

    if not session_id or session_id not in patients_session:
        return jsonify({"statut": "erreur", "message": "Session invalide"}), 400

    if not symptom_text:
        return jsonify({"statut": "erreur", "message": "Veuillez décrire vos symptômes"}), 400

    patients_session[session_id]["symptom_text"] = symptom_text
    patients_session[session_id]["etape"] = "symptomes_ok"

    # Pré-analyse NLP pour feedback immédiat
    features_nlp = extraire_features_nlp(symptom_text)
    urgence_detectee = features_nlp.get("nlp_urgence_critique", 0) == 1

    return jsonify({
        "statut":            "succès",
        "session_id":        session_id,
        "urgence_detectee":  urgence_detectee,
        "message":           "Symptômes enregistrés. Mesure des constantes en cours...",
    })


# ─────────────────────────────────────────────────────────────────────────────
# API — Étape 3 : Lire les constantes vitales
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/constantes', methods=['GET'])
def api_constantes():
    """
    Déclenche la lecture des capteurs et retourne les constantes vitales.
    Appelé automatiquement après la saisie des symptômes.
    """
    constantes = lire_toutes_constantes()
    return jsonify({
        "statut":    "succès",
        "constantes": constantes,
    })


# ─────────────────────────────────────────────────────────────────────────────
# API — Étape 4 : Triage complet
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/triage', methods=['POST'])
def api_triage():
    """
    Lance le triage complet :
    1. Récupère les données de session
    2. Lit les constantes vitales (capteurs)
    3. Prédit le niveau ESI
    4. Ajoute le patient dans la file APQ-h
    5. Attribue un médecin
    6. Émet la mise à jour WebSocket
    """
    donnees = request.get_json()
    if not donnees:
        return jsonify({"statut": "erreur", "message": "Corps JSON manquant"}), 400

    session_id = donnees.get("session_id")
    if not session_id or session_id not in patients_session:
        return jsonify({"statut": "erreur", "message": "Session invalide"}), 400

    session = patients_session[session_id]

    # Récupérer les constantes (envoyées par le Pi ou relire les capteurs)
    constantes_brutes = donnees.get("constantes") or lire_toutes_constantes()

    # Construire le vecteur de données pour le modèle
    donnees_modele = {
        "age":              session.get("age", 30),
        "sex":              session.get("sex", 0),
        "temperature":      constantes_brutes.get("temperature", 37.0),
        "heart_rate":       constantes_brutes.get("heart_rate", 75),
        "bp_systolic":      constantes_brutes.get("bp_systolic", 120),
        "bp_diastolic":     constantes_brutes.get("bp_diastolic", 80),
        "spo2":             constantes_brutes.get("spo2", 98.0),
        "respiratory_rate": constantes_brutes.get("respiratory_rate", 16),
        "glucose":          constantes_brutes.get("glucose", 90),
        "pain_score":       0,
        "chest_pain":       0, "dyspnea": 0,
        "loss_of_consciousness": 0, "severe_bleeding": 0,
        "neurological_symptoms": 0, "abdominal_pain": 0,
        "fever": 0, "trauma": 0,
        "symptom_text":     session.get("symptom_text", ""),
    }

    # Prédiction ESI
    try:
        resultat = predire_esi(donnees_modele)
    except Exception as e:
        return jsonify({"statut": "erreur", "message": f"Erreur modèle : {str(e)}"}), 500

    esi_predit = resultat["esi_predit"]

    # Attribution médecin (moins chargé)
    medecin_id = attribuer_medecin(session.get("age", 30))

    # ID patient unique
    patient_id = f"PT-{session_id}"

    # Sauvegarder dans la session
    session.update({
        "patient_id":    patient_id,
        "constantes":    constantes_brutes,
        "esi_predit":    esi_predit,
        "niveau_urgence": _libelle_urgence(esi_predit),
        "confiance":     resultat["confiance"],
        "medecin_id":    medecin_id,
        "etape":         "triage_ok",
    })

    # Ajouter dans la file APQ-h
    gestionnaire_file.ajouter_patient(
        patient_id=patient_id,
        esi_predit=esi_predit,
        age=session.get("age", 30),
        constantes={
            "temperature": constantes_brutes.get("temperature"),
            "spo2":        constantes_brutes.get("spo2"),
            "heart_rate":  constantes_brutes.get("heart_rate"),
        },
    )

    # Ajouter le patient dans la liste du médecin
    MEDECINS[medecin_id]["patients"].append(patient_id)

    # Position dans la file
    position = gestionnaire_file.get_position_patient(patient_id)

    # Délais estimés par ESI
    attentes = {1: "< 1 min", 2: "< 15 min", 3: "~30 min", 4: "~1h", 5: "~2h"}

    # Rapport pour le médecin
    rapport = construire_rapport_patient(patient_id)

    # Alerte si ESI critique
    if esi_predit <= 2:
        socketio.emit('alerte_critique', {
            "patient_id": patient_id,
            "nom":        session.get("nom"),
            "prenom":     session.get("prenom"),
            "esi":        esi_predit,
            "medecin_id": medecin_id,
            "rapport":    rapport,
        }, room=f"medecin_{medecin_id}")

    # Diffuser la mise à jour à tous
    emettre_mise_a_jour_file()

    return jsonify({
        "statut":         "succès",
        "patient_id":     patient_id,
        "esi_predit":     esi_predit,
        "niveau_urgence": _libelle_urgence(esi_predit),
        "confiance":      resultat["confiance"],
        "position_file":  position,
        "attente_estimee": attentes.get(esi_predit, "?"),
        "medecin_assigne": MEDECINS[medecin_id]["nom"],
        "rapport":        rapport,
    })


# ─────────────────────────────────────────────────────────────────────────────
# API — File d'attente
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/file', methods=['GET'])
def api_file():
    """Retourne l'état complet de la file."""
    return jsonify({"statut": "succès", **construire_etat_global()})


@app.route('/api/rapport/<patient_id>', methods=['GET'])
def api_rapport(patient_id):
    """Retourne le rapport médical d'un patient."""
    if patient_id not in patients_session:
        return jsonify({"statut": "erreur", "message": "Patient non trouvé"}), 404
    return jsonify({"statut": "succès", "rapport": construire_rapport_patient(patient_id)})


# ─────────────────────────────────────────────────────────────────────────────
# API — Actions médecin
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/prise_en_charge', methods=['POST'])
def api_prise_en_charge():
    """
    Le médecin marque un patient comme pris en charge.
    Le patient est retiré de la file et de la liste du médecin.
    """
    donnees    = request.get_json()
    patient_id = donnees.get("patient_id")
    medecin_id = donnees.get("medecin_id")

    if not patient_id or not medecin_id:
        return jsonify({"statut": "erreur", "message": "patient_id et medecin_id requis"}), 400

    if medecin_id not in MEDECINS:
        return jsonify({"statut": "erreur", "message": "Médecin non trouvé"}), 404

    # Retirer de la file
    patient = gestionnaire_file.retirer_patient(patient_id)

    # Retirer de la liste du médecin
    if patient_id in MEDECINS[medecin_id]["patients"]:
        MEDECINS[medecin_id]["patients"].remove(patient_id)

    # Archiver dans l'historique
    session = patients_session.get(patient_id, {})
    historique_patients.append({
        **session,
        "pris_en_charge_par": MEDECINS[medecin_id]["nom"],
        "heure_prise_en_charge": datetime.now().strftime("%H:%M"),
        "temps_attente_reel": round(patient.temps_attente_minutes(), 1) if patient else "?",
    })

    # Diffuser la mise à jour
    emettre_mise_a_jour_file()

    return jsonify({
        "statut":  "succès",
        "message": f"Patient {patient_id} pris en charge par {MEDECINS[medecin_id]['nom']}",
    })


@app.route('/api/medecin/<medecin_id>', methods=['GET'])
def api_patients_medecin(medecin_id):
    """Retourne les patients assignés à un médecin avec leurs rapports."""
    if medecin_id not in MEDECINS:
        return jsonify({"statut": "erreur", "message": "Médecin non trouvé"}), 404

    patients_ids = MEDECINS[medecin_id]["patients"]
    rapports = []

    for pid in patients_ids:
        if pid in patients_session:
            rapport = construire_rapport_patient(pid)
            en_file = gestionnaire_file.file.get(pid)
            rapport["position_file"] = gestionnaire_file.get_position_patient(pid)
            rapport["temps_attente_actuel"] = round(
                en_file.temps_attente_minutes(), 1
            ) if en_file else "?"
            rapports.append(rapport)

    # Trier par priorité ESI
    rapports.sort(key=lambda r: r.get("esi_predit", 5))

    return jsonify({
        "statut":    "succès",
        "medecin":   MEDECINS[medecin_id],
        "nb_patients": len(rapports),
        "patients":  rapports,
    })


@app.route('/api/degradation', methods=['POST'])
def api_degradation():
    """Signale une dégradation clinique d'un patient."""
    donnees    = request.get_json()
    patient_id = donnees.get("patient_id")
    nouvel_esi = donnees.get("nouvel_esi")

    succes = gestionnaire_file.signaler_degradation(
        patient_id, {}, int(nouvel_esi)
    )

    if succes:
        emettre_mise_a_jour_file()
        return jsonify({"statut": "succès", "message": "Dégradation enregistrée"})

    return jsonify({"statut": "erreur", "message": "Patient non trouvé"}), 404


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket — connexion des clients
# ─────────────────────────────────────────────────────────────────────────────

@socketio.on('connect')
def on_connect():
    """Envoie l'état actuel à un client qui se connecte."""
    emit('file_mise_a_jour', construire_etat_global())


@socketio.on('rejoindre_medecin')
def on_rejoindre_medecin(data):
    """Un médecin rejoint sa salle dédiée pour les alertes."""
    from flask_socketio import join_room
    medecin_id = data.get('medecin_id')
    if medecin_id in MEDECINS:
        join_room(f"medecin_{medecin_id}")
        emit('file_mise_a_jour', construire_etat_global())


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _libelle_urgence(esi: int) -> str:
    libelles = {
        1: "CRITIQUE — Immédiat",
        2: "TRÈS URGENT — 15 min",
        3: "URGENT — 30 min",
        4: "SEMI-URGENT — 1h",
        5: "NON URGENT",
    }
    return libelles.get(esi, "?")


# ─────────────────────────────────────────────────────────────────────────────
# Lancement
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 60)
    print("HEALTHGATE — Serveur principal")
    print("=" * 60)
    print("  Borne patient     : http://localhost:5000/")
    print("  Salle d'attente   : http://localhost:5000/salle")
    print("  Médecin 1         : http://localhost:5000/medecin/M1")
    print("  Médecin 2         : http://localhost:5000/medecin/M2")
    print("  Admin             : http://localhost:5000/admin")
    print("=" * 60)
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
