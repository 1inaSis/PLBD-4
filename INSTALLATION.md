# Guide d'installation HealthGate

> Guide complet pour installer et configurer le système HealthGate sur votre machine.

**Table des matières**
1. [Installation locale (développement)](#installation-locale)
2. [Installation Raspberry Pi](#installation-raspberry-pi)
3. [Déploiement production](#déploiement-production)
4. [Fichiers de configuration](#fichiers-de-configuration)

---

## Installation locale

### Pour Windows

#### 1. Installer Python 3.13+

```powershell
# Télécharger depuis https://www.python.org/
# OU via Chocolatey
choco install python

# Vérifier
python --version
```

#### 2. Installer Tesseract OCR

```powershell
# Via Chocolatey (recommandé)
choco install tesseract

# OU télécharger depuis
# https://github.com/UB-Mannheim/tesseract/wiki
# Pendant l'installation, cocher : French + Arabic
```

#### 3. Cloner le repository et se placer dans le dossier ML

```powershell
git clone https://github.com/username/PLBD-4.git
cd PLBD-4\ml
```

#### 4. Créer environnement virtuel

```powershell
python -m venv venv
venv\Scripts\activate
```

#### 5. Installer les dépendances

```powershell
pip install -r requirements.txt
```

#### 6. Configuration Tesseract (si besoin)

Éditer `scanner_cin.py` :
```python
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

#### 7. Vérifier l'installation

```powershell
# Importer tous les modules
python -c "import flask, pandas, numpy, sklearn, cv2, pytesseract; print('✓ Tous les modules OK')"
```

#### 8. Entraîner le modèle

```powershell
# Cela prend 2-3 minutes
python model_trainer.py

# Devrait créer :
# - models/random_forest_esi.pkl (5 MB)
# - models/scaler.pkl
# - models/feature_names.pkl
```

#### 9. Lancer le serveur

```powershell
python predict_api.py

# Sortie :
# * Running on http://0.0.0.0:5000
# * WARNING: This is a development server. ...
```

#### 10. Accéder aux interfaces

Ouvrir dans votre navigateur :
- Patient : http://localhost:5000/
- Salle attente : http://localhost:5000/salle
- Médecin 1 : http://localhost:5000/medecin/M1
- Médecin 2 : http://localhost:5000/medecin/M2

---

### Pour Mac

#### 1. Installer Homebrew (si pas déjà fait)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

#### 2. Installer Python et Tesseract

```bash
brew install python@3.13
brew install tesseract

# Vérifier
python3 --version
tesseract --version
```

#### 3-9. Mêmes étapes qu'Windows (remplacer `python` par `python3`)

```bash
git clone https://github.com/username/PLBD-4.git
cd PLBD-4/ml
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 model_trainer.py
python3 predict_api.py
```

---

### Pour Linux (Ubuntu/Debian)

```bash
# 1. Installer dépendances système
sudo apt update
sudo apt install python3.13 python3.13-venv python3-pip
sudo apt install tesseract-ocr libtesseract-dev

# 2-9. Mêmes commandes qu'Unix
git clone https://github.com/username/PLBD-4.git
cd PLBD-4/ml
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 model_trainer.py
python3 predict_api.py
```

---

## Installation Raspberry Pi 5

### Configuration du Raspberry Pi

#### 1. Flasher microSD (Raspberry Pi OS Bookworm 64-bit)

```bash
# Sur votre ordinateur :
# Télécharger Raspberry Pi Imager
# https://www.raspberrypi.com/software/

# Sélectionner :
# - Device: Raspberry Pi 5
# - OS: Raspberry Pi OS (64-bit) Bookworm
# - Storage: votre microSD
# - Clic "Next" → "Edit settings" → WiFi + SSH
```

#### 2. Première connexion

```bash
# SSH depuis votre PC
ssh pi@raspberrypi.local
# Mot de passe par défaut : raspberry

# Ou via IP
ssh pi@192.168.1.100  # Remplacer par votre IP
```

#### 3. Configuration système

```bash
# Mettre à jour
sudo apt update && sudo apt upgrade -y

# Installer Python et dépendances
sudo apt install python3.13 python3.13-venv python3-pip
sudo apt install tesseract-ocr libtesseract-dev
sudo apt install git

# Activer I2C et 1-Wire (pour capteurs)
sudo raspi-config
# → Interface Options → I2C → Enable
# → Interface Options → 1-Wire → Enable
# → Reboot
```

#### 4. Cloner et installer HealthGate

```bash
cd ~
git clone https://github.com/username/PLBD-4.git
cd PLBD-4/ml

python3 -m venv venv
source venv/bin/activate

# Installer dépendances RASPBERRY PI (ligne supplémentaire)
pip install -r requirements.txt
pip install RPi.GPIO w1thermsensor max30102 pyserial

# Entraîner modèle (optionnel si vous le copiez du PC)
python3 model_trainer.py
```

#### 5. Configuration capteurs

Éditer `capteurs_raspberry.py` et vérifier :
```python
# Line 8 - PIN 1-Wire pour température
TEMP_PIN = 4

# Line 10 - Adresse I2C pour SpO2
MAX30102_ADDRESS = 0x57

# Line 12 - Port UART pour tensiomètre
UART_PORT = "/dev/ttyUSB0"
```

#### 6. Lancer le serveur sur Pi

```bash
source venv/bin/activate
python3 predict_api.py

# Le serveur sera accessible depuis :
# http://<IP_RASPBERRY>:5000
```

#### 7. Créer un service Systemd (optionnel - pour auto-démarrage)

```bash
sudo nano /etc/systemd/system/healthgate.service
```

Copier ceci :
```ini
[Unit]
Description=HealthGate Medical Triage System
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/PLBD-4/ml
Environment="PATH=/home/pi/PLBD-4/ml/venv/bin"
ExecStart=/home/pi/PLBD-4/ml/venv/bin/python3 predict_api.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Puis :
```bash
sudo systemctl daemon-reload
sudo systemctl enable healthgate
sudo systemctl start healthgate
sudo systemctl status healthgate
```

---

## Déploiement production

### Via Docker (recommandé)

#### 1. Installer Docker

**Windows :** https://www.docker.com/products/docker-desktop  
**Mac :** https://www.docker.com/products/docker-desktop  
**Linux :**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

#### 2. Utiliser le docker-compose.yml

```bash
cd PLBD-4
docker-compose up -d
```

Cela démarre :
- Container Flask (port 5000)
- Container MongoDB (optionnel, stockage patient)
- Container Nginx (reverse proxy)

### Déploiement manuel

#### Configuration Nginx (reverse proxy)

```bash
sudo apt install nginx
sudo nano /etc/nginx/sites-available/healthgate
```

```nginx
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_request_buffering off;
    }

    location /socket.io {
        proxy_pass http://127.0.0.1:5000/socket.io;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/healthgate /etc/nginx/sites-enabled/
sudo systemctl restart nginx
```

---

## Fichiers de configuration

### .env (optionnel - créer dans le dossier `ml`)

```env
# Flask
FLASK_ENV=production
FLASK_DEBUG=False
SECRET_KEY=votre_clé_secrète_ici

# Base de données (si MongoDB)
MONGODB_URI=mongodb://localhost:27017/healthgate

# Tesseract
TESSERACT_PATH=/usr/bin/tesseract  # Linux/Mac
# TESSERACT_PATH=C:\\Program Files\\Tesseract-OCR\\tesseract.exe  # Windows

# Ports
FLASK_PORT=5000
SOCKET_PORT=5000

# Logging
LOG_LEVEL=INFO

# Capteurs Raspberry Pi
TEMP_SENSOR_PIN=4
MAX30102_ADDRESS=0x57
UART_PORT=/dev/ttyUSB0
```

### Configuration pour développement local

Si vous utilisez un fichier `.env`, charger dans `predict_api.py` :

```python
from dotenv import load_dotenv
import os

load_dotenv()
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-123')
FLASK_ENV = os.getenv('FLASK_ENV', 'development')
```

---

## Vérification de l'installation

```bash
# Tester les imports
python3 -c "
import flask
import pandas
import numpy
import sklearn
import cv2
import pytesseract
print('✓ Flask')
print('✓ Pandas')
print('✓ Numpy')
print('✓ Scikit-learn')
print('✓ OpenCV')
print('✓ Tesseract')
print('✓ Tous les modules installés avec succès!')
"

# Tester le modèle
python3 -c "
from model_trainer import predire_esi
import numpy as np
# Créer données test
X_test = np.random.rand(1, 29)
prediction = predire_esi(X_test)
print(f'✓ Modèle chargé. Prédiction test ESI: {prediction}')
"

# Tester le serveur Flask
python3 predict_api.py &
sleep 2
curl http://localhost:5000/api/file
# Devrait retourner {"patients": [], "total": 0}
kill %1
```

---

## Dépannage d'installation

| Erreur | Cause | Solution |
|--------|-------|----------|
| `ModuleNotFoundError: No module named 'flask'` | pip install échoué | `pip install -r requirements.txt` |
| `tesseract not found` | Tesseract non installé | Voir section Tesseract OCR ci-dessus |
| `Illegal argument: -tessdata-dir` | Chemin Tesseract incorrect | Vérifier `pytesseract.pytesseract.tesseract_cmd` |
| `Port 5000 already in use` | Autre processus sur port | `netstat -ano \| findstr :5000` (Windows) |
| `ImportError: opencv` | OpenCV non compilé correctement | `pip install --upgrade opencv-python` |
| `PermissionError: /dev/ttyUSB0` | Permission UART Pi | `sudo usermod -a -G dialout pi` |

---

## Prochaines étapes

1. ✅ Installation complète → Lire [README.md](../README.md)
2. 🔧 Configuration détaillée → Lire [ml/README.md](../ml/README.md)
3. 📡 Développement → Fork le repository et créer une branche
4. 🚀 Déploiement → Voir section Déploiement production

---

**Dernière mise à jour :** 25 avril 2026  
**Vérification :** Installation testée sur Windows 11, Mac Ventura, Ubuntu 22.04, Raspberry Pi 5 ✓
