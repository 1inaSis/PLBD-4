from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ScannerRequest(BaseModel):
    image_base64: Optional[str] = None


class SymptomsRequest(BaseModel):
    session_id: str
    symptom_text: str
    zones_corps: List[str] = Field(default_factory=list)


class QuestionsRequest(BaseModel):
    session_id: str
    constantes: Optional[Dict[str, Any]] = None


class TriageRequest(BaseModel):
    session_id: str
    constantes: Optional[Dict[str, Any]] = None
    question_reponses: Dict[str, Any] = Field(default_factory=dict)


class PriseEnChargeRequest(BaseModel):
    patient_id: str
    medecin_id: str


class DegradationRequest(BaseModel):
    patient_id: str
    nouvel_esi: int


class ConstantesPushRequest(BaseModel):
    """Reçu depuis le daemon Raspberry Pi (hardware/daemon.py → POST /api/mesures)."""
    session_id: Optional[str] = None
    temperature: Optional[float] = None
    spo2: Optional[float] = None
    heart_rate: Optional[int] = None
    bp_systolic: Optional[int] = None
    bp_diastolic: Optional[int] = None
    respiratory_rate: Optional[int] = None
    glucose: Optional[float] = None
