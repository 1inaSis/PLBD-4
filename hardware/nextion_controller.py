"""
=============================================================================
HEALTH GATE — nextion_controller.py
=============================================================================
 
RÔLE DE CE MODULE
-----------------
Ce fichier gère toute la communication entre le Raspberry Pi et l'écran
Nextion 7 pouces via le protocole Serial (UART). Il est le seul fichier
du projet qui parle à l'écran. Les autres fichiers (daemon.py) lui donnent
des instructions de haut niveau comme "affiche le résultat du triage" sans
savoir comment le protocole Nextion fonctionne.
 
COMPOSANTS PRINCIPAUX
----------------------
 
1. PROTOCOLE NEXTION — UART SERIAL
   Le Nextion communique via un port série (UART) à 9600 bauds.
   Chaque commande envoyée doit se terminer par 3 octets 0xFF.
   Exemple : 't0.txt="Bonjour"\xFF\xFF\xFF'
   Sans ces 3 octets, le Nextion ignore la commande.
 
2. ENUM PageNextion
   Liste toutes les pages de l'interface Nextion.
   L'écran Nextion fonctionne par pages — comme des slides PowerPoint.
   Chaque page a un numéro et un rôle précis.
 
3. ENUM NiveauTriage
   Les 5 niveaux du Manchester Triage System avec leurs couleurs.
   Ces couleurs sont affichées sur l'écran Nextion pour indiquer
   la gravité au patient.
 
4. CLASSE NextionController
   Le cerveau du module. Contient toutes les méthodes d'affichage :
   - afficher_accueil()         : écran de bienvenue en attente
   - afficher_scan_document()   : invite à poser la CIN
   - afficher_mesure_capteur()  : invite à poser le doigt
   - afficher_questionnaire()   : pendant que le patient répond
   - afficher_resultat_triage() : résultat final avec numéro et niveau
   - afficher_erreur()          : message d'erreur lisible
 
5. MODE SIMULATION
   Sur Mac, le port série n'existe pas. Le mode simulation affiche
   les commandes dans le terminal au lieu de les envoyer à l'écran.
 
PROTOCOLE NEXTION — DÉTAILS TECHNIQUES
----------------------------------------
- Communication : UART Serial
- Baudrate      : 9600 bps
- Terminaison   : 3 octets 0xFF après chaque commande
- Composants    : nommés dans Nextion Editor (t0, b0, p0...)
  t0 = TextBox numéro 0
  b0 = Button numéro 0
  p0 = Picture numéro 0
- Changement de page : commande "page N" où N est le numéro de page
 
DÉPENDANCES
-----------
- serial  : communication UART avec l'écran Nextion
- logging : traçabilité des commandes envoyées
 
=============================================================================
"""
 
import time
import logging
from enum import Enum
from typing import Optional
 
# =============================================================================
# CONFIGURATION LOGGING
# =============================================================================
 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("nextion.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
 
 
# =============================================================================
# DÉTECTION DE L'ENVIRONNEMENT
# Sur Mac le port série n'existe pas → mode simulation automatique
# =============================================================================
 
MODE_SIMULATION = False
 
try:
    import serial
    logger.info("Bibliothèque serial disponible — mode matériel activé")
except ImportError:
    MODE_SIMULATION = True
    logger.warning("pyserial non disponible — mode simulation activé")
 
 
# =============================================================================
# CONSTANTES — CONFIGURATION SERIAL
# =============================================================================
 
# Port série du Raspberry Pi connecté au Nextion
NEXTION_PORT     = "/dev/ttyS0"
NEXTION_BAUDRATE = 9600
 
# Terminaison obligatoire après chaque commande Nextion
# Sans ces 3 octets, l'écran ignore la commande
NEXTION_FIN_COMMANDE = b'\xFF\xFF\xFF'
 
# Délai entre deux commandes successives (en secondes)
DELAI_COMMANDE = 0.05
 
 
# =============================================================================
# ENUM — PAGES DE L'INTERFACE NEXTION
# =============================================================================
 
class PageNextion(Enum):
    ACCUEIL          = 0
    SCAN_DOCUMENT    = 1
    MESURE_CAPTEUR   = 2
    STABILISATION    = 3
    QUESTIONNAIRE    = 4
    RESULTAT_TRIAGE  = 5
    ERREUR           = 6
 
 
# =============================================================================
# ENUM — NIVEAUX DE TRIAGE MANCHESTER
# =============================================================================
 
class NiveauTriage(Enum):
    NIVEAU_1 = ("1", "IMMEDIAT",    "RED",    63488)
    NIVEAU_2 = ("2", "TRES URGENT", "ORANGE", 64512)
    NIVEAU_3 = ("3", "URGENT",      "YELLOW", 65504)
    NIVEAU_4 = ("4", "STANDARD",    "GREEN",  2016)
    NIVEAU_5 = ("5", "NON URGENT",  "BLUE",   31)
 
    def __init__(self, numero, libelle, couleur_nom, couleur_nextion):
        self.numero          = numero
        self.libelle         = libelle
        self.couleur_nom     = couleur_nom
        self.couleur_nextion = couleur_nextion
 
 
# =============================================================================
# CLASSE PRINCIPALE — NextionController
# =============================================================================
 
class NextionController:
 
    def __init__(self):
        self.connecte = False
        self.page_courante = PageNextion.ACCUEIL
        self._initialiser_connexion()
 
    # -------------------------------------------------------------------------
    # INITIALISATION DE LA CONNEXION SÉRIE
    # -------------------------------------------------------------------------
 
    def _initialiser_connexion(self):
        """
        Ouvre la connexion série avec l'écran Nextion.
        En mode simulation, aucune connexion réelle n'est établie.
        """
        if MODE_SIMULATION:
            self.port = None
            self.connecte = True
            logger.info("NextionController démarré en mode simulation")
            return
 
        try:
            self.port = serial.Serial(
                port=NEXTION_PORT,
                baudrate=NEXTION_BAUDRATE,
                timeout=1
            )
            self.connecte = True
            logger.info("Écran Nextion connecté sur %s à %d bauds",
                       NEXTION_PORT, NEXTION_BAUDRATE)
        except serial.SerialException as e:
            self.connecte = False
            logger.error("Impossible de connecter le Nextion : %s", e)
 
    # -------------------------------------------------------------------------
    # ENVOI D'UNE COMMANDE BRUTE
    # -------------------------------------------------------------------------
 
    def _envoyer_commande(self, commande: str):
        """
        Envoie une commande au Nextion via Serial.
        Ajoute automatiquement les 3 octets 0xFF de terminaison.
        En simulation, affiche la commande dans le terminal.
        """
        commande_complete = commande.encode("utf-8") + NEXTION_FIN_COMMANDE
 
        if MODE_SIMULATION:
            logger.info("[SIMULATION NEXTION] → %s", commande)
            return
 
        if not self.connecte:
            logger.warning("Nextion non connecté — commande ignorée : %s", commande)
            return
 
        try:
            self.port.write(commande_complete)
            time.sleep(DELAI_COMMANDE)
        except Exception as e:
            logger.error("Erreur d'envoi Nextion : %s", e)
 
    # -------------------------------------------------------------------------
    # CHANGEMENT DE PAGE
    # -------------------------------------------------------------------------
 
    def _aller_page(self, page: PageNextion):
        """
        Change la page affichée sur l'écran Nextion.
        Équivalent de changer de slide dans PowerPoint.
        """
        self._envoyer_commande(f"page {page.value}")
        self.page_courante = page
        logger.info("Nextion → page %s (%d)", page.name, page.value)
 
    # -------------------------------------------------------------------------
    # MISE À JOUR D'UN COMPOSANT TEXTE
    # -------------------------------------------------------------------------
 
    def _set_texte(self, composant: str, texte: str):
        """
        Met à jour le texte d'un composant TextBox sur la page courante.
        composant : nom du composant dans Nextion Editor (ex: "t0", "t1")
        texte     : texte à afficher
        """
        texte_court = texte[:50]
        self._envoyer_commande(f'{composant}.txt="{texte_court}"')
 
    # -------------------------------------------------------------------------
    # MISE À JOUR D'UNE COULEUR DE FOND
    # -------------------------------------------------------------------------
 
    def _set_couleur_fond(self, composant: str, couleur: int):
        """
        Change la couleur de fond d'un composant.
        couleur : valeur RGB565 (format Nextion)
        """
        self._envoyer_commande(f"{composant}.bco={couleur}")
 
    # =========================================================================
    # MÉTHODES PUBLIQUES — APPELÉES PAR daemon.py
    # =========================================================================
 
    def afficher_accueil(self):
        """
        Affiche l'écran de bienvenue.
        Appelé au démarrage de la borne et entre chaque patient.
        """
        self._aller_page(PageNextion.ACCUEIL)
        self._set_texte("t0", "Bienvenue")
        self._set_texte("t1", "Approchez votre CIN de la zone de scan")
        logger.info("Écran accueil affiché")
 
    def afficher_scan_document(self):
        """
        Invite le patient à poser son document d'identité.
        """
        self._aller_page(PageNextion.SCAN_DOCUMENT)
        self._set_texte("t0", "Scan du document")
        self._set_texte("t1", "Posez votre CIN face visible")
        self._set_texte("t2", "ضع بطاقة التعريف الوطنية")
        logger.info("Écran scan document affiché")
 
    def afficher_mesure_capteur(self):
        """
        Invite le patient à poser son doigt sur le MAX30100.
        """
        self._aller_page(PageNextion.MESURE_CAPTEUR)
        self._set_texte("t0", "Mesure biométrique")
        self._set_texte("t1", "Posez votre doigt sur le capteur")
        self._set_texte("t2", "ضع إصبعك على المستشعر")
        logger.info("Écran mesure capteur affiché")
 
    def afficher_stabilisation(self, secondes_restantes: int):
        """
        Affiche la progression de la stabilisation (20 secondes).
        Appelé toutes les 2 secondes pendant la stabilisation.
        """
        self._aller_page(PageNextion.STABILISATION)
        self._set_texte("t0", "Mesure en cours...")
        self._set_texte("t1", f"Ne bougez pas — {secondes_restantes}s")
 
        # Barre de progression — composant j0 dans Nextion Editor
        # Valeur entre 0 et 100
        progression = int(((20 - secondes_restantes) / 20) * 100)
        self._envoyer_commande(f"j0.val={progression}")
 
        logger.info("Stabilisation — %ds restantes (%d%%)",
                   secondes_restantes, progression)
 
    def afficher_questionnaire(self):
        """
        Informe le patient de se tourner vers la tablette.
        Le questionnaire est géré par React.js sur la tablette.
        """
        self._aller_page(PageNextion.QUESTIONNAIRE)
        self._set_texte("t0", "Questionnaire médical")
        self._set_texte("t1", "Répondez aux questions sur la tablette")
        self._set_texte("t2", "أجب على الأسئلة على اللوحة")
        logger.info("Écran questionnaire affiché")
 
    def afficher_resultat_triage(self, numero_ticket: str, niveau: NiveauTriage,
                                  patient_nom: Optional[str] = None):
        """
        Affiche le résultat final du triage au patient.
        C'est l'écran le plus important de la session.
 
        numero_ticket : numéro attribué au patient (ex: "042")
        niveau        : niveau de priorité Manchester
        patient_nom   : prénom du patient si disponible
        """
        self._aller_page(PageNextion.RESULTAT_TRIAGE)
 
        self._set_texte("t0", f"Votre numéro : {numero_ticket}")
        self._set_texte("t1", f"Niveau {niveau.numero} — {niveau.libelle}")
 
        if patient_nom:
            self._set_texte("t2", f"Merci {patient_nom}, un soignant s'occupera de vous")
        else:
            self._set_texte("t2", "Un soignant s'occupera de vous sous peu")
 
        # Couleur de fond selon le niveau Manchester
        self._set_couleur_fond("p0", niveau.couleur_nextion)
 
        logger.info("Résultat triage — Ticket: %s | Niveau: %s",
                   numero_ticket, niveau.libelle)
 
    def afficher_erreur(self, message: str):
        """
        Affiche un message d'erreur lisible.
        Appelé si le scan échoue, si le capteur ne répond pas, etc.
        """
        self._aller_page(PageNextion.ERREUR)
        self._set_texte("t0", "Une erreur est survenue")
        self._set_texte("t1", message[:50])
        self._set_texte("t2", "Veuillez vous adresser à l'accueil")
        logger.warning("Écran erreur affiché : %s", message)
 
    def fermer(self):
        """Ferme proprement la connexion série."""
        if not MODE_SIMULATION and self.connecte and self.port:
            self.port.close()
            logger.info("Connexion Nextion fermée")
 
 
# =============================================================================
# TEST STANDALONE
# Simule une session complète dans le terminal
# =============================================================================
 
if __name__ == "__main__":
    logger.info("Test — simulation d'une session complète")
 
    nextion = NextionController()
 
    print("\n--- Simulation d'une session patient ---\n")
 
    nextion.afficher_accueil()
    time.sleep(1)
 
    nextion.afficher_scan_document()
    time.sleep(1)
 
    nextion.afficher_mesure_capteur()
    time.sleep(1)
 
    for secondes_restantes in [20, 18, 16, 14, 12, 10, 8, 6, 4, 2]:
        nextion.afficher_stabilisation(secondes_restantes)
        time.sleep(0.3)
 
    nextion.afficher_questionnaire()
    time.sleep(1)
 
    nextion.afficher_resultat_triage(
        numero_ticket="042",
        niveau=NiveauTriage.NIVEAU_2,
        patient_nom="Mohamed"
    )
    time.sleep(2)
 
    nextion.fermer()
    print("\n--- Fin de la simulation ---")
 