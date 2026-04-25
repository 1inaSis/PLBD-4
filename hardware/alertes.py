"""
=============================================================================
HEALTH GATE — alertes.py
=============================================================================
 
RÔLE DE CE MODULE
-----------------
Ce fichier est responsable de la détection et de l'envoi d'alertes critiques
basées sur les mesures biométriques du capteur MAX30100 (SpO2 + fréquence
cardiaque). Il tourne en arrière-plan et surveille en permanence les données
reçues. Quand une mesure dépasse un seuil médical critique, il notifie
immédiatement le backend Java via l'API REST.
 
COMPOSANTS PRINCIPAUX
----------------------
 
1. SEUILS MÉDICAUX (constantes en haut du fichier)
   Définit les valeurs limites reconnues médicalement :
   - SpO2 < 90% → urgence absolue (hypoxémie sévère)
   - SpO2 entre 90% et 94% → zone de vigilance
   - Fréquence cardiaque < 40 bpm → bradycardie sévère
   - Fréquence cardiaque > 150 bpm → tachycardie sévère
 
2. CLASSE AlertLevel (Enum)
   Représente les niveaux de gravité d'une alerte :
   - CRITIQUE : nécessite une intervention immédiate
   - AVERTISSEMENT : surveiller de près
   - NORMAL : aucune action requise
 
3. CLASSE BiometricAlert (dataclass)
   Structure de données qui représente une alerte :
   contient le type de mesure, la valeur, le niveau, et l'horodatage.
 
4. CLASSE AlertManager
   Le cerveau du module. Contient toutes les méthodes :
   - analyser_spo2() : évalue la saturation en oxygène
   - analyser_frequence_cardiaque() : évalue le rythme cardiaque
   - evaluer_mesures() : point d'entrée principal, appelle les deux analyses
   - envoyer_alerte_backend() : envoie l'alerte au backend Java via HTTP POST
   - envoyer_alerte_nextion() : affiche un message d'urgence sur l'écran Nextion
   - historique_alertes : garde en mémoire les dernières alertes
 
5. FONCTION surveiller_en_continu()
   Boucle infinie (daemon) qui appelle evaluer_mesures() toutes les
   INTERVALLE_VERIFICATION secondes. Utilisée quand alertes.py est
   lancé seul en ligne de commande.
 
FLUX D'EXÉCUTION
----------------
sensor_manager.py lit le MAX30100
        ↓
daemon.py appelle evaluer_mesures(spo2, fc)
        ↓
AlertManager analyse les valeurs
        ↓
Si alerte détectée → envoyer_alerte_backend() + envoyer_alerte_nextion()
        ↓
Backend Java reçoit l'alerte → notifie les soignants via WebSocket
 
DÉPENDANCES
-----------
- requests : pour les appels HTTP vers le backend Java
- serial : pour la communication avec l'écran Nextion
- logging : pour tracer toutes les alertes dans un fichier de log
- dataclasses, enum : structures de données Python standard
 
=============================================================================
"""
 
import requests
import serial
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Optional, List
 
 
# =============================================================================
# CONFIGURATION LOGGING
# Toutes les alertes sont tracées dans un fichier pour la traçabilité médicale
# =============================================================================
 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("alertes.log"),
        logging.StreamHandler()  # affiche aussi dans le terminal
    ]
)
logger = logging.getLogger(__name__)
 
 
# =============================================================================
# CONSTANTES — SEUILS MÉDICAUX
# Basés sur les standards OMS et le Manchester Triage System
# =============================================================================
 
# SpO2 (Saturation en oxygène du sang) — en pourcentage
SPO2_CRITIQUE_MIN = 90.0       # En dessous → hypoxémie sévère, urgence absolue
SPO2_AVERTISSEMENT_MIN = 94.0  # Entre 90 et 94 → zone de vigilance
 
# Fréquence cardiaque — en battements par minute (bpm)
FC_BRADYCARDIE_SEVERE = 40     # En dessous → bradycardie sévère
FC_BRADYCARDIE_LEGERE = 50     # Entre 40 et 50 → bradycardie légère
FC_TACHYCARDIE_SEVERE = 150    # Au dessus → tachycardie sévère
FC_TACHYCARDIE_LEGERE = 100    # Entre 100 et 150 → tachycardie légère
 
# Intervalle de vérification en secondes (utilisé si mode daemon autonome)
INTERVALLE_VERIFICATION = 5
 
# URL du backend Java Spring Boot
BACKEND_URL = "http://localhost:8080/api/alertes"
 
# Port série de l'écran Nextion
NEXTION_PORT = "/dev/ttyS0"
NEXTION_BAUDRATE = 9600
 
 
# =============================================================================
# ENUM — NIVEAUX D'ALERTE
# =============================================================================
 
class AlertLevel(Enum):
    NORMAL = "NORMAL"
    AVERTISSEMENT = "AVERTISSEMENT"
    CRITIQUE = "CRITIQUE"
 
 
# =============================================================================
# DATACLASS — STRUCTURE D'UNE ALERTE
# Représente une alerte unique avec toutes ses métadonnées
# =============================================================================
 
@dataclass
class BiometricAlert:
    type_mesure: str          # "SPO2" ou "FREQUENCE_CARDIAQUE"
    valeur: float             # Valeur brute mesurée
    niveau: AlertLevel        # CRITIQUE, AVERTISSEMENT, ou NORMAL
    message: str              # Message lisible par un soignant
    horodatage: datetime = field(default_factory=datetime.now)
    patient_id: Optional[str] = None  # ID du patient si disponible
 
    def to_dict(self) -> dict:
        """Convertit l'alerte en dictionnaire pour l'envoi JSON au backend."""
        return {
            "type_mesure": self.type_mesure,
            "valeur": self.valeur,
            "niveau": self.niveau.value,
            "message": self.message,
            "horodatage": self.horodatage.isoformat(),
            "patient_id": self.patient_id
        }
 
 
# =============================================================================
# CLASSE PRINCIPALE — ALERTMANAGER
# Gère toute la logique d'analyse et d'envoi des alertes
# =============================================================================
 
class AlertManager:
 
    def __init__(self):
        self.historique_alertes: List[BiometricAlert] = []
        self.nextion_connecte = False
        self._initialiser_nextion()
 
    # -------------------------------------------------------------------------
    # INITIALISATION NEXTION
    # Tentative de connexion à l'écran série au démarrage
    # -------------------------------------------------------------------------
 
    def _initialiser_nextion(self):
        """Tente d'ouvrir la connexion série avec l'écran Nextion."""
        try:
            self.nextion = serial.Serial(NEXTION_PORT, NEXTION_BAUDRATE, timeout=1)
            self.nextion_connecte = True
            logger.info("Écran Nextion connecté sur %s", NEXTION_PORT)
        except serial.SerialException as e:
            logger.warning("Nextion non disponible : %s — les alertes écran seront ignorées", e)
            self.nextion_connecte = False
 
    # -------------------------------------------------------------------------
    # ANALYSE SPO2
    # Évalue la saturation en oxygène et retourne une alerte si nécessaire
    # -------------------------------------------------------------------------
 
    def analyser_spo2(self, spo2: float, patient_id: Optional[str] = None) -> Optional[BiometricAlert]:
        """
        Analyse la valeur SpO2 et retourne une BiometricAlert si un seuil
        médical est dépassé, ou None si la valeur est normale.
        """
        if spo2 < SPO2_CRITIQUE_MIN:
            return BiometricAlert(
                type_mesure="SPO2",
                valeur=spo2,
                niveau=AlertLevel.CRITIQUE,
                message=f"SpO2 critique : {spo2:.1f}% — hypoxémie sévère, intervention immédiate requise",
                patient_id=patient_id
            )
        elif spo2 < SPO2_AVERTISSEMENT_MIN:
            return BiometricAlert(
                type_mesure="SPO2",
                valeur=spo2,
                niveau=AlertLevel.AVERTISSEMENT,
                message=f"SpO2 basse : {spo2:.1f}% — surveillance rapprochée recommandée",
                patient_id=patient_id
            )
        return None  # valeur normale, aucune alerte
 
    # -------------------------------------------------------------------------
    # ANALYSE FRÉQUENCE CARDIAQUE
    # Évalue le rythme cardiaque et retourne une alerte si nécessaire
    # -------------------------------------------------------------------------
 
    def analyser_frequence_cardiaque(self, fc: float, patient_id: Optional[str] = None) -> Optional[BiometricAlert]:
        """
        Analyse la fréquence cardiaque et retourne une BiometricAlert si un
        seuil médical est dépassé, ou None si la valeur est normale.
        """
        if fc < FC_BRADYCARDIE_SEVERE:
            return BiometricAlert(
                type_mesure="FREQUENCE_CARDIAQUE",
                valeur=fc,
                niveau=AlertLevel.CRITIQUE,
                message=f"Bradycardie sévère : {fc:.0f} bpm — risque d'arrêt cardiaque",
                patient_id=patient_id
            )
        elif fc < FC_BRADYCARDIE_LEGERE:
            return BiometricAlert(
                type_mesure="FREQUENCE_CARDIAQUE",
                valeur=fc,
                niveau=AlertLevel.AVERTISSEMENT,
                message=f"Bradycardie légère : {fc:.0f} bpm — surveillance recommandée",
                patient_id=patient_id
            )
        elif fc > FC_TACHYCARDIE_SEVERE:
            return BiometricAlert(
                type_mesure="FREQUENCE_CARDIAQUE",
                valeur=fc,
                niveau=AlertLevel.CRITIQUE,
                message=f"Tachycardie sévère : {fc:.0f} bpm — risque d'arythmie critique",
                patient_id=patient_id
            )
        elif fc > FC_TACHYCARDIE_LEGERE:
            return BiometricAlert(
                type_mesure="FREQUENCE_CARDIAQUE",
                valeur=fc,
                niveau=AlertLevel.AVERTISSEMENT,
                message=f"Tachycardie légère : {fc:.0f} bpm — surveillance recommandée",
                patient_id=patient_id
            )
        return None  # valeur normale, aucune alerte
 
    # -------------------------------------------------------------------------
    # POINT D'ENTRÉE PRINCIPAL
    # Reçoit SpO2 + FC, analyse les deux, envoie les alertes si nécessaire
    # -------------------------------------------------------------------------
 
    def evaluer_mesures(self, spo2: float, fc: float, patient_id: Optional[str] = None):
        """
        Point d'entrée appelé par daemon.py à chaque nouvelle mesure.
        Analyse SpO2 et FC, et déclenche les alertes si des seuils sont dépassés.
        """
        logger.info("Évaluation — SpO2: %.1f%% | FC: %.0f bpm | Patient: %s", spo2, fc, patient_id or "inconnu")
 
        alertes_detectees = []
 
        # Analyse des deux mesures
        alerte_spo2 = self.analyser_spo2(spo2, patient_id)
        alerte_fc = self.analyser_frequence_cardiaque(fc, patient_id)
 
        if alerte_spo2:
            alertes_detectees.append(alerte_spo2)
 
        if alerte_fc:
            alertes_detectees.append(alerte_fc)
 
        # Traitement de chaque alerte détectée
        for alerte in alertes_detectees:
            self.historique_alertes.append(alerte)
            logger.warning("[%s] %s", alerte.niveau.value, alerte.message)
            self.envoyer_alerte_backend(alerte)
 
            # Seules les alertes critiques s'affichent sur le Nextion
            if alerte.niveau == AlertLevel.CRITIQUE:
                self.envoyer_alerte_nextion(alerte)
 
        if not alertes_detectees:
            logger.info("Mesures dans les normes — aucune alerte")
 
    # -------------------------------------------------------------------------
    # ENVOI AU BACKEND JAVA
    # HTTP POST vers Spring Boot — les soignants sont notifiés via WebSocket
    # -------------------------------------------------------------------------
 
    def envoyer_alerte_backend(self, alerte: BiometricAlert):
        """
        Envoie l'alerte au backend Java via HTTP POST.
        Le backend relaie ensuite aux soignants via WebSocket en temps réel.
        """
        try:
            response = requests.post(
                BACKEND_URL,
                json=alerte.to_dict(),
                timeout=3  # timeout court — on est en contexte d'urgence
            )
            if response.status_code == 200:
                logger.info("Alerte envoyée au backend avec succès")
            else:
                logger.error("Backend a répondu avec le code : %d", response.status_code)
        except requests.exceptions.ConnectionError:
            logger.error("Backend inaccessible — alerte non transmise : %s", alerte.message)
        except requests.exceptions.Timeout:
            logger.error("Timeout — le backend ne répond pas dans les 3 secondes")
 
    # -------------------------------------------------------------------------
    # AFFICHAGE SUR NEXTION
    # Envoie une commande série pour afficher le message d'urgence sur l'écran
    # -------------------------------------------------------------------------
 
    def envoyer_alerte_nextion(self, alerte: BiometricAlert):
        """
        Affiche un message d'alerte critique sur l'écran Nextion via Serial.
        Le Nextion reçoit une commande texte et l'affiche immédiatement.
        Format Nextion : commande + trois octets 0xFF de terminaison.
        """
        if not self.nextion_connecte:
            return
 
        try:
            # Construction de la commande Nextion
            # t0.txt = composant texte nommé "t0" dans l'interface Nextion Editor
            message_court = alerte.message[:50]  # Nextion limite la longueur
            commande = f't0.txt="{message_court}"\xFF\xFF\xFF'
            self.nextion.write(commande.encode("utf-8"))
            logger.info("Alerte affichée sur Nextion : %s", message_court)
        except serial.SerialException as e:
            logger.error("Erreur d'envoi Nextion : %s", e)
 
    # -------------------------------------------------------------------------
    # HISTORIQUE
    # Retourne les N dernières alertes pour consultation ou log
    # -------------------------------------------------------------------------
 
    def get_dernières_alertes(self, n: int = 10) -> List[BiometricAlert]:
        """Retourne les n dernières alertes enregistrées."""
        return self.historique_alertes[-n:]
 
 
# =============================================================================
# MODE DAEMON AUTONOME
# Si alertes.py est lancé directement (python alertes.py), il démarre une
# boucle de surveillance en important les mesures depuis sensor_manager.py
# =============================================================================
 
def surveiller_en_continu():
    """
    Boucle infinie de surveillance. Importe sensor_manager pour lire
    les mesures en direct depuis le MAX30100.
    Utilisée uniquement si ce fichier est lancé en standalone.
    """
    from sensor_manager import SensorManager
 
    manager = AlertManager()
    sensor = SensorManager()
 
    logger.info("Démarrage de la surveillance biométrique en continu...")
 
    while True:
        try:
            mesures = sensor.lire_mesures()
            if mesures:
                manager.evaluer_mesures(
                    spo2=mesures["spo2"],
                    fc=mesures["frequence_cardiaque"],
                    patient_id=mesures.get("patient_id")
                )
        except Exception as e:
            logger.error("Erreur inattendue dans la boucle de surveillance : %s", e)
 
        time.sleep(INTERVALLE_VERIFICATION)
 
 
if __name__ == "__main__":
    surveiller_en_continu()
 
 