# HealthGate — Guide de déploiement sur Raspberry Pi

**Projet PLBD-4 | École Centrale Casablanca | 2025-2026**

---

## Architecture du système

```
┌─────────────────────────────────────────────────────┐
│                  Raspberry Pi                        │
│                                                     │
│  ┌──────────────────┐   ┌──────────────────────┐   │
│  │ Backend FastAPI   │   │  Frontend React       │   │
│  │ port 8000        │   │  port 5173            │   │
│  │ (uvicorn)        │◄──►│  (npm run preview)   │   │
│  └──────────────────┘   └──────────────────────┘   │
│           ▲                                         │
│           │ USB                                     │
│  ┌─────────────────┐                               │
│  │ Arduino Uno/Nano│                               │
│  │ MLX90614 (temp) │                               │
│  │ MAX30102 (SpO2) │                               │
│  └─────────────────┘                               │
└─────────────────────────────────────────────────────┘
         │ WiFi / Ethernet
         ▼
┌──────────────────────┐  ┌────────────────────────┐
│ Borne patient (kiosk)│  │ Tablette médecin        │
│ http://<IP>:5173/    │  │ http://<IP>:5173/       │
│                      │  │   medecin/M1            │
└──────────────────────┘  └────────────────────────┘
         │
┌──────────────────────┐
│ Écran salle d'attente│
│ http://<IP>:5173/    │
│   salle              │
└──────────────────────┘
```

---

## 1. Prérequis

### Matériel
- Raspberry Pi 4 (recommandé) ou Pi 3B+ minimum
- Carte SD 16 Go minimum (classe 10)
- Arduino Uno ou Nano avec câble USB
- Capteur MLX90614 GY-906 (température)
- Capteur MAX30102 (SpO2 + fréquence cardiaque)
- Écran tactile (pour la borne patient) ou connexion réseau

### Système
- **Raspberry Pi OS** (Bullseye ou Bookworm, 64-bit recommandé)
- Connexion internet lors de l'installation

---

## 2. Cloner le projet sur le Pi

### Option A — Depuis GitHub
```bash
cd /home/pi
git clone https://github.com/<votre-org>/PLBD-4.git
cd PLBD-4
```

### Option B — Copie depuis PC (via SSH)
```bash
# Sur votre PC :
scp -r ./PLBD-4 pi@<IP_PI>:/home/pi/PLBD-4
```

### Option C — Clé USB
```bash
# Sur le Pi, monter la clé USB puis copier :
cp -r /media/pi/USB/PLBD-4 /home/pi/PLBD-4
```

---

## 3. Brancher l'Arduino

### Câblage des capteurs sur l'Arduino (Uno / Nano)

```
MLX90614 GY-906           Arduino
────────────────          ───────
VCC  ─────────────────►  3.3V
GND  ─────────────────►  GND
SDA  ─────────────────►  A4
SCL  ─────────────────►  A5

MAX30102                  Arduino
────────────────          ───────
VCC  ─────────────────►  3.3V
GND  ─────────────────►  GND
SDA  ─────────────────►  A4
SCL  ─────────────────►  A5
```

> **Note :** SDA et SCL des deux capteurs se partagent le même bus I2C (A4/A5).

### Flasher le sketch Arduino
1. Ouvrir `arduino/capteurs.ino` dans l'IDE Arduino
2. Installer les bibliothèques (Gestionnaire de bibliothèques) :
   - `Adafruit MLX90614 Library`
   - `SparkFun MAX3010x Pulse and Proximity Sensor Library`
3. Sélectionner la bonne carte (Uno ou Nano) et le bon port COM
4. Téléverser le sketch
5. Brancher l'Arduino au Raspberry Pi via USB

### Vérifier la connexion série
```bash
# Lister les ports disponibles
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null

# Lire les données en temps réel (Ctrl+C pour quitter)
cat /dev/ttyUSB0   # ou ttyACM0

# La sortie doit ressembler à :
# {"temperature": 36.7, "spo2": 98, "heart_rate": 72, "source": "capteur"}
```

---

## 4. Installation et démarrage automatique

```bash
cd /home/pi/PLBD-4

# Rendre les scripts exécutables
chmod +x scripts/install_services.sh
chmod +x scripts/start_dev.sh

# Lancer l'installation (remplacer 192.168.1.100 par l'IP souhaitée)
sudo ./scripts/install_services.sh 192.168.1.100

# Pour une interface WiFi au lieu d'Ethernet :
sudo ./scripts/install_services.sh 192.168.1.100 wlan0
```

Le script fait automatiquement :
- Installation des dépendances Python dans un virtualenv (`.venv/`)
- Build du frontend React (`npm run build`)
- Installation des services systemd dans `/etc/systemd/system/`
- Activation au démarrage (`systemctl enable`)
- Configuration de l'IP fixe (détecte dhcpcd ou NetworkManager)
- Ajout de l'utilisateur `pi` au groupe `dialout` (accès Arduino)

---

## 5. Accès aux interfaces

Une fois installé, depuis n'importe quel appareil sur le réseau :

| Interface | URL | Utilisateur |
|-----------|-----|-------------|
| Borne patient (kiosk) | `http://192.168.1.100:5173/` | Patient |
| Salle d'attente | `http://192.168.1.100:5173/salle` | Écran public |
| Interface médecin M1 | `http://192.168.1.100:5173/medecin/M1` | Dr. Alami |
| Interface médecin M2 | `http://192.168.1.100:5173/medecin/M2` | Dr. Benali |
| API backend | `http://192.168.1.100:8000/api/health` | Debug |

---

## 6. Mode développement (sur PC ou Pi)

```bash
./scripts/start_dev.sh
```

Lance les deux serveurs en parallèle avec logs colorés :
- **Cyan** → logs FastAPI (backend)
- **Violet** → logs Vite (frontend, hot-reload)

`Ctrl+C` arrête les deux proprement.

---

## 7. Gestion des services

```bash
# Voir l'état des services
systemctl status plbd4-backend
systemctl status plbd4-frontend

# Redémarrer après une modification du code
systemctl restart plbd4-backend
systemctl restart plbd4-frontend

# Voir les logs en temps réel
journalctl -u plbd4-backend -f
journalctl -u plbd4-frontend -f

# Voir les 50 dernières lignes
journalctl -u plbd4-backend -n 50

# Désactiver le démarrage automatique
systemctl disable plbd4-backend plbd4-frontend
```

---

## 8. Mise à jour du projet

```bash
cd /home/pi/PLBD-4

# Récupérer les dernières modifications
git pull

# Reconstruire le frontend si les fichiers .jsx ont changé
cd frontend && npm run build && cd ..

# Redémarrer les services
sudo systemctl restart plbd4-backend plbd4-frontend
```

---

## 9. Dépannage

### Le backend ne démarre pas
```bash
journalctl -u plbd4-backend -n 30
# Vérifier que le .env est présent avec les clés API
cat /home/pi/PLBD-4/backend/.env
```

### L'Arduino n'est pas détecté
```bash
# Vérifier que l'utilisateur est dans le groupe dialout
groups pi

# Si non, ajouter et se reconnecter
sudo usermod -aG dialout pi
# Fermer puis rouvrir la session SSH

# Vérifier les permissions du port
ls -l /dev/ttyUSB0
```

### Le frontend affiche une page blanche
```bash
# Le build est peut-être absent ou obsolète
cd /home/pi/PLBD-4/frontend
npm run build
sudo systemctl restart plbd4-frontend
```

### Connaître l'IP actuelle du Pi
```bash
hostname -I
ip addr show eth0 | grep "inet "
ip addr show wlan0 | grep "inet "
```

---

## 10. Écran Nextion NX8048K070-011R

### Comprendre les deux composants d'affichage

Le Nextion NX8048K070-011R est un écran tactile **avec son propre microcontrôleur interne**.
Il communique uniquement via **UART (TTL série)** et **ne peut pas afficher de contenu web** (pas de signal HDMI/DSI/VGA).

Le système HealthGate utilise donc deux couches d'affichage distinctes :

| Composant | Interface | Ce qu'il affiche |
|-----------|-----------|-----------------|
| Sortie HDMI du Pi | HDMI → moniteur standard | Chromium kiosque → interface React complète |
| Nextion NX8048K070 | UART (/dev/ttyAMA0) | Affichage secondaire statique (nom patient, n° ticket, ESI) |

---

### Option A — Configuration recommandée : HDMI + Kiosque Chromium

Branchez un **moniteur HDMI 800×480** (ou tout moniteur standard) à la sortie HDMI du Pi.
Le script `launch_kiosk.sh` ouvre automatiquement Chromium sur http://localhost:5173 en plein écran.

```bash
# Tester manuellement le kiosque (session graphique active)
DISPLAY=:0 ./scripts/launch_kiosk.sh

# Voir les logs du kiosque
journalctl -u plbd4-kiosk -f

# Forcer la résolution 800x480 manuellement
DISPLAY=:0 xrandr --output HDMI-1 --mode 800x480
```

> **Auto-login requis** : le service `plbd4-kiosk` a besoin d'une session graphique active.
> `install_services.sh` configure l'auto-login via `raspi-config`.
> Si ce n'est pas fait automatiquement : `sudo raspi-config` → System Options → Boot → Desktop Autologin.

---

### Option B — Câblage du Nextion au Raspberry Pi (affichage secondaire)

Le Nextion se branche sur le port UART du Pi via des câbles Dupont (TTL 3.3V).

```
Nextion NX8048K070          Raspberry Pi (GPIO)
──────────────────          ───────────────────────────────
TX  ─────────────────────►  Pin 10 (GPIO15 / UART RX)
RX  ◄─────────────────────  Pin  8 (GPIO14 / UART TX)
GND ─────────────────────►  Pin  6 (GND)
VCC ─────────────────────►  Alimentation 5V EXTERNE (*)
```

> **(*) IMPORTANT** : Le Nextion 7" consomme jusqu'à 2A en pointe. N'alimentez JAMAIS via les 5V du Pi
> (pin 2 ou 4) — vous risquez de faire tomber le Pi ou d'endommager les deux cartes.
> Utilisez une alimentation 5V / 2A dédiée branchée directement sur le connecteur du Nextion.

---

### Activer le port UART sur le Raspberry Pi

Par défaut, le port série est utilisé par la console système sur le Pi. Il faut le libérer :

```bash
sudo raspi-config
# → Interface Options → Serial Port
#   "Would you like a login shell to be accessible over serial?" → Non
#   "Would you like the serial port hardware to be enabled?"     → Oui
sudo reboot
```

Vérification après reboot :

```bash
# Le port UART hardware doit être visible
ls /dev/ttyAMA0   # Pi 3/4/5
ls /dev/serial0   # alias générique

# Tester l'envoi d'une commande Nextion (protocole propriétaire)
# Chaque commande se termine par 3 octets 0xFF
python3 -c "
import serial, time
s = serial.Serial('/dev/ttyAMA0', 9600, timeout=1)
s.write(b't0.txt=\"HealthGate\"\xff\xff\xff')  # changer le texte du composant t0
time.sleep(0.1)
print('Recu:', s.read(10))
s.close()
"
```

---

### Programmer le Nextion (affichage secondaire)

Pour afficher du contenu sur le Nextion, vous devez créer une interface dans **Nextion Editor**
(Windows, gratuit) puis la flasher via carte microSD ou UART.

Ressources :
- Nextion Editor : https://nextion.tech/nextion-editor/
- Guide du protocole : https://nextion.tech/instruction-set/
- Bibliothèque Python : `pip install pyserial` (communication UART)

> L'intégration du Nextion comme affichage secondaire (n° de ticket, ESI, nom patient)
> est une évolution future du projet — elle nécessite un fichier `.HMI` dédié
> et un thread Python dans `backend/main.py` qui envoie les mises à jour via UART.

---

## 11. Structure des fichiers de déploiement

```
PLBD-4/
├── arduino/
│   └── capteurs.ino              # Sketch Arduino (MLX90614 + MAX30102)
├── systemd/
│   ├── plbd4-backend.service      # Service systemd backend FastAPI
│   ├── plbd4-frontend.service     # Service systemd frontend React
│   └── plbd4-kiosk.service        # Service systemd kiosque Chromium
├── scripts/
│   ├── install_services.sh        # Installation complète sur le Pi
│   ├── launch_kiosk.sh            # Lancement Chromium 800x480 (kiosque)
│   └── start_dev.sh               # Lancement rapide en développement
└── README_DEPLOY.md               # Ce fichier
```
