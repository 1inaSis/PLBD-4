"""
predict_api.py - API Flask + Socket.IO du projet HealthGate
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO, emit, join_room

from capteurs_raspberry import lire_toutes_constantes
from model_trainer import predire_esi
from nlp_extractor import extraire_features_nlp
from questions_moteur import encoder_reponses, generer_questions
from queue_manager import gestionnaire_file
from scanner_cin import scanner_piece_identite

BASE_DIR = Path(__file__).resolve().parent
START_TIME = datetime.now()

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))
app.config["SECRET_KEY"] = "healthgate-secret-2026"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Etat memoire (prototype)
patients_session: Dict[str, Dict[str, Any]] = {}

MEDECINS = {
    "M1": {
        "id": "M1",
        "nom": "Dr. El Amrani",
        "specialite": "Urgences adultes",
        "patients": [],
    },
    "M2": {
        "id": "M2",
        "nom": "Dr. Bensouda",
        "specialite": "Pediatrie / geriatrie",
        "patients": [],
    },
}


def _libelle_urgence(esi: int) -> str:
    labels = {
        1: "CRITIQUE - immediat",
        2: "TRES URGENT - < 15 min",
        3: "URGENT - ~30 min",
        4: "SEMI URGENT - ~1h",
        5: "NON URGENT",
    }
    return labels.get(esi, "INCONNU")


def _to_sex(raw_value: Any) -> int:
    if isinstance(raw_value, (int, float)):
        return int(raw_value)

    value = str(raw_value or "").strip().lower()
    if value in {"m", "male", "masculin", "homme"}:
        return 1
    if value in {"f", "female", "feminin", "femme"}:
        return 0
    return 0


def attribuer_medecin(age: int) -> str:
    m1_count = len(MEDECINS["M1"]["patients"])
    m2_count = len(MEDECINS["M2"]["patients"])

    if m1_count == m2_count:
        if age < 15 or age > 65:
            return "M2"
        return "M1"

    return "M1" if m1_count < m2_count else "M2"


def construire_etat_global() -> dict:
    file_triee = gestionnaire_file.get_file_triee()
    alertes = gestionnaire_file.get_alertes_actives()

    return {
        "horodatage": datetime.now().strftime("%H:%M:%S"),
        "nb_patients": len(file_triee),
        "file": [
            {
                **patient.to_dict(),
                "position": i + 1,
                "nom": patients_session.get(patient.patient_id, {}).get("nom", "Patient"),
                "prenom": patients_session.get(patient.patient_id, {}).get("prenom", ""),
                "medecin_id": patients_session.get(patient.patient_id, {}).get("medecin_id", ""),
            }
            for i, patient in enumerate(file_triee)
        ],
        "medecins": {
            mid: {
                "id": info["id"],
                "nom": info["nom"],
                "specialite": info["specialite"],
                "nb_patients": len(info["patients"]),
            }
            for mid, info in MEDECINS.items()
        },
        "alertes": [
            {
                **p.to_dict(),
                "nom": patients_session.get(p.patient_id, {}).get("nom", "Patient"),
                "prenom": patients_session.get(p.patient_id, {}).get("prenom", ""),
            }
            for p in alertes
        ],
    }


def emettre_mise_a_jour_file() -> None:
    etat = construire_etat_global()
    socketio.emit("file_mise_a_jour", etat)


def _build_modele_input(session_data: dict, constantes: dict, features_questions: dict) -> dict:
    return {
        "age": session_data.get("age", 30),
        "sex": session_data.get("sex", 0),
        "temperature": constantes.get("temperature", 37.0),
        "heart_rate": constantes.get("heart_rate", 75),
        "bp_systolic": constantes.get("bp_systolic", 120),
        "bp_diastolic": constantes.get("bp_diastolic", 80),
        "spo2": constantes.get("spo2", 98.0),
        "respiratory_rate": constantes.get("respiratory_rate", 16),
        "glucose": constantes.get("glucose", 90),
        "pain_score": session_data.get("pain_score", 0),
        "chest_pain": 0,
        "dyspnea": 0,
        "loss_of_consciousness": 0,
        "severe_bleeding": 0,
        "neurological_symptoms": 0,
        "abdominal_pain": 0,
        "fever": 0,
        "trauma": 0,
        "symptom_text": session_data.get("symptom_text", ""),
        "questions": session_data.get("questions", []),
        "question_reponses": session_data.get("question_reponses", {}),
        **features_questions,
    }


def construire_rapport_patient(patient_id: str) -> dict:
    session_data = patients_session.get(patient_id, {})
    entry = gestionnaire_file.file.get(patient_id)
    nlp = extraire_features_nlp(session_data.get("symptom_text", ""))

    return {
        "patient_id": patient_id,
        "nom": session_data.get("nom", "Inconnu"),
        "prenom": session_data.get("prenom", "Inconnu"),
        "age": session_data.get("age", "?"),
        "sexe": "Homme" if session_data.get("sex", 0) == 1 else "Femme",
        "symptom_text": session_data.get("symptom_text", ""),
        "constantes": session_data.get("constantes", {}),
        "esi_predit": session_data.get("esi_predit", "?"),
        "niveau_urgence": session_data.get("niveau_urgence", "?"),
        "confiance_modele": session_data.get("confiance", 0),
        "diagnostic_probable": session_data.get("diagnostic_probable", "Evaluation clinique complementaire"),
        "score_priorite": round(entry.score, 2) if entry else "?",
        "temps_attente_min": round(entry.temps_attente_minutes(), 1) if entry else "?",
        "features_nlp_actives": {k: v for k, v in nlp.items() if v > 0},
        "medecin_assigne": MEDECINS.get(session_data.get("medecin_id", ""), {}).get("nom", "?"),
        "horodatage_rapport": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }


@app.route("/")
def index():
    return render_template("borne.html")


@app.route("/salle")
def salle_attente():
    return render_template("salle_attente.html")


@app.route("/medecin/<medecin_id>")
def interface_medecin(medecin_id: str):
    if medecin_id not in MEDECINS:
        return "Medecin non trouve", 404
    return render_template("medecin.html", medecin=MEDECINS[medecin_id])


@app.route("/admin")
def admin():
    return jsonify({"statut": "succes", "message": "Interface admin non implementee"})


@app.route("/api/sante", methods=["GET"])
def api_sante():
    uptime_seconds = int((datetime.now() - START_TIME).total_seconds())
    return jsonify(
        {
            "statut": "ok",
            "service": "healthgate-api",
            "uptime_seconds": uptime_seconds,
            "modele_charge": True,
            "queue_patients": len(gestionnaire_file.file),
        }
    )


@app.route("/api/scanner", methods=["POST"])
def api_scanner():
    payload = request.get_json(silent=True) or {}
    image_b64 = payload.get("image_base64")

    if image_b64:
        try:
            source = base64.b64decode(image_b64)
        except Exception:
            return jsonify({"statut": "erreur", "message": "image_base64 invalide"}), 400
    else:
        source = 0

    scan = scanner_piece_identite(source=source)
    session_id = str(uuid.uuid4())[:8].upper()

    patients_session[session_id] = {
        "session_id": session_id,
        "nom": scan.get("nom", "Inconnu"),
        "prenom": scan.get("prenom", "Inconnu"),
        "age": int(scan.get("age", 30) or 30),
        "sex": _to_sex(scan.get("sexe", 0)),
        "heure_arrivee": datetime.now().strftime("%H:%M"),
        "etape": "scan_ok",
    }

    return jsonify({"statut": "succes", "session_id": session_id, **scan})


@app.route("/api/symptomes", methods=["POST"])
def api_symptomes():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    symptom_text = str(payload.get("symptom_text", "")).strip()

    if not session_id:
        return jsonify({"statut": "erreur", "message": "Session invalide"}), 400

    # Compatibilite borne: autorise la creation d'une session manuelle si l'utilisateur
    # poursuit sans scan carte.
    if session_id not in patients_session and str(session_id).startswith("MANUEL-"):
        patients_session[session_id] = {
            "session_id": session_id,
            "nom": "Inconnu",
            "prenom": "Inconnu",
            "age": 30,
            "sex": 0,
            "heure_arrivee": datetime.now().strftime("%H:%M"),
            "etape": "scan_ok",
        }

    if session_id not in patients_session:
        return jsonify({"statut": "erreur", "message": "Session invalide"}), 400

    if not symptom_text:
        return jsonify({"statut": "erreur", "message": "symptom_text requis"}), 400

    patients_session[session_id]["symptom_text"] = symptom_text
    patients_session[session_id]["etape"] = "symptomes_ok"

    urgence = extraire_features_nlp(symptom_text).get("nlp_urgence_critique", 0) == 1
    return jsonify({"statut": "succes", "session_id": session_id, "urgence_detectee": urgence})


@app.route("/api/constantes", methods=["GET"])
def api_constantes():
    constantes = lire_toutes_constantes()
    return jsonify({"statut": "succes", "constantes": constantes})


@app.route("/api/constantes_from_pi", methods=["POST"])
def api_constantes_from_pi():
    payload = request.get_json(silent=True) or {}
    patient_id = payload.get("patient_id")
    if not patient_id or patient_id not in patients_session:
        return jsonify({"statut": "erreur", "message": "Patient non trouve"}), 404

    constantes = {
        "temperature": payload.get("temperature", 37.0),
        "spo2": payload.get("spo2", 98.0),
        "heart_rate": payload.get("heart_rate", 75),
        "bp_systolic": payload.get("bp_systolic", 120),
        "bp_diastolic": payload.get("bp_diastolic", 80),
        "respiratory_rate": payload.get("respiratory_rate", 16),
        "glucose": payload.get("glucose", 90),
    }

    patients_session[patient_id]["constantes"] = constantes
    socketio.emit(
        "constantes_recu",
        {
            "patient_id": patient_id,
            "constantes": constantes,
            "horodatage": datetime.now().strftime("%H:%M:%S"),
        },
        room=f"borne_{patient_id}",
    )

    return jsonify({"statut": "succes", "message": "Constantes recues"})


@app.route("/api/questions", methods=["POST"])
def api_questions():
    payload = request.get_json(silent=True) or {}
    patient_id = payload.get("patient_id") or payload.get("session_id")

    if not patient_id or patient_id not in patients_session:
        return jsonify({"statut": "erreur", "message": "Patient non trouve"}), 404

    session_data = patients_session[patient_id]
    constantes = payload.get("constantes") or session_data.get("constantes", {})
    session_data["constantes"] = constantes

    questions = generer_questions(
        constantes,
        session_data.get("symptom_text", ""),
        int(session_data.get("age", 0) or 0),
        int(session_data.get("sex", 0) or 0),
    )

    session_data["questions"] = questions
    session_data["etape"] = "questions_ok"

    socketio.emit(
        "question_suivante",
        {
            "patient_id": patient_id,
            "questions": questions,
            "question_courante": questions[0] if questions else None,
            "nb_questions": len(questions),
        },
        room=f"borne_{patient_id}",
    )

    return jsonify({"statut": "succes", "patient_id": patient_id, "questions_proposees": questions})


@app.route("/api/questions_adaptatif", methods=["POST"])
def api_questions_adaptatif():
    return api_questions()


@app.route("/api/questions/reponses", methods=["POST"])
def api_questions_reponses():
    payload = request.get_json(silent=True) or {}
    patient_id = payload.get("patient_id") or payload.get("session_id")
    reponses = payload.get("reponses") or payload.get("question_reponses") or {}

    if not patient_id or patient_id not in patients_session:
        return jsonify({"statut": "erreur", "message": "Patient non trouve"}), 404

    session_data = patients_session[patient_id]
    questions = session_data.get("questions", [])
    session_data["question_reponses"] = reponses
    encoded = encoder_reponses(questions, reponses)

    return jsonify(
        {
            "statut": "succes",
            "patient_id": patient_id,
            "question_reponses": reponses,
            "features_questions": encoded,
        }
    )


@app.route("/api/triage", methods=["POST"])
def api_triage():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")

    if not session_id or session_id not in patients_session:
        return jsonify({"statut": "erreur", "message": "Session invalide"}), 400

    session_data = patients_session[session_id]
    constantes = payload.get("constantes") or session_data.get("constantes") or lire_toutes_constantes()
    session_data["constantes"] = constantes

    if not session_data.get("questions"):
        session_data["questions"] = generer_questions(
            constantes,
            session_data.get("symptom_text", ""),
            int(session_data.get("age", 0) or 0),
            int(session_data.get("sex", 0) or 0),
        )

    if payload.get("question_reponses"):
        session_data["question_reponses"] = payload["question_reponses"]

    question_reponses = session_data.get("question_reponses", {})
    features_questions = encoder_reponses(session_data.get("questions", []), question_reponses)

    try:
        resultat = predire_esi(_build_modele_input(session_data, constantes, features_questions))
    except Exception as exc:
        return jsonify({"statut": "erreur", "message": f"Erreur modele: {exc}"}), 500

    esi = int(resultat["esi_predit"])
    medecin_id = attribuer_medecin(int(session_data.get("age", 30) or 30))
    patient_id = f"PT-{session_id}"

    session_data.update(
        {
            "patient_id": patient_id,
            "esi_predit": esi,
            "niveau_urgence": _libelle_urgence(esi),
            "confiance": resultat.get("confiance", 0),
            "diagnostic_probable": resultat.get("diagnostic_probable", "Evaluation clinique complementaire"),
            "diagnostic_encode": resultat.get("diagnostic_encode", 0),
            "medecin_id": medecin_id,
            "etape": "triage_ok",
        }
    )
    patients_session[patient_id] = session_data

    if patient_id not in MEDECINS[medecin_id]["patients"]:
        MEDECINS[medecin_id]["patients"].append(patient_id)

    if patient_id not in gestionnaire_file.file:
        gestionnaire_file.ajouter_patient(
            patient_id=patient_id,
            esi_predit=esi,
            age=int(session_data.get("age", 30) or 30),
            constantes={
                "temperature": constantes.get("temperature"),
                "spo2": constantes.get("spo2"),
                "heart_rate": constantes.get("heart_rate"),
            },
        )

    position = gestionnaire_file.get_position_patient(patient_id)
    attentes = {1: "< 1 min", 2: "< 15 min", 3: "~30 min", 4: "~1h", 5: "~2h"}

    emettre_mise_a_jour_file()

    if esi <= 2:
        payload_alerte = {
            "patient_id": patient_id,
            "nom": session_data.get("nom", "Patient"),
            "prenom": session_data.get("prenom", ""),
            "esi": esi,
            "medecin_id": medecin_id,
            "rapport": construire_rapport_patient(patient_id),
        }
        socketio.emit("alerte_critique", payload_alerte, room="medecins")
        socketio.emit("alerte_critique", payload_alerte, room=f"medecin_{medecin_id}")

    socketio.emit(
        "triage_complete",
        {
            "patient_id": patient_id,
            "esi_predit": esi,
            "niveau_urgence": _libelle_urgence(esi),
            "position_file": position,
            "attente_estimee": attentes.get(esi, "?"),
        },
        room=f"borne_{session_id}",
    )

    return jsonify(
        {
            "statut": "succes",
            "patient_id": patient_id,
            "esi_predit": esi,
            "niveau_urgence": _libelle_urgence(esi),
            "confiance": resultat.get("confiance", 0),
            "diagnostic_probable": resultat.get("diagnostic_probable"),
            "position_file": position,
            "attente_estimee": attentes.get(esi, "?"),
            "medecin_assigne": MEDECINS[medecin_id]["nom"],
            "rapport": construire_rapport_patient(patient_id),
        }
    )


@app.route("/api/file", methods=["GET"])
def api_file():
    return jsonify({"statut": "succes", **construire_etat_global()})


@app.route("/api/queue/<patient_id>", methods=["GET"])
def api_queue_patient(patient_id: str):
    position = gestionnaire_file.get_position_patient(patient_id)
    patient = gestionnaire_file.file.get(patient_id)

    if patient is None:
        return jsonify({"statut": "erreur", "message": "Patient non trouve"}), 404

    return jsonify(
        {
            "statut": "succes",
            "patient_id": patient_id,
            "position": position,
            "esi_actuel": patient.esi_actuel,
            "score_priorite": round(patient.score, 2),
            "temps_attente_min": round(patient.temps_attente_minutes(), 1),
            "alerte_active": patient.alerte_active,
        }
    )


@app.route("/api/rapport/<patient_id>", methods=["GET"])
def api_rapport(patient_id: str):
    if patient_id not in patients_session:
        return jsonify({"statut": "erreur", "message": "Patient non trouve"}), 404
    return jsonify({"statut": "succes", "rapport": construire_rapport_patient(patient_id)})


@app.route("/api/prise_en_charge", methods=["POST"])
def api_prise_en_charge():
    payload = request.get_json(silent=True) or {}
    patient_id = payload.get("patient_id")
    medecin_id = payload.get("medecin_id")

    if not patient_id or not medecin_id:
        return jsonify({"statut": "erreur", "message": "patient_id et medecin_id requis"}), 400
    if medecin_id not in MEDECINS:
        return jsonify({"statut": "erreur", "message": "Medecin non trouve"}), 404

    gestionnaire_file.retirer_patient(patient_id)
    if patient_id in MEDECINS[medecin_id]["patients"]:
        MEDECINS[medecin_id]["patients"].remove(patient_id)

    emettre_mise_a_jour_file()
    return jsonify({"statut": "succes", "message": f"Patient {patient_id} pris en charge"})


@app.route("/api/medecin/<medecin_id>", methods=["GET"])
def api_medecin(medecin_id: str):
    if medecin_id not in MEDECINS:
        return jsonify({"statut": "erreur", "message": "Medecin non trouve"}), 404

    patients = []
    for pid in MEDECINS[medecin_id]["patients"]:
        if pid in patients_session:
            rapport = construire_rapport_patient(pid)
            rapport["position_file"] = gestionnaire_file.get_position_patient(pid)
            patients.append(rapport)

    patients.sort(key=lambda item: int(item.get("esi_predit", 5) or 5))
    return jsonify(
        {
            "statut": "succes",
            "medecin": MEDECINS[medecin_id],
            "nb_patients": len(patients),
            "patients": patients,
        }
    )


@app.route("/api/degradation", methods=["POST"])
def api_degradation():
    payload = request.get_json(silent=True) or {}
    patient_id = payload.get("patient_id")
    nouvel_esi = int(payload.get("nouvel_esi", 0) or 0)
    constantes = payload.get("nouvelles_constantes") or {}

    if not patient_id or not (1 <= nouvel_esi <= 5):
        return jsonify({"statut": "erreur", "message": "patient_id et nouvel_esi valides requis"}), 400

    success = gestionnaire_file.signaler_degradation(patient_id, constantes, nouvel_esi)
    if not success:
        return jsonify({"statut": "erreur", "message": "Patient non trouve"}), 404

    if patient_id in patients_session:
        patients_session[patient_id]["esi_predit"] = nouvel_esi
        patients_session[patient_id]["niveau_urgence"] = _libelle_urgence(nouvel_esi)

    emettre_mise_a_jour_file()
    return jsonify({"statut": "succes", "message": "Degradation enregistree"})


@app.route("/api/alertes", methods=["GET"])
def api_alertes():
    alertes = []
    for patient in gestionnaire_file.get_alertes_actives():
        info = patients_session.get(patient.patient_id, {})
        alertes.append(
            {
                "patient_id": patient.patient_id,
                "esi_actuel": patient.esi_actuel,
                "score_priorite": round(patient.score, 2),
                "temps_attente_min": round(patient.temps_attente_minutes(), 1),
                "nom": info.get("nom", "Patient"),
                "prenom": info.get("prenom", ""),
            }
        )

    return jsonify({"statut": "succes", "nb_alertes": len(alertes), "alertes": alertes})


@app.route("/api/alertes/<patient_id>/lue", methods=["POST"])
def api_alerte_lue(patient_id: str):
    success = gestionnaire_file.marquer_alerte_lue(patient_id)
    if not success:
        return jsonify({"statut": "erreur", "message": "Patient non trouve"}), 404

    emettre_mise_a_jour_file()
    return jsonify({"statut": "succes", "message": "Alerte marquee comme lue"})


@socketio.on("connect")
def ws_connect():
    emit("connection_response", {"data": "Connecte au serveur HealthGate"})
    emit("file_mise_a_jour", construire_etat_global())


@socketio.on("rejoindre_borne")
def ws_rejoindre_borne(data):
    payload = data or {}
    patient_id = payload.get("patient_id")
    if patient_id:
        join_room(f"borne_{patient_id}")
    emit("borne_connectee", {"patient_id": patient_id})


@socketio.on("rejoindre_medecin")
def ws_rejoindre_medecin(data):
    payload = data or {}
    medecin_id = payload.get("medecin_id")
    join_room("medecins")
    if medecin_id and medecin_id in MEDECINS:
        join_room(f"medecin_{medecin_id}")
    emit("file_mise_a_jour", construire_etat_global())


if __name__ == "__main__":
    gestionnaire_file.demarrer_mise_a_jour_auto(intervalle=60)
    print("=" * 60)
    print("HEALTHGATE - Serveur principal")
    print("=" * 60)
    print("Borne patient   : http://localhost:5000/")
    print("Salle attente   : http://localhost:5000/salle")
    print("Medecin M1      : http://localhost:5000/medecin/M1")
    print("Medecin M2      : http://localhost:5000/medecin/M2")
    print("Sante API       : http://localhost:5000/api/sante")
    print("=" * 60)
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
