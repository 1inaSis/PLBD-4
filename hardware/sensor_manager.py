"""
=============================================================================
HEALTH GATE — sensor_manager.py
=============================================================================
 
RÔLE DE CE MODULE
-----------------
Ce fichier est la couche de communication directe avec le capteur physique
MAX30100. Il est le seul fichier du projet qui parle au matériel. Tous les
autres fichiers (daemon.py, alertes.py) lui demandent des mesures sans
savoir comment le capteur fonctionne techniquement.
 
Sur Mac (développement) → simule des valeurs aléatoires réalistes
Sur Raspberry Pi (production) → lit le vrai capteur MAX30100 via I2C
 
COMPOSANTS PRINCIPAUX
----------------------
 
1. DÉTECTION DE L'ENVIRONNEMENT
   Au démarrage, le module détecte automatiquement s'il tourne sur un
   Raspberry Pi ou sur un Mac. Sur Mac, la bibliothèque RPi.GPIO n'existe
   pas — on active le mode simulation automatiquement.
 
2. CLASSE MAX30100Reader
   Gère la connexion I2C avec le capteur physique sur Raspberry Pi.
   Le MAX30100 communique via le protocole I2C sur les broches GPIO du Pi.
   Cette classe initialise la connexion et lit les registres du capteur.
 
3. CLASSE SensorManager
   Point d'entrée principal utilisé par daemon.py et alertes.py.
   Contient la méthode lire_mesures() qui retourne SpO2 et FC.
   En mode simulation, génère des valeurs réalistes avec des cas critiques
   occasionnels pour pouvoir tester les alertes.
 
4. MODE SIMULATION
   Génère des valeurs aléatoires dans des plages médicalement réalistes.
   10% du temps génère des valeurs critiques pour tester les alertes.
   Indispensable pour développer et tester sans le vrai matériel.
 
PROTOCOLE I2C — EXPLICATION SIMPLE
------------------------------------
I2C (Inter-Integrated Circuit) est un protocole de communication série
qui permet au Raspberry Pi de parler à des capteurs via seulement 2 fils :
- SDA (Serial Data)  → broche GPIO 2 du Raspberry Pi
- SCL (Serial Clock) → broche GPIO 3 du Raspberry Pi
Le MAX30100 a une adresse I2C fixe : 0x57
 
DÉPENDANCES
-----------
- smbus2    : communication I2C avec le MAX30100 (Raspberry Pi uniquement)
- RPi.GPIO  : accès aux broches GPIO du Raspberry Pi
- random    : génération de valeurs simulées (mode développement Mac)
- logging   : traçabilité des lectures
 
=============================================================================
"""
 
import time
import random
import logging
from typing import Optional, Dict
 
# =============================================================================
# CONFIGURATION LOGGING
# =============================================================================
 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("sensor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
 
 
# =============================================================================
# DÉTECTION DE L'ENVIRONNEMENT
# On essaie d'importer les bibliothèques Raspberry Pi.
# Sur Mac elles n'existent pas → mode simulation automatique.
# =============================================================================
 
MODE_SIMULATION = False
 
try:
    import smbus2
    import RPi.GPIO as GPIO
    logger.info("Bibliothèques Raspberry Pi détectées — mode matériel réel activé")
except ImportError:
    MODE_SIMULATION = True
    logger.warning("RPi.GPIO non disponible — mode simulation activé (développement Mac)")
 
 
# =============================================================================
# CONSTANTES — CONFIGURATION DU CAPTEUR MAX30100
# =============================================================================
 
# Adresse I2C du MAX30100 (fixée par le fabricant, ne pas modifier)
MAX30100_ADRESSE_I2C = 0x57
 
# Registres internes du MAX30100
# Ce sont des adresses mémoire dans la puce qu'on lit via I2C
REGISTRE_SPO2_DATA   = 0x05   # Registre contenant la donnée SpO2
REGISTRE_HR_DATA     = 0x06   # Registre contenant la fréquence cardiaque
REGISTRE_MODE_CONFIG = 0x06   # Registre de configuration du mode
REGISTRE_INT_STATUS  = 0x00   # Registre de statut des interruptions
 
# Bus I2C numéro 1 sur Raspberry Pi (broches GPIO 2 et 3)
I2C_BUS = 1
 
# Plages de valeurs normales pour la validation des lectures
SPO2_MIN_VALIDE = 70.0    # En dessous → lecture aberrante à ignorer
SPO2_MAX_VALIDE = 100.0
FC_MIN_VALIDE   = 30.0
FC_MAX_VALIDE   = 220.0
 
 
# =============================================================================
# CLASSE MAX30100Reader
# Gère la communication I2C directe avec le capteur physique.
# Utilisée uniquement sur Raspberry Pi en production.
# =============================================================================
 
class MAX30100Reader:
 
    def __init__(self):
        """Initialise la connexion I2C avec le capteur MAX30100."""
        if MODE_SIMULATION:
            return
 
        try:
            self.bus = smbus2.SMBus(I2C_BUS)
            self._configurer_capteur()
            logger.info("MAX30100 initialisé sur le bus I2C %d à l'adresse 0x%02X",
                       I2C_BUS, MAX30100_ADRESSE_I2C)
        except Exception as e:
            logger.error("Impossible d'initialiser le MAX30100 : %s", e)
            raise
 
    def _configurer_capteur(self):
        """
        Configure le MAX30100 en mode SpO2 + fréquence cardiaque.
        On écrit dans le registre de configuration pour activer les deux LEDs
        infrarouge et rouge que le capteur utilise pour mesurer le sang.
        """
        try:
            # Mode 0x03 = SpO2 activé (LED rouge + infrarouge)
            self.bus.write_byte_data(MAX30100_ADRESSE_I2C, REGISTRE_MODE_CONFIG, 0x03)
            time.sleep(0.1)  # Attendre que le capteur applique la configuration
            logger.info("MAX30100 configuré en mode SpO2")
        except Exception as e:
            logger.error("Erreur de configuration du MAX30100 : %s", e)
            raise
 
    def lire_registres(self) -> Optional[Dict]:
        """
        Lit les registres bruts du MAX30100 via I2C.
        Retourne les valeurs brutes SpO2 et FC, ou None si erreur.
        """
        try:
            # Lecture des données depuis les registres du capteur
            spo2_raw = self.bus.read_byte_data(MAX30100_ADRESSE_I2C, REGISTRE_SPO2_DATA)
            hr_raw   = self.bus.read_byte_data(MAX30100_ADRESSE_I2C, REGISTRE_HR_DATA)
 
            return {
                "spo2_raw": spo2_raw,
                "hr_raw": hr_raw
            }
        except Exception as e:
            logger.error("Erreur de lecture I2C : %s", e)
            return None
 
 
# =============================================================================
# CLASSE PRINCIPALE — SensorManager
# Point d'entrée utilisé par daemon.py et alertes.py.
# Abstraite le matériel — les autres fichiers ne savent pas si on simule
# ou si on lit un vrai capteur.
# =============================================================================
 
class SensorManager:
 
    def __init__(self):
        self.patient_id_courant: Optional[str] = None
 
        if not MODE_SIMULATION:
            self.reader = MAX30100Reader()
        else:
            self.reader = None
            logger.info("SensorManager démarré en mode simulation")
 
    # -------------------------------------------------------------------------
    # DÉFINIR LE PATIENT COURANT
    # Appelé par daemon.py quand un nouveau patient est identifié via la CIN
    # -------------------------------------------------------------------------
 
    def definir_patient(self, patient_id: str):
        """
        Associe les prochaines mesures à un patient identifié.
        Appelé après le scan de la CIN par le module scanner.
        """
        self.patient_id_courant = patient_id
        logger.info("Patient défini pour les prochaines mesures : %s", patient_id)
 
    def reinitialiser_patient(self):
        """Réinitialise l'ID patient après la fin de la session."""
        self.patient_id_courant = None
 
    # -------------------------------------------------------------------------
    # VALIDATION DES VALEURS
    # Vérifie que les valeurs lues sont dans des plages médicalement possibles
    # -------------------------------------------------------------------------
 
    def _valeur_valide(self, spo2: float, fc: float) -> bool:
        """
        Retourne True si les valeurs sont dans des plages médicalement
        possibles. Les valeurs hors plage indiquent une lecture aberrante
        (doigt mal posé, interférence lumineuse, etc.)
        """
        spo2_ok = SPO2_MIN_VALIDE <= spo2 <= SPO2_MAX_VALIDE
        fc_ok   = FC_MIN_VALIDE   <= fc   <= FC_MAX_VALIDE
 
        if not spo2_ok:
            logger.warning("SpO2 aberrante ignorée : %.1f%%", spo2)
        if not fc_ok:
            logger.warning("FC aberrante ignorée : %.0f bpm", fc)
 
        return spo2_ok and fc_ok
 
    # -------------------------------------------------------------------------
    # LECTURE SIMULÉE — Mode développement Mac
    # Génère des valeurs réalistes avec des cas critiques occasionnels
    # -------------------------------------------------------------------------
 
    def _lire_simulation(self) -> Optional[Dict]:
        """
        Génère des mesures simulées réalistes.
        90% du temps : valeurs normales
        10% du temps : valeurs critiques pour tester les alertes
        """
        # 10% de chance de générer un cas critique pour tester les alertes
        cas_critique = random.random() < 0.10
 
        if cas_critique:
            choix = random.choice(["hypoxemie", "tachycardie", "bradycardie"])
 
            if choix == "hypoxemie":
                spo2 = round(random.uniform(82.0, 89.9), 1)
                fc   = round(random.uniform(60.0, 100.0), 1)
                logger.info("[SIMULATION] Cas critique — hypoxémie")
 
            elif choix == "tachycardie":
                spo2 = round(random.uniform(94.0, 99.0), 1)
                fc   = round(random.uniform(151.0, 180.0), 1)
                logger.info("[SIMULATION] Cas critique — tachycardie")
 
            else:  # bradycardie
                spo2 = round(random.uniform(94.0, 99.0), 1)
                fc   = round(random.uniform(25.0, 39.9), 1)
                logger.info("[SIMULATION] Cas critique — bradycardie")
        else:
            # Valeurs normales
            spo2 = round(random.uniform(95.0, 100.0), 1)
            fc   = round(random.uniform(60.0, 100.0), 1)
 
        return {
            "spo2": spo2,
            "frequence_cardiaque": fc,
            "patient_id": self.patient_id_courant
        }
 
    # -------------------------------------------------------------------------
    # LECTURE RÉELLE — Mode Raspberry Pi
    # Lit le MAX30100 via I2C et convertit les valeurs brutes
    # -------------------------------------------------------------------------
 
    def _lire_capteur_reel(self) -> Optional[Dict]:
        """
        Lit le MAX30100 physique via I2C.
        Convertit les valeurs brutes des registres en SpO2 et FC lisibles.
        """
        registres = self.reader.lire_registres()
 
        if not registres:
            return None
 
        # Conversion des valeurs brutes en valeurs médicales
        # Le MAX30100 renvoie des valeurs sur 8 bits (0-255)
        # On les normalise dans les plages médicales réelles
        spo2 = round((registres["spo2_raw"] / 255.0) * 30.0 + 70.0, 1)
        fc   = round((registres["hr_raw"]   / 255.0) * 190.0 + 30.0, 1)
 
        return {
            "spo2": spo2,
            "frequence_cardiaque": fc,
            "patient_id": self.patient_id_courant
        }
 
    # -------------------------------------------------------------------------
    # POINT D'ENTRÉE PRINCIPAL
    # Appelé par daemon.py à chaque cycle de la boucle principale
    # -------------------------------------------------------------------------
 
    def lire_mesures(self) -> Optional[Dict]:
        """
        Retourne les mesures biométriques actuelles du capteur.
        En simulation : valeurs générées aléatoirement.
        En production : valeurs lues depuis le MAX30100 via I2C.
 
        Retourne un dictionnaire :
        {
            "spo2": float,               # Saturation en oxygène (%)
            "frequence_cardiaque": float, # Fréquence cardiaque (bpm)
            "patient_id": str | None      # ID du patient courant
        }
        Retourne None si la lecture échoue ou si les valeurs sont aberrantes.
        """
        if MODE_SIMULATION:
            mesures = self._lire_simulation()
        else:
            mesures = self._lire_capteur_reel()
 
        if not mesures:
            return None
 
        # Validation des valeurs avant de les retourner
        if not self._valeur_valide(mesures["spo2"], mesures["frequence_cardiaque"]):
            return None
 
        logger.debug("Lecture — SpO2: %.1f%% | FC: %.0f bpm",
                    mesures["spo2"], mesures["frequence_cardiaque"])
 
        return mesures
 
 
# =============================================================================
# TEST STANDALONE
# Lance une série de lectures pour vérifier que le capteur fonctionne
# =============================================================================
 
if __name__ == "__main__":
    logger.info("Test du SensorManager — 10 lectures espacées de 2 secondes")
    sensor = SensorManager()
 
    for i in range(10):
        mesures = sensor.lire_mesures()
        if mesures:
            print(f"Lecture {i+1:02d} — SpO2: {mesures['spo2']}% | FC: {mesures['frequence_cardiaque']} bpm")
        else:
            print(f"Lecture {i+1:02d} — Échec de lecture")
        time.sleep(2)
 