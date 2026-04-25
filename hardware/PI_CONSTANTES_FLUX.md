# 📊 Flux des Constantes Biomédicales - Raspberry Pi

## 🎯 Architecture

```
┌─────────────────────────┐
│   Raspberry Pi 5        │
│   - DS18B20 (Temp)      │
│   - MAX30102 (SpO2/HR)  │
│   - Tensiomètre (TA)    │
└────────────┬────────────┘
             │
             │ POST JSON
             ↓
┌─────────────────────────────────────────┐
│   Serveur HealthGate (predict_api.py)   │
│   POST /api/constantes_from_pi          │
└─────────────────────────────────────────┘
             │
             ↓ WebSocket
┌─────────────────────────────────────────┐
│   3 Interfaces (temps réel)             │
│   - Borne patient (kiosk)               │
│   - Salle d'attente (TV)                │
│   - Tableau médecin (dashboard)         │
└─────────────────────────────────────────┘
```

## 📡 Workflow Détaillé

### Étape 1 : Patient enregistrement (Borne)
1. Patient scanne sa pièce d'identité → `patient_id` généré
2. Patient rentre ses symptômes (texte libre)
3. Attendre mesure des capteurs...

### Étape 2 : Lecture Capteurs (Pi)
```python
# Sur le Raspberry Pi (capteurs_raspberry.py)
constantes = lire_toutes_constantes()
# Retourne:
{
    "temperature":   37.2,      # °C (DS18B20)
    "spo2":          97.5,      # % (MAX30102)
    "heart_rate":    78,        # bpm (MAX30102)
    "bp_systolic":   120,       # mmHg (Tensiomètre)
    "bp_diastolic":  80,        # mmHg (Tensiomètre)
    "respiratory_rate": 16,     # respirations/min
    "glucose":       95,        # mg/dL
}
```

### Étape 3 : Envoi au Serveur (Deux options)

#### Option A : Pi envoie directement au serveur
```bash
curl -X POST http://SERVER_IP:5000/api/constantes_from_pi \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "PT-ABC123",
    "temperature": 37.2,
    "spo2": 97.5,
    "heart_rate": 78,
    "bp_systolic": 120,
    "bp_diastolic": 80,
    "respiratory_rate": 16,
    "glucose": 95
  }'
```

#### Option B : Borne poll les constantes (GET /api/constantes)
```javascript
// Dans borne.html après symptômes enregistrés:
fetch('/api/constantes')
  .then(r => r.json())
  .then(data => {
    // Les constantes sont lues par lire_toutes_constantes()
    // Si Pi connecté → vraies valeurs
    // Si Pi absent → valeurs simulées
    afficherConstantes(data.constantes);
  });
```

### Étape 4 : Synchronisation WebSocket

Après réception des constantes, le serveur émet:

```javascript
// Sur le serveur (emit)
socketio.emit('constantes_recu', {
  "patient_id": "PT-ABC123",
  "constantes": { ...values... },
  "horodatage": "14:32:15",
});

// Ensuite les questions adaptatives s'affichent sur la borne
```

## 🔧 Code Python pour Envoi du Pi

**Créer `/home/pi/healthgate_sender.py`:**

```python
#!/usr/bin/env python3
import requests
import json
import time
from capteurs_raspberry import lire_toutes_constantes

# Configuration
SERVER_URL = "http://192.168.1.100:5000"  # IP de ton serveur
PATIENT_ID = "PT-ABC123"  # Sera défini dynamiquement

def envoyer_constantes(patient_id):
    """Lire les capteurs et envoyer au serveur."""
    try:
        # Lire tous les capteurs
        constantes = lire_toutes_constantes()
        
        # Préparer la requête
        data = {
            "patient_id": patient_id,
            **constantes  # Dépack température, spo2, etc.
        }
        
        # Envoyer
        response = requests.post(
            f"{SERVER_URL}/api/constantes_from_pi",
            json=data,
            timeout=5
        )
        
        if response.status_code == 200:
            print(f"✓ Constantes envoyées pour {patient_id}")
            print(f"  - Temp: {constantes.get('temperature')}°C")
            print(f"  - SpO2: {constantes.get('spo2')}%")
            print(f"  - HR: {constantes.get('heart_rate')} bpm")
        else:
            print(f"✗ Erreur serveur: {response.status_code}")
            
    except Exception as e:
        print(f"✗ Erreur d'envoi: {e}")

if __name__ == "__main__":
    # Exemple: envoyer constantes toutes les 10 secondes
    patient_id = "PT-DEMO123"
    
    while True:
        envoyer_constantes(patient_id)
        time.sleep(10)  # Attendre 10 secondes
```

**Lancer:**
```bash
sudo python3 /home/pi/healthgate_sender.py
```

## 📋 Endpoints API

### 1. Envoyer constantes du Pi
```
POST /api/constantes_from_pi
Content-Type: application/json

Body:
{
  "patient_id": "PT-ABC123",
  "temperature": 37.2,
  "spo2": 97.5,
  "heart_rate": 78,
  "bp_systolic": 120,
  "bp_diastolic": 80,
  "respiratory_rate": 16,
  "glucose": 95
}

Response (200 OK):
{
  "statut": "succès",
  "message": "Constantes reçues"
}
```

### 2. Générer questions adaptatives
```
POST /api/questions
Content-Type: application/json

Body:
{
  "patient_id": "PT-ABC123"
}

Response:
{
  "statut": "succès",
  "questions_proposees": [
    {
      "id": "q_duree_dyspnee",
      "texte": "Depuis combien de temps avez-vous du mal à respirer ?",
      "type": "choix",
      "feature_name": "q_duree_dyspnee"
    },
    ...
  ],
  "nb_questions": 4
}
```

### 3. Lancer triage final avec réponses
```
POST /api/triage
Content-Type: application/json

Body:
{
  "session_id": "SES-123",
  "constantes": {
    "temperature": 37.4,
    "spo2": 95.0,
    "heart_rate": 98,
    "bp_systolic": 125,
    "bp_diastolic": 82,
    "respiratory_rate": 18,
    "glucose": 96
  },
  "question_reponses": {
    "q_duree_dyspnee": "Depuis quelques heures",
    "q_dyspnee_aggrave_effort": "Oui"
  }
}

Response:
{
  "statut": "succès",
  "patient_id": "PT-SES-123",
  "esi_predit": 2,
  "diagnostic_probable": "Détresse respiratoire",
  "position_file": 1
}
```

## 🔔 WebSocket Events

### Client → Serveur
```javascript
// Quand borne patient se connecte
socket.emit('rejoindre_borne', { patient_id: 'PT-ABC123' });

// Quand salle d'attente se connecte  
socket.emit('rejoindre_salle');

// Quand médecin se connecte
socket.emit('rejoindre_medecin', { medecin_id: 'MED-001' });
```

### Serveur → Clients (Broadcasts)
```javascript
// Quand constantes reçues
socket.on('constantes_recu', (data) => {
  // data.patient_id, data.constantes, data.horodatage
  afficherConstantes(data);
});

// Quand la file change (nouveau patient, changement position)
socket.on('file_mise_a_jour', (data) => {
  // data.file_triee, data.total_patients, data.attente_moyenne
  mettreAJourAffichage(data);
});

// Alerte critique ESI 1/2
socket.on('alerte_critique', (data) => {
  // data.patient_id, data.nom, data.prenom, data.esi, data.rapport
  afficherAlerte(data);
});

// Confirmation de synchronisation
socket.on('file_synchronisee', (data) => {
  // data.horodatage, data.nb_patients
  console.log('Synchro OK:', data);
});
```

## 🧪 Test Complet

### 1. Démarrer le serveur
```bash
cd /path/to/PLBD-4/ml
python predict_api.py
```

### 2. Ouvrir les 3 interfaces
- **Borne patient:** http://localhost:5000/
- **Salle d'attente:** http://localhost:5000/salle
- **Médecin 1:** http://localhost:5000/medecin/M1
- **Médecin 2:** http://localhost:5000/medecin/M2

### 3. Workflow test (sans Pi)
```bash
# Terminal 1: Démarrer serveur
python predict_api.py

# Terminal 2: Tester scan ID
curl -X POST http://localhost:5000/api/scanner \
  -H "Content-Type: application/json" \
  -d '{"source": "simulation"}'

# Terminal 3: Enregistrer symptômes
curl -X POST http://localhost:5000/api/symptomes \
  -H "Content-Type: application/json" \
  -d '{"session_id": "SES-123", "symptom_text": "fièvre depuis 2 jours, toux"}'

# Terminal 4: Lire constantes
curl http://localhost:5000/api/constantes

# Terminal 5: Générer questions
curl -X POST http://localhost:5000/api/questions \
  -H "Content-Type: application/json" \
  -d '{"patient_id": "PT-SES-123"}'

# Terminal 6: Triage final avec réponses
curl -X POST http://localhost:5000/api/triage \
  -H "Content-Type: application/json" \
  -d '{"session_id": "SES-123", "question_reponses": {"q_duree_dyspnee": "Depuis quelques heures"}}'
```

## ✅ Checklist Déploiement Pi

- [ ] Pi connecté au réseau (IPv4: 192.168.1.X)
- [ ] Capteurs branchés:
  - [ ] DS18B20 sur GPIO 4
  - [ ] MAX30102 sur I2C (SDA=2, SCL=3)
  - [ ] Tensiomètre sur /dev/ttyUSB0
- [ ] Script `healthgate_sender.py` créé et testé
- [ ] Cron job pour lancer sender au boot:
  ```bash
  @reboot /usr/bin/python3 /home/pi/healthgate_sender.py >> /var/log/healthgate.log 2>&1
  ```
- [ ] Firewall ouvert port 5000 du serveur
- [ ] Test ping serveur depuis Pi: `ping 192.168.1.100`
- [ ] Test curl vers serveur: `curl http://192.168.1.100:5000/api/constantes`

## 📚 Références

- **capteurs_raspberry.py:** Fonctions de lecture capteurs
- **predict_api.py:** Endpoints et WebSocket
- **questions_moteur.py:** Génération questions ciblées

---

**Dernière mise à jour:** 2025-12-19  
**Version:** 1.0 - Flux Pi intégré
