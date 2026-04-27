from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from triage_engine import TriageEngine
from database import SessionLocal, Patient
from datetime import datetime

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")
engine = TriageEngine()

@app.route('/api/health')
def health():
    return jsonify({"status": "ok", "timestamp": str(datetime.now())})

@app.route('/api/triage', methods=['POST'])
def triage():
    data = request.get_json()
    resultat = engine.evaluer(data)
    db = SessionLocal()
    patient = Patient(
        nom=data.get('nom', 'Anonyme'),
        prenom=data.get('prenom', ''),
        temperature=data.get('temperature'),
        spo2=data.get('spo2'),
        niveau_triage=resultat['niveau'],
        motif_triage=resultat['motif'],
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    resultat['patient_id'] = patient.id
    db.close()
    socketio.emit('nouveau_patient', resultat)
    return jsonify(resultat)

@app.route('/api/file-attente')
def file_attente():
    db = SessionLocal()
    patients = db.query(Patient)\
        .filter(Patient.statut == 'EN_ATTENTE')\
        .order_by(Patient.niveau_triage, Patient.heure_arrivee)\
        .all()
    
    # Appliquer la dégradation temporelle
    now = datetime.now()
    result = []
    for p in patients:
        minutes = (now - p.heure_arrivee).seconds // 60
        niveau_actuel = engine.degradation_temporelle(p.niveau_triage, minutes)
        if niveau_actuel != p.niveau_triage:
            p.niveau_triage = niveau_actuel
            db.commit()
            socketio.emit('degradation', {'patient_id': p.id, 'nouveau_niveau': niveau_actuel})
        result.append({
            "id": p.id, "nom": p.nom, "prenom": p.prenom,
            "niveau": niveau_actuel, "motif": p.motif_triage,
            "temperature": p.temperature, "minutes_attente": minutes
        })
    db.close()
    return jsonify(result)

@app.route('/api/patient/<int:pid>/pris_en_charge', methods=['PUT'])
def prise_en_charge(pid):
    db = SessionLocal()
    patient = db.query(Patient).filter(Patient.id == pid).first()
    patient.statut = 'PRIS_EN_CHARGE'
    db.commit()
    socketio.emit('patient_pris', {'patient_id': pid})
    db.close()
    return jsonify({"message": "Patient pris en charge"})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)