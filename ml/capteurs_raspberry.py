"""
capteurs_raspberry.py — Lecture des capteurs biomédicaux pour HealthGate
Projet HealthGate | Centrale Casablanca | PLBD 4 | 2025-2026

Architecture (mode commande) :
  - L'Arduino (USB) est démarré UNIQUEMENT quand le patient arrive sur l'étape Constantes.
  - Le Pi envoie une commande série ("MESURE:temperature" ou "MESURE:spo2"),
    l'Arduino mesure et répond UNE FOIS avec un JSON, puis se rendort.
  - La tension artérielle est toujours simulée (pas de tensiomètre connecté).
  - Si l'Arduino est absent ou ne répond pas → simulation complète.

API publique :
  demarrer_arduino() → bool        : ouvre le port série (appelé au mount de ConstantesPage)
  arreter_arduino()                 : ferme le port série (appelé au unmount)
  mesurer_capteur(type) → dict      : envoie commande, lit réponse JSON
  lire_toutes_constantes() → dict   : fallback séquentiel (utilisé par api_triage)
"""

import json
import random
import threading
import time

# ── Ports série candidats (Linux / Raspberry Pi OS) ──────────────────────────
PORTS_CANDIDATS = [
    "/dev/ttyACM0",   # Arduino Uno/Nano sur USB natif (priorité)
    "/dev/ttyACM1",
    "/dev/ttyUSB0",   # Convertisseur USB-série
    "/dev/ttyUSB1",
]
BAUDRATE_ARDUINO = 9600
TIMEOUT_MESURE   = 10    # secondes max pour recevoir la réponse de l'Arduino

# ── État partagé ─────────────────────────────────────────────────────────────
_verrou: threading.Lock = threading.Lock()
_port_serie = None       # serial.Serial | None  (None = Arduino non connecté)


# ─────────────────────────────────────────────────────────────────────────────
# Démarrage / arrêt du port série
# ─────────────────────────────────────────────────────────────────────────────

def demarrer_arduino() -> bool:
    """
    Détecte et ouvre le port série de l'Arduino.
    Appelé quand le patient arrive sur l'étape Constantes (GET /api/constantes/start).
    Retourne True si la connexion est établie, False sinon.
    """
    global _port_serie

    with _verrou:
        # Déjà ouvert → rien à faire
        if _port_serie is not None and _port_serie.is_open:
            print("[ARDUINO] Port serie deja ouvert")
            return True

        try:
            import serial
        except ImportError:
            print("[ARDUINO] pyserial non installe (pip install pyserial)")
            return False

        for port in PORTS_CANDIDATS:
            try:
                ser = serial.Serial(port, BAUDRATE_ARDUINO, timeout=2)
                # Attendre la fin du reset Arduino (ouverture USB déclenche un reset)
                time.sleep(1.5)
                ser.reset_input_buffer()

                # Attendre confirmation "Pret" de l'Arduino (timeout 5s)
                deadline = time.time() + 5.0
                pret = False
                while time.time() < deadline:
                    ligne = ser.readline().decode("utf-8", errors="ignore").strip()
                    if ligne:
                        print(f"[ARDUINO] {ligne}")
                    if "Pret" in ligne or "pret" in ligne.lower():
                        pret = True
                        break

                if not pret:
                    print(f"[ARDUINO] Pas de confirmation 'Pret' sur {port}, abandon")
                    ser.close()
                    continue

                ser.timeout = TIMEOUT_MESURE
                _port_serie = ser
                print(f"[ARDUINO] Connecte et pret sur {port}")
                return True
            except Exception as e:
                print(f"[ARDUINO] Port {port} inaccessible : {e}")

        print("[ARDUINO] Aucun port disponible → simulation")
        return False


def arreter_arduino() -> None:
    """
    Envoie MESURE:stop puis ferme le port série.
    Appelé quand le patient quitte l'étape Constantes (GET /api/constantes/stop).
    """
    global _port_serie

    with _verrou:
        if _port_serie is not None and _port_serie.is_open:
            try:
                _port_serie.write(b"MESURE:stop\n")
                time.sleep(0.1)
            except Exception:
                pass
            try:
                _port_serie.close()
            except Exception:
                pass
            print("[ARDUINO] Port serie ferme")
        _port_serie = None


# ─────────────────────────────────────────────────────────────────────────────
# Mesure sur commande
# ─────────────────────────────────────────────────────────────────────────────

def mesurer_capteur(type_mesure: str) -> dict:
    """
    Envoie une commande à l'Arduino et attend la réponse JSON (bloquant).

    Paramètre
    ---------
    type_mesure : "temperature" | "spo2"

    Retourne
    --------
    dict avec les valeurs mesurées + "source": "capteur"|"simulation"|"erreur"
    """
    if not _verrou.acquire(timeout=5):
        print(f"[ARDUINO] Verrou occupé (mesure parallèle ?) → simulation ({type_mesure})")
        return _simuler_mesure(type_mesure)
    try:
        if _port_serie is None or not _port_serie.is_open:
            print(f"[ARDUINO] Port non ouvert → simulation ({type_mesure})")
            return _simuler_mesure(type_mesure)

        _port_serie.reset_input_buffer()
        commande = f"MESURE:{type_mesure}\n".encode()
        _port_serie.write(commande)
        print(f"[ARDUINO] Commande → MESURE:{type_mesure}")

        # Attente de la réponse JSON (timeout = TIMEOUT_MESURE)
        deadline = time.time() + TIMEOUT_MESURE
        while time.time() < deadline:
            ligne = _port_serie.readline().decode("utf-8", errors="ignore").strip()
            if not ligne:
                continue
            if ligne.startswith("{"):
                try:
                    data = json.loads(ligne)
                    print(f"[ARDUINO] Reponse : {data}")
                    return data
                except json.JSONDecodeError:
                    continue
            # Ignorer les lignes de debug Arduino ("[ARDUINO] ...")

        print(f"[ARDUINO] Timeout ({TIMEOUT_MESURE}s) pour {type_mesure} → simulation")
        return _simuler_mesure(type_mesure)

    except Exception as e:
        print(f"[ARDUINO] Erreur serie ({type_mesure}) : {e}")
        return _simuler_mesure(type_mesure)
    finally:
        _verrou.release()


# ─────────────────────────────────────────────────────────────────────────────
# Simulations de repli
# ─────────────────────────────────────────────────────────────────────────────

def _simuler_mesure(type_mesure: str) -> dict:
    """Génère une mesure simulée réaliste pour le type demandé."""
    if type_mesure == "temperature":
        temp = round(random.gauss(37.0, 0.8), 1)
        temp = max(35.0, min(42.0, temp))
        return {"temperature": temp, "source": "simulation"}

    if type_mesure == "spo2":
        spo2 = round(random.gauss(97.0, 1.5), 1)
        spo2 = max(85.0, min(100.0, spo2))
        fc   = int(random.gauss(75, 12))
        fc   = max(45, min(150, fc))
        return {"spo2": spo2, "heart_rate": fc, "source": "simulation"}

    return {"source": "simulation"}


def _simuler_tension() -> dict:
    """Génère une tension artérielle simulée avec distribution réaliste."""
    sys  = int(random.gauss(120, 15))
    sys  = max(80, min(200, sys))
    dias = int(sys * random.uniform(0.55, 0.68))
    return {"bp_systolic": sys, "bp_diastolic": dias, "source": "simulation"}


# ─────────────────────────────────────────────────────────────────────────────
# Lecture complète — fallback pour api_triage (si constantes pas en session)
# ─────────────────────────────────────────────────────────────────────────────

def lire_toutes_constantes() -> dict:
    """
    Lit toutes les constantes vitales séquentiellement.
    Utilisé uniquement comme fallback depuis api_triage() si l'étape Constantes
    a été ignorée ou si la session ne contient pas encore les constantes.
    """
    print("[CAPTEURS] Lecture sequentielle de toutes les constantes...")

    temp_data = mesurer_capteur("temperature")
    spo2_data = mesurer_capteur("spo2")
    tension   = _simuler_tension()

    temperature = temp_data.get("temperature")
    spo2        = spo2_data.get("spo2")
    heart_rate  = spo2_data.get("heart_rate")

    # Repli simulation si valeur nulle ou source erreur
    temp_ok = temperature is not None and temp_data.get("source") != "erreur"
    spo2_ok = spo2 is not None and spo2_data.get("source") != "erreur"
    fc_ok   = heart_rate is not None and spo2_data.get("source") != "erreur"

    if not temp_ok:
        temperature = round(random.gauss(37.0, 0.8), 1)
        temperature = max(35.0, min(42.0, temperature))
    if not spo2_ok:
        spo2 = round(random.gauss(97.0, 1.5), 1)
        spo2 = max(85.0, min(100.0, spo2))
    if not fc_ok:
        heart_rate = int(random.gauss(75, 12))
        heart_rate = max(45, min(150, heart_rate))

    constantes = {
        "temperature":   round(float(temperature), 1),
        "spo2":          round(float(spo2), 1),
        "heart_rate":    int(heart_rate),
        "bp_systolic":   tension["bp_systolic"],
        "bp_diastolic":  tension["bp_diastolic"],
        "succes_global": True,
        "statut_capteurs": {
            "temperature": {"source": "capteur" if temp_ok else "simulation"},
            "spo2_fc":     {"source": "capteur" if (spo2_ok and fc_ok) else "simulation"},
            "tension":     {"source": "simulation"},
        },
    }

    print(f"[CAPTEURS] Temperature : {constantes['temperature']}°C")
    print(f"[CAPTEURS] SpO2        : {constantes['spo2']}%")
    print(f"[CAPTEURS] Freq. card. : {constantes['heart_rate']} bpm")
    print(f"[CAPTEURS] Tension     : {constantes['bp_systolic']}/{constantes['bp_diastolic']} mmHg (sim)")

    return constantes


# ─────────────────────────────────────────────────────────────────────────────
# Test en ligne de commande
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("TEST DES CAPTEURS — HealthGate (mode commande)")
    print("=" * 50)

    print("\n[1] Démarrage Arduino...")
    ok = demarrer_arduino()
    print(f"    Connecte : {ok}")

    print("\n[2] Mesure température...")
    res = mesurer_capteur("temperature")
    print(f"    → {res}")

    print("\n[3] Mesure SpO2 + FC...")
    res = mesurer_capteur("spo2")
    print(f"    → {res}")

    print("\n[4] Arrêt Arduino...")
    arreter_arduino()
    print("    Arrete.")
