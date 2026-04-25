"""
capteurs_raspberry.py — Lecture des capteurs biomédicaux pour HealthGate
Projet HealthGate | Centrale Casablanca | PLBD 4 | 2025-2026

Capteurs utilisés :
  - DS18B20      → Température corporelle (GPIO / 1-Wire)
  - MAX30102     → SpO2 + fréquence cardiaque (I2C)
  - Tensiomètre  → Tension artérielle (UART ou I2C selon modèle)

Sur PC (dev/test) : mode simulation automatique si RPi non détecté.
Sur Raspberry Pi  : lecture réelle des capteurs.

Câblage conseillé :
  DS18B20  → GPIO 4  (1-Wire, résistance pull-up 4.7kΩ requise)
  MAX30102 → SDA=GPIO2, SCL=GPIO3 (I2C bus 1)
  Tensiomètre UART → TX=GPIO14, RX=GPIO15
"""

import time
import random

# Détection automatique Raspberry Pi
try:
    import RPi.GPIO as GPIO
    SUR_RASPBERRY = True
except ImportError:
    SUR_RASPBERRY = False

# Librairies capteurs (installées uniquement sur le Pi)
if SUR_RASPBERRY:
    try:
        import w1thermsensor          # DS18B20
        TEMP_DISPONIBLE = True
    except ImportError:
        TEMP_DISPONIBLE = False

    try:
        from max30102 import MAX30102  # SpO2 / FC
        import hrcalc
        SPO2_DISPONIBLE = True
    except ImportError:
        SPO2_DISPONIBLE = False
else:
    TEMP_DISPONIBLE = False
    SPO2_DISPONIBLE = False


# ─────────────────────────────────────────────────────────────────────────────
# Lecture Température (DS18B20)
# ─────────────────────────────────────────────────────────────────────────────

def lire_temperature() -> dict:
    """
    Lit la température corporelle via le capteur DS18B20.

    Retourne
    --------
    dict : { valeur (float °C), capteur, succes, message }
    """
    if not SUR_RASPBERRY or not TEMP_DISPONIBLE:
        # Simulation réaliste
        temp = round(random.gauss(37.0, 0.8), 1)
        temp = max(35.0, min(42.0, temp))
        return {
            "valeur":   temp,
            "capteur":  "DS18B20 (simulé)",
            "succes":   True,
            "message":  "Simulation",
        }

    try:
        capteur = w1thermsensor.W1ThermSensor()
        # Moyenne sur 3 lectures pour plus de précision
        lectures = []
        for _ in range(3):
            lectures.append(capteur.get_temperature())
            time.sleep(0.1)

        temperature = round(sum(lectures) / len(lectures), 1)

        return {
            "valeur":  temperature,
            "capteur": "DS18B20",
            "succes":  True,
            "message": "Lecture réussie",
        }

    except Exception as e:
        return {
            "valeur":  37.0,
            "capteur": "DS18B20",
            "succes":  False,
            "message": f"Erreur capteur température : {str(e)}",
        }


# ─────────────────────────────────────────────────────────────────────────────
# Lecture SpO2 et fréquence cardiaque (MAX30102)
# ─────────────────────────────────────────────────────────────────────────────

def lire_spo2_fc() -> dict:
    """
    Lit le taux d'oxygène (SpO2) et la fréquence cardiaque via MAX30102.

    Le patient doit garder le doigt immobile pendant ~5 secondes.

    Retourne
    --------
    dict : { spo2 (float %), fc (int bpm), capteur, succes, message }
    """
    if not SUR_RASPBERRY or not SPO2_DISPONIBLE:
        # Simulation réaliste
        spo2 = round(random.gauss(97.0, 1.5), 1)
        spo2 = max(85.0, min(100.0, spo2))
        fc   = int(random.gauss(75, 12))
        fc   = max(45, min(150, fc))
        return {
            "spo2":    spo2,
            "fc":      fc,
            "capteur": "MAX30102 (simulé)",
            "succes":  True,
            "message": "Simulation",
        }

    try:
        capteur = MAX30102()
        capteur.setup_sensor()

        # Collecter 500 échantillons (~5 secondes à 100Hz)
        rouge, infrarouge = [], []
        for _ in range(500):
            capteur.check()
            if capteur.available():
                rouge.append(capteur.pop_red_from_storage())
                infrarouge.append(capteur.pop_ir_from_storage())
            time.sleep(0.01)

        # Calcul SpO2 et FC
        if len(rouge) >= 100:
            valide, spo2, _, fc = hrcalc.calc_hr_and_spo2(
                infrarouge[:100], rouge[:100]
            )
            if valide and 50 < spo2 <= 100 and 30 < fc < 200:
                return {
                    "spo2":    round(float(spo2), 1),
                    "fc":      int(fc),
                    "capteur": "MAX30102",
                    "succes":  True,
                    "message": "Lecture réussie",
                }

        return {
            "spo2":    98.0,
            "fc":      75,
            "capteur": "MAX30102",
            "succes":  False,
            "message": "Signal insuffisant — replacez le doigt",
        }

    except Exception as e:
        return {
            "spo2":    98.0,
            "fc":      75,
            "capteur": "MAX30102",
            "succes":  False,
            "message": f"Erreur SpO2 : {str(e)}",
        }


# ─────────────────────────────────────────────────────────────────────────────
# Lecture Tension artérielle
# ─────────────────────────────────────────────────────────────────────────────

def lire_tension() -> dict:
    """
    Lit la tension artérielle.

    Note : la plupart des tensiomètres grand public communiquent via UART
    ou Bluetooth. Cette fonction gère le protocole UART série.
    À adapter selon votre modèle exact.

    Retourne
    --------
    dict : { systolique (int), diastolique (int), capteur, succes, message }
    """
    if not SUR_RASPBERRY:
        # Simulation réaliste
        sys  = int(random.gauss(120, 15))
        sys  = max(80, min(200, sys))
        dias = int(sys * random.uniform(0.55, 0.68))
        return {
            "systolique":  sys,
            "diastolique": dias,
            "capteur":     "Tensiomètre UART (simulé)",
            "succes":      True,
            "message":     "Simulation",
        }

    # ── Lecture UART (à adapter selon votre tensiomètre) ──────────
    try:
        import serial

        # Configuration UART — adapter le port selon votre Pi
        # Pi 4/5 : /dev/ttyAMA0 ou /dev/ttyUSB0 (si adaptateur USB)
        port  = "/dev/ttyUSB0"
        baud  = 9600

        with serial.Serial(port, baud, timeout=30) as ser:
            # Déclencher la mesure (commande spécifique à votre modèle)
            # Exemple générique — consultez la datasheet de votre tensiomètre
            ser.write(b'\x52')   # commande "mesure" souvent 0x52 ou 0x53

            # Attendre la réponse (peut prendre 30s pour une mesure complète)
            donnees = ser.read(10)

            if len(donnees) >= 4:
                # Décoder selon le protocole de votre tensiomètre
                # Format typique : [START][SYS_H][SYS_L][DIAS_H][DIAS_L][...]
                systolique  = (donnees[1] << 8) | donnees[2]
                diastolique = (donnees[3] << 8) | donnees[4]

                if 60 < systolique < 250 and 40 < diastolique < 150:
                    return {
                        "systolique":  systolique,
                        "diastolique": diastolique,
                        "capteur":     "Tensiomètre UART",
                        "succes":      True,
                        "message":     "Lecture réussie",
                    }

        return {
            "systolique":  120,
            "diastolique": 80,
            "capteur":     "Tensiomètre UART",
            "succes":      False,
            "message":     "Données invalides reçues",
        }

    except Exception as e:
        return {
            "systolique":  120,
            "diastolique": 80,
            "capteur":     "Tensiomètre",
            "succes":      False,
            "message":     f"Erreur tension : {str(e)}",
        }


# ─────────────────────────────────────────────────────────────────────────────
# Lecture complète de toutes les constantes
# ─────────────────────────────────────────────────────────────────────────────

def lire_toutes_constantes() -> dict:
    """
    Lit les 3 constantes vitales en parallèle et retourne un résultat unifié.
    Appel principal depuis predict_api.py

    Retourne
    --------
    dict avec : temperature, spo2, heart_rate, bp_systolic, bp_diastolic,
                statut_capteurs, succes_global
    """
    print("[CAPTEURS] Lecture en cours...")

    # Lecture séquentielle (parallèle possible avec threading si besoin)
    res_temp    = lire_temperature()
    res_spo2    = lire_spo2_fc()
    res_tension = lire_tension()

    succes_global = res_temp["succes"] and res_spo2["succes"] and res_tension["succes"]

    constantes = {
        "temperature":   res_temp["valeur"],
        "spo2":          res_spo2["spo2"],
        "heart_rate":    res_spo2["fc"],
        "bp_systolic":   res_tension["systolique"],
        "bp_diastolic":  res_tension["diastolique"],
        "succes_global": succes_global,
        "statut_capteurs": {
            "temperature": {
                "valeur":  res_temp["valeur"],
                "capteur": res_temp["capteur"],
                "succes":  res_temp["succes"],
                "message": res_temp["message"],
            },
            "spo2_fc": {
                "spo2":    res_spo2["spo2"],
                "fc":      res_spo2["fc"],
                "capteur": res_spo2["capteur"],
                "succes":  res_spo2["succes"],
                "message": res_spo2["message"],
            },
            "tension": {
                "systolique":  res_tension["systolique"],
                "diastolique": res_tension["diastolique"],
                "capteur":     res_tension["capteur"],
                "succes":      res_tension["succes"],
                "message":     res_tension["message"],
            },
        }
    }

    print(f"[CAPTEURS] Température  : {constantes['temperature']}°C  ({res_temp['capteur']})")
    print(f"[CAPTEURS] SpO2         : {constantes['spo2']}%  ({res_spo2['capteur']})")
    print(f"[CAPTEURS] Fréq. card.  : {constantes['heart_rate']} bpm")
    print(f"[CAPTEURS] Tension      : {constantes['bp_systolic']}/{constantes['bp_diastolic']} mmHg")

    return constantes


# ─────────────────────────────────────────────────────────────────────────────
# Test en ligne de commande
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("TEST DES CAPTEURS — HealthGate")
    print(f"Mode : {'Raspberry Pi réel' if SUR_RASPBERRY else 'Simulation PC'}")
    print("=" * 50)

    constantes = lire_toutes_constantes()

    print("\n=== CONSTANTES VITALES ===")
    print(f"  Température  : {constantes['temperature']} °C")
    print(f"  SpO2         : {constantes['spo2']} %")
    print(f"  Fréq. card.  : {constantes['heart_rate']} bpm")
    print(f"  Tension      : {constantes['bp_systolic']}/{constantes['bp_diastolic']} mmHg")
    print(f"  Succès global: {constantes['succes_global']}")
