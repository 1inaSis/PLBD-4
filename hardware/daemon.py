"""
=============================================================================
HEALTH GATE — daemon.py
=============================================================================
 
RÔLE DE CE MODULE
-----------------
C'est le chef d'orchestre de toute la couche hardware. Il tourne en
arrière-plan dès que la borne démarre et gère le cycle de vie complet
d'une mesure patient : attente du doigt → stabilisation 20 secondes →
lecture unique → envoi au backend → réinitialisation pour le patient suivant.
 
COMPOSANTS PRINCIPAUX
----------------------
 
1. CLASSE PatientSession
   Représente la session d'un seul patient sur le capteur.
   Gère l'état : EN_ATTENTE → STABILISATION → MESURE_PRISE → TERMINÉE
 
2. CLASSE Daemon
   Le cœur du module. Contient la boucle principale et coordonne :
   - sensor_manager.py : lecture physique du MAX30100
   - alertes.py       : analyse et envoi des alertes critiques
   - Le backend Java  : envoi des mesures finales via HTTP POST
 
3. LOGIQUE DE MESURE UNIQUE
   Le capteur a besoin de 20 secondes pour se stabiliser.
   On attend, on prend la moyenne des 5 dernières lectures,
   on envoie UNE seule fois, puis on libère le capteur.
 
FLUX D'EXÉCUTION
----------------
Borne allumée → daemon démarre
        ↓
Attente qu'un doigt soit posé sur le MAX30100
        ↓
Stabilisation 20 secondes (lectures intermédiaires ignorées)
        ↓
Moyenne des 5 dernières lectures → valeur finale fiable
        ↓
Envoi au backend Java + analyse alertes
        ↓
Réinitialisation → attente du patient suivant
 
=============================================================================
"""
 
import time
import logging
import requests
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
 
from sensor_manager import SensorManager
from alertes import AlertManager
 
 
# =============================================================================
# CONFIGURATION LOGGING
# =============================================================================
 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("daemon.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
 
 
# =============================================================================
# CONSTANTES
# =============================================================================
 
BACKEND_URL = "http://localhost:8080/api/mesures"
 
# Durée de stabilisation en secondes avant de prendre la mesure finale
DUREE_STABILISATION = 20
 
# Nombre de lectures à moyenner à la fin de la stabilisation
NB_LECTURES_MOYENNE = 5
 
# Intervalle entre chaque lecture pendant la stabilisation (en secondes)
INTERVALLE_LECTURE = 2
 
# Seuil minimum de SpO2 pour considérer qu'un doigt est posé sur le capteur
# En dessous de cette valeur, le capteur renvoie 0 ou des valeurs aberrantes
SPO2_SEUIL_PRESENCE = 50.0
 
 
# =============================================================================
# ENUM — ÉTATS DE LA SESSION
# =============================================================================
 
class EtatSession(Enum):
    EN_ATTENTE     = "EN_ATTENTE"      # Pas de doigt sur le capteur
    STABILISATION  = "STABILISATION"   # Doigt détecté, attente 20s
    MESURE_PRISE   = "MESURE_PRISE"    # Mesure finale calculée
    TERMINEE       = "TERMINEE"        # Envoyée au backend, session fermée
 
 
# =============================================================================
# DATACLASS — SESSION PATIENT
# Représente le cycle complet d'un patient sur la borne
# =============================================================================
 
@dataclass
class PatientSession:
    patient_id: Optional[str] = None
    debut_stabilisation: Optional[float] = None   # timestamp float
    lectures_intermediaires: list = field(default_factory=list)
    spo2_finale: Optional[float] = None
    fc_finale: Optional[float] = None
    etat: EtatSession = EtatSession.EN_ATTENTE
    horodatage_mesure: Optional[datetime] = None
 
    def reset(self):
        """Réinitialise la session pour accueillir le patient suivant."""
        self.patient_id = None
        self.debut_stabilisation = None
        self.lectures_intermediaires = []
        self.spo2_finale = None
        self.fc_finale = None
        self.etat = EtatSession.EN_ATTENTE
        self.horodatage_mesure = None
 
 
# =============================================================================
# CLASSE PRINCIPALE — DAEMON
# =============================================================================
 
class Daemon:
 
    def __init__(self):
        self.sensor = SensorManager()
        self.alert_manager = AlertManager()
        self.session = PatientSession()
        logger.info("Daemon Health Gate démarré — en attente d'un patient")
 
    # -------------------------------------------------------------------------
    # DÉTECTION DE PRÉSENCE
    # Un doigt est considéré présent si le capteur renvoie une SpO2 > 50%
    # En dessous, le MAX30100 renvoie des valeurs aberrantes ou nulles
    # -------------------------------------------------------------------------
 
    def _doigt_present(self, spo2: float) -> bool:
        return spo2 is not None and spo2 > SPO2_SEUIL_PRESENCE
 
    # -------------------------------------------------------------------------
    # CALCUL DE LA MOYENNE FINALE
    # Prend les NB_LECTURES_MOYENNE dernières lectures et calcule la moyenne
    # C'est cette valeur unique qui sera envoyée au backend
    # -------------------------------------------------------------------------
 
    def _calculer_moyenne(self) -> tuple:
        """
        Retourne (spo2_moyenne, fc_moyenne) à partir des dernières lectures.
        On prend les N dernières pour ignorer les lectures instables du début.
        """
        dernieres = self.session.lectures_intermediaires[-NB_LECTURES_MOYENNE:]
 
        spo2_moy = sum(l["spo2"] for l in dernieres) / len(dernieres)
        fc_moy   = sum(l["fc"]   for l in dernieres) / len(dernieres)
 
        return round(spo2_moy, 1), round(fc_moy, 1)
 
    # -------------------------------------------------------------------------
    # ENVOI AU BACKEND JAVA
    # Envoie la mesure finale unique — appelé une seule fois par patient
    # -------------------------------------------------------------------------
 
    def _envoyer_au_backend(self, spo2: float, fc: float):
        """
        Envoie la mesure biométrique finale au backend Java via HTTP POST.
        Cette fonction n'est appelée qu'une seule fois par patient.
        """
        payload = {
            "patient_id": self.session.patient_id,
            "spo2": spo2,
            "frequence_cardiaque": fc,
            "horodatage": self.session.horodatage_mesure.isoformat()
        }
 
        try:
            response = requests.post(BACKEND_URL, json=payload, timeout=3)
            if response.status_code == 200:
                logger.info("Mesures envoyées au backend — SpO2: %.1f%% | FC: %.0f bpm", spo2, fc)
            else:
                logger.error("Backend a répondu avec le code : %d", response.status_code)
        except requests.exceptions.ConnectionError:
            logger.error("Backend inaccessible — mesures non transmises")
        except requests.exceptions.Timeout:
            logger.error("Timeout — backend ne répond pas")
 
    # -------------------------------------------------------------------------
    # BOUCLE PRINCIPALE
    # Machine à états : EN_ATTENTE → STABILISATION → MESURE_PRISE → TERMINEE
    # -------------------------------------------------------------------------
 
    def _cycle(self):
        """
        Un cycle de la boucle principale.
        Lit le capteur et fait avancer la machine à états selon l'état actuel.
        """
        mesure = self.sensor.lire_mesures()
 
        if not mesure:
            return  # capteur non disponible, on attend
 
        spo2 = mesure.get("spo2", 0)
        fc   = mesure.get("frequence_cardiaque", 0)
 
        # ------------------------------------------------------------------
        # ÉTAT 1 : EN_ATTENTE — on attend qu'un doigt soit posé
        # ------------------------------------------------------------------
        if self.session.etat == EtatSession.EN_ATTENTE:
 
            if self._doigt_present(spo2):
                logger.info("Doigt détecté — début de la stabilisation (20 secondes)")
                self.session.etat = EtatSession.STABILISATION
                self.session.debut_stabilisation = time.time()
                self.session.patient_id = mesure.get("patient_id")
 
        # ------------------------------------------------------------------
        # ÉTAT 2 : STABILISATION — on attend 20 secondes
        # On collecte les lectures mais on ne décide pas encore
        # ------------------------------------------------------------------
        elif self.session.etat == EtatSession.STABILISATION:
 
            # Si le doigt a été retiré pendant la stabilisation → reset
            if not self._doigt_present(spo2):
                logger.warning("Doigt retiré pendant la stabilisation — reset")
                self.session.reset()
                return
 
            # Collecte des lectures intermédiaires
            self.session.lectures_intermediaires.append({"spo2": spo2, "fc": fc})
 
            temps_ecoule = time.time() - self.session.debut_stabilisation
            restant = DUREE_STABILISATION - temps_ecoule
            logger.info("Stabilisation en cours — %.0fs restantes | SpO2: %.1f%% | FC: %.0f bpm",
                        restant, spo2, fc)
 
            # Les 20 secondes sont écoulées → on calcule la mesure finale
            if temps_ecoule >= DUREE_STABILISATION:
 
                if len(self.session.lectures_intermediaires) < NB_LECTURES_MOYENNE:
                    logger.warning("Pas assez de lectures — reset")
                    self.session.reset()
                    return
 
                spo2_finale, fc_finale = self._calculer_moyenne()
                self.session.spo2_finale = spo2_finale
                self.session.fc_finale = fc_finale
                self.session.horodatage_mesure = datetime.now()
                self.session.etat = EtatSession.MESURE_PRISE
 
                logger.info("Mesure finale — SpO2: %.1f%% | FC: %.0f bpm", spo2_finale, fc_finale)
 
        # ------------------------------------------------------------------
        # ÉTAT 3 : MESURE_PRISE — on envoie, une seule fois
        # ------------------------------------------------------------------
        elif self.session.etat == EtatSession.MESURE_PRISE:
 
            # Envoi au backend Java
            self._envoyer_au_backend(self.session.spo2_finale, self.session.fc_finale)
 
            # Analyse des alertes critiques
            self.alert_manager.evaluer_mesures(
                spo2=self.session.spo2_finale,
                fc=self.session.fc_finale,
                patient_id=self.session.patient_id
            )
 
            self.session.etat = EtatSession.TERMINEE
 
        # ------------------------------------------------------------------
        # ÉTAT 4 : TERMINÉE — on attend que le doigt soit retiré puis reset
        # ------------------------------------------------------------------
        elif self.session.etat == EtatSession.TERMINEE:
 
            if not self._doigt_present(spo2):
                logger.info("Patient parti — réinitialisation pour le patient suivant")
                self.session.reset()
 
    # -------------------------------------------------------------------------
    # LANCEMENT DE LA BOUCLE INFINIE
    # -------------------------------------------------------------------------
 
    def demarrer(self):
        """Lance la boucle infinie du daemon. S'arrête sur Ctrl+C."""
        logger.info("Boucle principale démarrée")
        try:
            while True:
                self._cycle()
                time.sleep(INTERVALLE_LECTURE)
        except KeyboardInterrupt:
            logger.info("Daemon arrêté manuellement")
 
 
# =============================================================================