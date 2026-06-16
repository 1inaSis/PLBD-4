"""
HealthGate — Backend FastAPI
Kiosque de triage patient | PLBD-4 | 2025-2026

Démarrage : uvicorn backend.main:app --reload --port 8000
         ou (depuis backend/) : uvicorn main:app --reload --port 8000

Endpoints REST :
  GET  /api/health               → Santé du serveur
  POST /api/scanner              → Étape 1 : Scanner pièce d'identité
  POST /api/symptomes            → Étape 2 : Enregistrer symptômes + NLP
  GET  /api/constantes           → Étape 3 : Lire capteurs vitaux
  POST /api/mesures              → Étape 3b : Push depuis daemon Raspberry Pi
  POST /api/questions            → Étape 4 : Générer questions adaptatives (Groq/Llama)
  POST /api/triage               → Étape 5 : ESI (Random Forest) + file APQ-h
  GET  /api/file                 → État complet de la file d'attente
  GET  /api/rapport/{patient_id} → Rapport médical d'un patient
  POST /api/prise_en_charge      → Médecin marque patient pris en charge
  GET  /api/medecin/{id}         → Patients assignés à un médecin
  POST /api/degradation          → Signaler dégradation clinique

WebSocket :
  WS /ws?role=borne|salle|medecin[&medecin_id=M1|M2]

Événements serveur → client :
  file_mise_a_jour       → salle, medecin_M1, medecin_M2
  nouveau_patient        → salle, medecin_M1, medecin_M2
  alerte_critique        → medecin_M1 ou medecin_M2 (selon attribution)
  patient_pris_en_charge → salle, borne
  degradation            → salle, medecin_M1, medecin_M2
  constantes_update      → borne

Commandes client → serveur (JSON via WS) :
  {"action": "ping"}     → {"event": "pong", "data": {"ts": "..."}}
  {"action": "get_file"} → {"event": "file_mise_a_jour", "data": {...}}
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

# ── Chemins : backend/ (schemas) et ml/ (modules métier) ────────────────────
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_ML_DIR = os.path.normpath(os.path.join(_BACKEND_DIR, "..", "ml"))
for _p in (_BACKEND_DIR, _ML_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from schemas import (
    ConstantesPushRequest,
    DegradationRequest,
    PriseEnChargeRequest,
    QuestionsRequest,
    ScannerRequest,
    SymptomsRequest,
    TriageRequest,
)

# ── Imports ML ───────────────────────────────────────────────────────────────
from capteurs_raspberry import (
    lire_toutes_constantes,
    demarrer_arduino,
    arreter_arduino,
    mesurer_capteur,
)
from model_trainer import predire_esi
from nlp_extractor import extraire_features_nlp
from queue_manager import gestionnaire_file
from questions_moteur import encoder_reponses, generer_questions
from scanner_cin import scanner_piece_identite


# ═══════════════════════════════════════════════════════════════════════════════
# Gestionnaire WebSocket
# ═══════════════════════════════════════════════════════════════════════════════

class ConnectionManager:
    """
    Maintient les connexions WebSocket organisées par groupe :
      - "borne"       : kiosque patient
      - "salle"       : écran salle d'attente
      - "medecin_M1"  : interface Dr. El Amrani
      - "medecin_M2"  : interface Dr. Bensouda

    Utilisation :
      await manager.connect(ws, "salle")
      await manager.broadcast_to("file_mise_a_jour", data, ["salle", "medecin_M1"])
      manager.disconnect(ws, "salle")
    """

    def __init__(self) -> None:
        self._groups: Dict[str, Set[WebSocket]] = {
            "borne": set(),
            "salle": set(),
            "medecin_M1": set(),
            "medecin_M2": set(),
        }

    def resolve_group(self, role: str, medecin_id: str = "") -> str:
        if role == "medecin" and medecin_id:
            return f"medecin_{medecin_id}"
        return role if role in self._groups else "borne"

    async def connect(self, ws: WebSocket, group: str) -> None:
        await ws.accept()
        if group not in self._groups:
            self._groups[group] = set()
        self._groups[group].add(ws)

    def disconnect(self, ws: WebSocket, group: str) -> None:
        self._groups.get(group, set()).discard(ws)

    async def _send(self, ws: WebSocket, event: str, data: Any) -> bool:
        try:
            await ws.send_text(json.dumps({"event": event, "data": data}))
            return True
        except Exception:
            return False

    async def send_one(self, ws: WebSocket, event: str, data: Any) -> None:
        await self._send(ws, event, data)

    async def broadcast_to(self, event: str, data: Any, groups: List[str]) -> None:
        targets: Set[WebSocket] = set()
        for g in groups:
            targets |= self._groups.get(g, set())

        dead: List[WebSocket] = []
        for ws in targets:
            if not await self._send(ws, event, data):
                dead.append(ws)

        for ws in dead:
            for s in self._groups.values():
                s.discard(ws)

    async def broadcast_all(self, event: str, data: Any) -> None:
        await self.broadcast_to(event, data, list(self._groups.keys()))


manager = ConnectionManager()


# ═══════════════════════════════════════════════════════════════════════════════
# État global en mémoire (prototype — remplacer par DB pour prod)
# ═══════════════════════════════════════════════════════════════════════════════

# État de la caméra (partagé entre api_scanner et api_camera_status)
_camera_active: bool = False

patients_session: Dict[str, dict] = {}

MEDECINS: Dict[str, dict] = {
    "M1": {
        "id": "M1",
        "nom": "Dr. El Amrani",
        "specialite": "Médecine générale — Urgences adultes",
        "patients": [],
    },
    "M2": {
        "id": "M2",
        "nom": "Dr. Bensouda",
        "specialite": "Médecine générale — Pédiatrie & gériatrie",
        "patients": [],
    },
}

historique_patients: List[dict] = []


# ═══════════════════════════════════════════════════════════════════════════════
# Cycle de vie — tâches de fond
# ═══════════════════════════════════════════════════════════════════════════════

async def _periodic_queue_broadcast() -> None:
    """Diffuse l'état de la file toutes les 60 s aux écrans de surveillance."""
    while True:
        await asyncio.sleep(60)
        await manager.broadcast_to(
            "file_mise_a_jour",
            _construire_etat_global(),
            ["salle", "medecin_M1", "medecin_M2"],
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Le queue_manager a son propre thread de mise à jour des scores
    gestionnaire_file.demarrer_mise_a_jour_auto(intervalle=60)
    # Tâche asyncio séparée pour le broadcast WebSocket
    task = asyncio.create_task(_periodic_queue_broadcast())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# Application
# ═══════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="HealthGate API",
    version="2.0.0",
    description="Backend FastAPI — Kiosque de triage patient PLBD-4",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # CRA / preview
        "http://localhost:8080",  # hardware daemon
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fonctions utilitaires
# ═══════════════════════════════════════════════════════════════════════════════

def _libelle_urgence(esi: int) -> str:
    return {
        1: "CRITIQUE — Immédiat",
        2: "TRÈS URGENT — 15 min",
        3: "URGENT — 30 min",
        4: "SEMI-URGENT — 1h",
        5: "NON URGENT",
    }.get(esi, "?")


def _attente_estimee(esi: int) -> str:
    return {1: "< 1 min", 2: "< 15 min", 3: "~30 min", 4: "~1h", 5: "~2h"}.get(esi, "?")


def _attribuer_medecin(age: int) -> str:
    nb_m1 = len(MEDECINS["M1"]["patients"])
    nb_m2 = len(MEDECINS["M2"]["patients"])
    if nb_m1 == nb_m2:
        return "M2" if (age < 15 or age > 65) else "M1"
    return "M1" if nb_m1 < nb_m2 else "M2"


def _construire_etat_global() -> dict:
    file_triee = gestionnaire_file.get_file_triee()
    return {
        "horodatage": datetime.now().strftime("%H:%M:%S"),
        "nb_patients": len(file_triee),
        "file": [
            {
                **p.to_dict(),
                "position": i + 1,
                "nom": patients_session.get(p.patient_id, {}).get("nom", "Patient"),
                "prenom": patients_session.get(p.patient_id, {}).get("prenom", ""),
                "medecin_id": patients_session.get(p.patient_id, {}).get("medecin_id", ""),
                "symptom_text": patients_session.get(p.patient_id, {}).get("symptom_text", ""),
                "zones_corps": patients_session.get(p.patient_id, {}).get("zones_corps", []),
            }
            for i, p in enumerate(file_triee)
        ],
        "medecins": {
            mid: {**info, "nb_patients": len(info["patients"])}
            for mid, info in MEDECINS.items()
        },
        "alertes": [
            {
                **p.to_dict(),
                "nom": patients_session.get(p.patient_id, {}).get("nom", "Patient"),
                "prenom": patients_session.get(p.patient_id, {}).get("prenom", ""),
            }
            for p in gestionnaire_file.get_alertes_actives()
        ],
    }


def _construire_rapport(patient_id: str) -> dict:
    session = patients_session.get(patient_id, {})
    en_file = gestionnaire_file.file.get(patient_id)
    features_nlp = extraire_features_nlp(session.get("symptom_text", ""))
    return {
        "patient_id": patient_id,
        "nom": session.get("nom", "Inconnu"),
        "prenom": session.get("prenom", ""),
        "age": session.get("age", "?"),
        "sexe": "Homme" if session.get("sex", -1) == 1 else "Femme",
        "heure_arrivee": session.get("heure_arrivee", "?"),
        "symptom_text": session.get("symptom_text", ""),
        "zones_corps": session.get("zones_corps", []),
        "constantes": session.get("constantes", {}),
        "esi_predit": session.get("esi_predit", "?"),
        "niveau_urgence": session.get("niveau_urgence", "?"),
        "confiance_modele": session.get("confiance", "?"),
        "features_nlp_actives": {k: v for k, v in features_nlp.items() if v > 0},
        "score_priorite": round(en_file.score, 1) if en_file else "?",
        "temps_attente_min": round(en_file.temps_attente_minutes(), 1) if en_file else "?",
        "medecin_assigne": MEDECINS.get(session.get("medecin_id", ""), {}).get("nom", "?"),
        "horodatage_rapport": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }


def _get_session(session_id: str) -> dict:
    session = patients_session.get(session_id)
    if session is None:
        raise HTTPException(status_code=400, detail="Session invalide ou expirée")
    return session


# ═══════════════════════════════════════════════════════════════════════════════
# Endpoints REST
# ═══════════════════════════════════════════════════════════════════════════════

# Schéma pour POST /api/constantes/mesurer (défini ici car spécifique à ce module)
class MesureRequest(BaseModel):
    type: str                        # "temperature" | "spo2" | "tension"
    session_id: Optional[str] = None


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "patients_en_attente": len(gestionnaire_file.get_file_triee()),
        "connexions_ws": {g: len(s) for g, s in manager._groups.items()},
    }


# ── Étape 1 : Scanner identité ───────────────────────────────────────────────

@app.get("/api/camera/status")
async def api_camera_status():
    """Indique si la caméra est actuellement active (scan en cours)."""
    return {"active": _camera_active}


@app.post("/api/scanner")
async def api_scanner(body: ScannerRequest):
    """
    Scanne la CIN du patient (image base64) ou déclenche la caméra (sans image).
    La caméra est ouverte le temps du scan puis immédiatement libérée.
    Crée une session et retourne session_id + données identité extraites.
    """
    global _camera_active
    _camera_active = True
    try:
        if body.image_base64:
            image_bytes = base64.b64decode(body.image_base64.encode())
            resultat = scanner_piece_identite(source=image_bytes)
        else:
            resultat = scanner_piece_identite(source=0)
    finally:
        _camera_active = False

    # Normalisation sexe : scanner retourne 0=Femme / 1=Homme / -1=Inconnu
    # Le modèle ML attend strictement 0 (Femme) ou 1 (Homme).
    sexe_brut = resultat.get("sexe", 0)
    sex_normalise = int(sexe_brut) if sexe_brut in (0, 1) else 0

    session_id = str(uuid.uuid4())[:8].upper()
    patients_session[session_id] = {
        "session_id": session_id,
        "nom": resultat.get("nom", "Inconnu"),
        "prenom": resultat.get("prenom", ""),
        "age": int(resultat.get("age", 30) or 30),
        "sex": sex_normalise,
        "heure_arrivee": datetime.now().strftime("%H:%M"),
        "etape": "scan_ok",
    }

    return {"statut": "succès", "session_id": session_id, **resultat}


# ── Étape 2 : Symptômes + NLP ────────────────────────────────────────────────

@app.post("/api/symptomes")
async def api_symptomes(body: SymptomsRequest):
    """
    Enregistre la description libre du patient + les zones cliquées sur le
    pictogramme du corps. Lance une pré-analyse NLP immédiate.
    Émet alerte_critique aux médecins si urgence détectée dès la saisie.
    """
    session = _get_session(body.session_id)

    if not body.symptom_text.strip():
        raise HTTPException(status_code=400, detail="Veuillez décrire vos symptômes")

    session["symptom_text"] = body.symptom_text.strip()
    session["zones_corps"] = body.zones_corps
    session["etape"] = "symptomes_ok"

    features_nlp = extraire_features_nlp(body.symptom_text)
    urgence_detectee = features_nlp.get("nlp_urgence_critique", 0) == 1

    if urgence_detectee:
        await manager.broadcast_to(
            "alerte_critique",
            {
                "session_id": body.session_id,
                "nom": session.get("nom"),
                "prenom": session.get("prenom"),
                "urgence_pre_triage": True,
                "message": "Urgence détectée lors de la saisie des symptômes — patient pas encore trié",
            },
            ["medecin_M1", "medecin_M2"],
        )

    return {
        "statut": "succès",
        "session_id": body.session_id,
        "urgence_detectee": urgence_detectee,
        "features_nlp": {k: v for k, v in features_nlp.items() if v > 0},
    }


# ── Étape 3 : Constantes vitales (pull capteurs) ─────────────────────────────

@app.get("/api/constantes")
async def api_constantes(session_id: Optional[str] = Query(default=None)):
    """
    Déclenche la lecture de tous les capteurs (DS18B20, MAX30102, tensiomètre).
    Si session_id fourni, stocke les constantes dans la session.
    Diffuse constantes_update à la borne pour l'affichage temps réel.
    """
    constantes = lire_toutes_constantes()

    if session_id and session_id in patients_session:
        patients_session[session_id]["constantes"] = constantes
        patients_session[session_id]["etape"] = "constantes_ok"

    await manager.broadcast_to(
        "constantes_update",
        {"session_id": session_id, "constantes": constantes},
        ["borne"],
    )

    return {"statut": "succès", "constantes": constantes}


# ── Étape 3 : Démarrage / arrêt Arduino (lifecycle ConstantesPage) ───────────

@app.get("/api/constantes/start")
async def api_constantes_start():
    """
    Ouvre le port série USB de l'Arduino.
    Appelé au mount de ConstantesPage.jsx (useEffect cleanup).
    La détection du port peut prendre 3-5 secondes.
    """
    loop = asyncio.get_running_loop()
    connecte = await loop.run_in_executor(None, demarrer_arduino)
    return {"statut": "ok", "arduino_connecte": connecte}


@app.get("/api/constantes/stop")
async def api_constantes_stop():
    """
    Envoie MESURE:stop à l'Arduino puis ferme le port série.
    Appelé au unmount de ConstantesPage.jsx (useEffect cleanup).
    """
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, arreter_arduino)
    return {"statut": "ok"}


@app.post("/api/constantes/mesurer")
async def api_constantes_mesurer(body: MesureRequest):
    """
    Déclenche la mesure d'une seule constante vitale.
    L'Arduino mesure et répond une fois, puis s'arrête.

    body.type : "temperature" | "spo2" | "tension"
    La tension est toujours simulée (pas de tensiomètre connecté à l'Arduino).

    Stocke la constante dans la session si session_id fourni.
    Diffuse constantes_update à la borne.
    """
    import random

    types_valides = {"temperature", "spo2", "tension"}
    if body.type not in types_valides:
        raise HTTPException(status_code=400, detail=f"type doit être parmi {types_valides}")

    loop = asyncio.get_running_loop()

    if body.type == "tension":
        # Tension artérielle : toujours simulée
        sys_  = int(random.gauss(120, 15))
        sys_  = max(80, min(200, sys_))
        dias  = int(sys_ * random.uniform(0.55, 0.68))
        nouvelles = {"bp_systolic": sys_, "bp_diastolic": dias, "source": "simulation"}
    else:
        # Déléguer à l'Arduino (bloquant jusqu'à TIMEOUT_MESURE secondes)
        data = await loop.run_in_executor(None, mesurer_capteur, body.type)
        nouvelles = data

    # Stocker dans la session
    if body.session_id and body.session_id in patients_session:
        session = patients_session[body.session_id]
        constantes_session = session.get("constantes", {})
        constantes_session.update({k: v for k, v in nouvelles.items() if k != "source"})
        session["constantes"] = constantes_session
        # Marquer l'étape complète seulement quand les 4 clés vitales sont présentes
        cles_vitales = {"temperature", "spo2", "heart_rate", "bp_systolic"}
        if cles_vitales.issubset(constantes_session.keys()):
            session["etape"] = "constantes_ok"

    await manager.broadcast_to(
        "constantes_update",
        {"session_id": body.session_id, "constantes": nouvelles},
        ["borne"],
    )

    return {"statut": "succès", "type": body.type, "constantes": nouvelles}


# ── Étape 3b : Push capteurs depuis daemon Raspberry Pi ──────────────────────

@app.post("/api/mesures")
async def api_mesures_push(body: ConstantesPushRequest):
    """
    Reçu depuis hardware/daemon.py (POST http://localhost:8000/api/mesures).
    Stocke les constantes mesurées par le Pi et les diffuse à la borne.
    """
    constantes = {
        k: v for k, v in body.model_dump().items()
        if k != "session_id" and v is not None
    }

    if body.session_id and body.session_id in patients_session:
        patients_session[body.session_id]["constantes"] = constantes
        patients_session[body.session_id]["etape"] = "constantes_ok"

    await manager.broadcast_to(
        "constantes_update",
        {"session_id": body.session_id, "constantes": constantes},
        ["borne"],
    )

    return {"statut": "succès", "constantes_reçues": constantes}


# ── Étape 4 : Questions adaptatives ──────────────────────────────────────────

@app.post("/api/questions")
async def api_questions(body: QuestionsRequest):
    """
    Génère 4 questions médicales adaptatives via Groq/Llama-3.3 en fonction
    des constantes vitales et du texte de symptômes.
    Stocke les questions dans la session pour l'encodage lors du triage.
    """
    session = _get_session(body.session_id)
    constantes = body.constantes or session.get("constantes") or {}

    features_nlp_q = extraire_features_nlp(session.get("symptom_text", ""))
    questions = generer_questions(
        constantes=constantes,
        symptom_text=session.get("symptom_text", ""),
        age=int(session.get("age", 30) or 30),
        sex=int(session.get("sex", 0)),
        zones_corps=session.get("zones_corps", []),
        features_nlp=features_nlp_q,
    )

    session["questions"] = questions
    session["etape"] = "questions_ok"

    return {
        "statut": "succès",
        "session_id": body.session_id,
        "questions": questions,
    }


# ── Mapping zones pictogramme → features binaires ML ─────────────────────────
# 15 zones du CorpsHumain.jsx → features attendues par le Random Forest.
# Appliqué en OR avec le NLP : si le NLP OU la zone détectent le symptôme → 1.
_ZONES_VERS_BINAIRES: dict[str, dict[str, int]] = {
    "tete":          {"neurological_symptoms": 1},
    "cou":           {"neurological_symptoms": 1},
    "poitrine":      {"chest_pain": 1},
    "ventre":        {"abdominal_pain": 1},
    "bas_ventre":    {"abdominal_pain": 1},
    "epaule_gauche": {"chest_pain": 1, "trauma": 1},  # douleur épaule G → possible irradiation cardiaque
    "epaule_droite": {"trauma": 1},
    "bras_gauche":   {"chest_pain": 1, "trauma": 1},  # bras gauche → irradiation coronarienne
    "bras_droit":    {"trauma": 1},
    "hanche_gauche": {"trauma": 1, "abdominal_pain": 1},
    "hanche_droite": {"trauma": 1, "abdominal_pain": 1},
    "jambe_gauche":  {"trauma": 1},
    "jambe_droite":  {"trauma": 1},
    "pied_gauche":   {"trauma": 1},
    "pied_droit":    {"trauma": 1},
}


def _enrichir_binaires_depuis_zones(zones: list, binaires: dict) -> dict:
    """
    Applique un OR entre les features binaires issues du NLP et les zones
    cliquées par le patient sur le pictogramme du corps.
    Retourne un nouveau dict (le dict original n'est pas modifié).
    """
    resultat = dict(binaires)
    for zone in (zones or []):
        for feature, valeur in _ZONES_VERS_BINAIRES.get(zone, {}).items():
            resultat[feature] = max(resultat.get(feature, 0), valeur)
    return resultat


# ── Étape 5 : Triage ESI + file APQ-h ────────────────────────────────────────

@app.post("/api/triage")
async def api_triage(body: TriageRequest):
    """
    Triage complet :
    1. Encode les réponses aux questions adaptatives (68 features)
    2. Applique le NLP sur symptom_text (11 features)
    3. Prédit l'ESI via Random Forest (200 arbres)
    4. Insère le patient dans la file APQ-h
    5. Attribue un médecin (charge équilibrée + spécialité)
    6. Diffuse file_mise_a_jour + nouveau_patient via WebSocket
    7. Émet alerte_critique si ESI ≤ 2
    """
    session = _get_session(body.session_id)
    constantes = body.constantes or session.get("constantes") or lire_toutes_constantes()

    # Encoder les réponses aux questions adaptatives (68 features)
    questions = session.get("questions", [])
    features_questions = encoder_reponses(questions, body.question_reponses)

    # NLP sur le texte libre (11 features)
    features_nlp = extraire_features_nlp(session.get("symptom_text", ""))

    # Features binaires NLP enrichies par les zones du pictogramme (OR logique)
    binaires_nlp = {
        "chest_pain":            features_nlp.get("nlp_chest_pain", 0),
        "dyspnea":               features_nlp.get("nlp_dyspnea", 0),
        "loss_of_consciousness": features_nlp.get("nlp_loss_of_consciousness", 0),
        "severe_bleeding":       features_nlp.get("nlp_severe_bleeding", 0),
        "neurological_symptoms": features_nlp.get("nlp_neurological", 0),
        "abdominal_pain":        features_nlp.get("nlp_abdominal_pain", 0),
        "fever":                 features_nlp.get("nlp_fever", 0),
        "trauma":                features_nlp.get("nlp_trauma", 0),
    }
    binaires = _enrichir_binaires_depuis_zones(session.get("zones_corps", []), binaires_nlp)

    # Vecteur complet pour le modèle (~98 features)
    donnees_modele = {
        # Constantes vitales (10)
        "age":              int(session.get("age", 30) or 30),
        "sex":              int(session.get("sex", 0)),
        "temperature":      constantes.get("temperature", 37.0),
        "heart_rate":       constantes.get("heart_rate", 75),
        "bp_systolic":      constantes.get("bp_systolic", 120),
        "bp_diastolic":     constantes.get("bp_diastolic", 80),
        "spo2":             constantes.get("spo2", 98.0),
        "respiratory_rate": constantes.get("respiratory_rate", 16),
        "glucose":          constantes.get("glucose", 90),
        "pain_score":       features_nlp.get("nlp_pain_score", 0),
        # Symptômes binaires NLP + zones (8)
        **binaires,
        # Texte brut (NLP interne re-extrait dans predire_esi)
        "symptom_text": session.get("symptom_text", ""),
        # Réponses aux questions adaptatives (68 features)
        **features_questions,
    }

    try:
        resultat = predire_esi(donnees_modele)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur modèle ML : {e}")

    esi_predit: int = resultat["esi_predit"]
    medecin_id = _attribuer_medecin(session.get("age", 30))
    patient_id = f"PT-{body.session_id}"

    session.update({
        "patient_id": patient_id,
        "constantes": constantes,
        "esi_predit": esi_predit,
        "niveau_urgence": _libelle_urgence(esi_predit),
        "confiance": resultat.get("confiance", 0),
        "medecin_id": medecin_id,
        "etape": "triage_ok",
    })

    gestionnaire_file.ajouter_patient(
        patient_id=patient_id,
        esi_predit=esi_predit,
        age=session.get("age", 30),
        constantes={
            "temperature": constantes.get("temperature"),
            "spo2": constantes.get("spo2"),
            "heart_rate": constantes.get("heart_rate"),
        },
    )
    MEDECINS[medecin_id]["patients"].append(patient_id)

    position = gestionnaire_file.get_position_patient(patient_id)
    rapport = _construire_rapport(patient_id)

    # Diffusion — toutes les interfaces de surveillance
    etat = _construire_etat_global()
    await manager.broadcast_to("file_mise_a_jour", etat, ["salle", "medecin_M1", "medecin_M2"])
    await manager.broadcast_to(
        "nouveau_patient",
        {
            "patient_id": patient_id,
            "nom": session.get("nom"),
            "prenom": session.get("prenom"),
            "esi": esi_predit,
            "niveau_urgence": _libelle_urgence(esi_predit),
            "position": position,
            "attente_estimee": _attente_estimee(esi_predit),
            "medecin_id": medecin_id,
        },
        ["salle", "medecin_M1", "medecin_M2"],
    )

    # Alerte critique si ESI 1 ou 2 — médecin assigné seulement
    if esi_predit <= 2:
        await manager.broadcast_to(
            "alerte_critique",
            {
                "patient_id": patient_id,
                "nom": session.get("nom"),
                "prenom": session.get("prenom"),
                "esi": esi_predit,
                "rapport": rapport,
            },
            [f"medecin_{medecin_id}"],
        )

    return {
        "statut": "succès",
        "patient_id": patient_id,
        "esi_predit": esi_predit,
        "niveau_urgence": _libelle_urgence(esi_predit),
        "confiance": resultat.get("confiance", 0),
        "position_file": position,
        "attente_estimee": _attente_estimee(esi_predit),
        "medecin_assigne": MEDECINS[medecin_id]["nom"],
        "rapport": rapport,
    }


# ── File d'attente ────────────────────────────────────────────────────────────

@app.get("/api/file")
async def api_file():
    return {"statut": "succès", **_construire_etat_global()}


@app.get("/api/rapport/{patient_id}")
async def api_rapport(patient_id: str):
    if patient_id not in patients_session:
        raise HTTPException(status_code=404, detail="Patient non trouvé")
    return {"statut": "succès", "rapport": _construire_rapport(patient_id)}


# ── Actions médecin ───────────────────────────────────────────────────────────

@app.post("/api/prise_en_charge")
async def api_prise_en_charge(body: PriseEnChargeRequest):
    if body.medecin_id not in MEDECINS:
        raise HTTPException(status_code=404, detail="Médecin non trouvé")

    patient_file = gestionnaire_file.retirer_patient(body.patient_id)

    if body.patient_id in MEDECINS[body.medecin_id]["patients"]:
        MEDECINS[body.medecin_id]["patients"].remove(body.patient_id)

    session = patients_session.get(body.patient_id, {})
    historique_patients.append({
        **session,
        "pris_en_charge_par": MEDECINS[body.medecin_id]["nom"],
        "heure_prise_en_charge": datetime.now().strftime("%H:%M"),
        "temps_attente_reel": (
            round(patient_file.temps_attente_minutes(), 1) if patient_file else "?"
        ),
    })

    etat = _construire_etat_global()
    await manager.broadcast_to("file_mise_a_jour", etat, ["salle", "medecin_M1", "medecin_M2"])
    await manager.broadcast_to(
        "patient_pris_en_charge",
        {
            "patient_id": body.patient_id,
            "medecin": MEDECINS[body.medecin_id]["nom"],
            "heure": datetime.now().strftime("%H:%M"),
        },
        ["salle", "borne"],
    )

    return {
        "statut": "succès",
        "message": f"Patient {body.patient_id} pris en charge par {MEDECINS[body.medecin_id]['nom']}",
    }


@app.get("/api/medecin/{medecin_id}")
async def api_patients_medecin(medecin_id: str):
    if medecin_id not in MEDECINS:
        raise HTTPException(status_code=404, detail="Médecin non trouvé")

    rapports = []
    for pid in MEDECINS[medecin_id]["patients"]:
        if pid not in patients_session:
            continue
        rapport = _construire_rapport(pid)
        en_file = gestionnaire_file.file.get(pid)
        rapport["position_file"] = gestionnaire_file.get_position_patient(pid)
        rapport["temps_attente_actuel"] = (
            round(en_file.temps_attente_minutes(), 1) if en_file else "?"
        )
        rapports.append(rapport)

    rapports.sort(key=lambda r: r.get("esi_predit", 5) if isinstance(r.get("esi_predit"), int) else 5)

    return {
        "statut": "succès",
        "medecin": MEDECINS[medecin_id],
        "nb_patients": len(rapports),
        "patients": rapports,
    }


@app.post("/api/degradation")
async def api_degradation(body: DegradationRequest):
    succes = gestionnaire_file.signaler_degradation(body.patient_id, {}, body.nouvel_esi)
    if not succes:
        raise HTTPException(status_code=404, detail="Patient non trouvé dans la file")

    session = patients_session.get(body.patient_id, {})
    ancien_esi = session.get("esi_predit", "?")
    session["esi_predit"] = body.nouvel_esi
    session["niveau_urgence"] = _libelle_urgence(body.nouvel_esi)

    etat = _construire_etat_global()
    await manager.broadcast_to("file_mise_a_jour", etat, ["salle", "medecin_M1", "medecin_M2"])
    await manager.broadcast_to(
        "degradation",
        {
            "patient_id": body.patient_id,
            "nom": session.get("nom", ""),
            "ancien_esi": ancien_esi,
            "nouvel_esi": body.nouvel_esi,
            "nouveau_libelle": _libelle_urgence(body.nouvel_esi),
        },
        ["salle", "medecin_M1", "medecin_M2"],
    )

    return {"statut": "succès", "message": "Dégradation enregistrée et diffusée"}


# ═══════════════════════════════════════════════════════════════════════════════
# WebSocket — /ws
# ═══════════════════════════════════════════════════════════════════════════════

@app.websocket("/ws")
async def websocket_endpoint(
    ws: WebSocket,
    role: str = Query(default="borne"),
    medecin_id: str = Query(default=""),
) -> None:
    """
    Point d'entrée WebSocket unique. Le groupe est déterminé par les paramètres URL.

    Connexion :
      ws://localhost:8000/ws?role=borne
      ws://localhost:8000/ws?role=salle
      ws://localhost:8000/ws?role=medecin&medecin_id=M1
      ws://localhost:8000/ws?role=medecin&medecin_id=M2

    À la connexion, le serveur envoie immédiatement l'état de la file.
    Ensuite, les événements sont poussés en fonction des actions cliniques.

    Commandes acceptées depuis le client (JSON) :
      {"action": "ping"}     → {"event": "pong", "data": {"ts": "..."}}
      {"action": "get_file"} → {"event": "file_mise_a_jour", "data": {...}}
    """
    group = manager.resolve_group(role, medecin_id)
    await manager.connect(ws, group)
    try:
        # Envoi immédiat de l'état courant à la connexion
        await manager.send_one(ws, "file_mise_a_jour", _construire_etat_global())

        # Boucle d'écoute des commandes client
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            action = msg.get("action")
            if action == "ping":
                await manager.send_one(ws, "pong", {"ts": datetime.now().isoformat()})
            elif action == "get_file":
                await manager.send_one(ws, "file_mise_a_jour", _construire_etat_global())

    except WebSocketDisconnect:
        manager.disconnect(ws, group)
    except Exception:
        manager.disconnect(ws, group)


# ═══════════════════════════════════════════════════════════════════════════════
# Point d'entrée
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
