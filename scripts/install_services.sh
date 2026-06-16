#!/bin/bash
# =============================================================================
# install_services.sh — Déploiement HealthGate sur Raspberry Pi
# Projet PLBD-4 | Centrale Casablanca | 2025-2026
#
# Usage :
#   chmod +x scripts/install_services.sh
#   sudo ./scripts/install_services.sh [IP_FIXE] [INTERFACE_RESEAU]
#
# Exemples :
#   sudo ./scripts/install_services.sh 192.168.1.100
#   sudo ./scripts/install_services.sh 192.168.1.100 wlan0
# =============================================================================

set -e   # arrêt immédiat en cas d'erreur

# ── Couleurs pour les logs ───────────────────────────────────────────────────
VERT="\033[1;32m"
JAUNE="\033[1;33m"
ROUGE="\033[1;31m"
BLEU="\033[1;34m"
RESET="\033[0m"

ok()   { echo -e "${VERT}[OK]${RESET}    $*"; }
info() { echo -e "${BLEU}[INFO]${RESET}  $*"; }
warn() { echo -e "${JAUNE}[WARN]${RESET}  $*"; }
err()  { echo -e "${ROUGE}[ERR]${RESET}   $*"; exit 1; }

# ── Paramètres ───────────────────────────────────────────────────────────────
IP_FIXE="${1:-}"
INTERFACE="${2:-eth0}"
PROJET_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="${PROJET_DIR}/.venv"
USER_PI="${SUDO_USER:-pi}"

echo -e "${BLEU}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║     HealthGate — Installation services systemd      ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${RESET}"
info "Répertoire projet : ${PROJET_DIR}"
info "Utilisateur       : ${USER_PI}"

# ── Vérifications préliminaires ──────────────────────────────────────────────
[ "$EUID" -ne 0 ] && err "Ce script doit être lancé en sudo : sudo ./scripts/install_services.sh"
[ ! -f "${PROJET_DIR}/backend/main.py" ] && err "Fichier backend/main.py introuvable. Êtes-vous à la racine du projet ?"

# ── 1. Dépendances système ───────────────────────────────────────────────────
info "Installation des dépendances système..."
apt-get update -qq
apt-get install -y -qq python3-pip python3-venv nodejs npm
ok "Dépendances système installées"

# ── 2. Virtualenv Python ─────────────────────────────────────────────────────
info "Création du virtualenv Python..."
if [ ! -d "${VENV_DIR}" ]; then
    sudo -u "${USER_PI}" python3 -m venv "${VENV_DIR}"
    ok "Virtualenv créé dans ${VENV_DIR}"
else
    ok "Virtualenv existant trouvé"
fi

info "Installation des dépendances Python..."
sudo -u "${USER_PI}" "${VENV_DIR}/bin/pip" install --upgrade pip -q
sudo -u "${USER_PI}" "${VENV_DIR}/bin/pip" install -r "${PROJET_DIR}/backend/requirements.txt" -q
sudo -u "${USER_PI}" "${VENV_DIR}/bin/pip" install -r "${PROJET_DIR}/ml/requirements.txt" -q 2>/dev/null || true

# pyserial pour la communication Arduino
sudo -u "${USER_PI}" "${VENV_DIR}/bin/pip" install pyserial --break-system-packages -q 2>/dev/null || \
sudo -u "${USER_PI}" "${VENV_DIR}/bin/pip" install pyserial -q
ok "Dépendances Python installées (pyserial inclus)"

# ── 3. Build du frontend React ───────────────────────────────────────────────
info "Build du frontend React (production)..."
cd "${PROJET_DIR}/frontend"
sudo -u "${USER_PI}" npm install --silent
sudo -u "${USER_PI}" npm run build --silent
ok "Frontend buildé dans frontend/dist/"
cd "${PROJET_DIR}"

# ── 4. Adapter les chemins dans les fichiers service ─────────────────────────
info "Configuration des fichiers service systemd..."
for SERVICE_SRC in "${PROJET_DIR}/systemd/"*.service; do
    SERVICE_NAME=$(basename "${SERVICE_SRC}")
    SERVICE_DEST="/etc/systemd/system/${SERVICE_NAME}"

    # Remplacer /home/pi/PLBD-4 par le chemin réel du projet
    sed "s|/home/pi/PLBD-4|${PROJET_DIR}|g; s|User=pi|User=${USER_PI}|g; s|Group=pi|Group=${USER_PI}|g" \
        "${SERVICE_SRC}" > "${SERVICE_DEST}"

    ok "Service installé : ${SERVICE_DEST}"
done

# ── 5. Kiosque Chromium — installation et configuration ──────────────────────
info "Installation de Chromium et des utilitaires kiosque..."
apt-get install -y -qq chromium-browser unclutter x11-xserver-utils
ok "Chromium et unclutter installés"

info "Rendre launch_kiosk.sh exécutable..."
chmod +x "${PROJET_DIR}/scripts/launch_kiosk.sh"
ok "Permissions kiosque configurées"

# ── 5b. Configuration de l'auto-login graphique (nécessaire pour DISPLAY=:0) ─
info "Configuration de l'auto-login graphique pour ${USER_PI}..."
if command -v raspi-config > /dev/null 2>&1; then
    # Mode Desktop avec auto-login (raspi-config non-interactif)
    raspi-config nonint do_boot_behaviour B4 2>/dev/null && \
        ok "Auto-login graphique activé via raspi-config" || \
        warn "raspi-config B4 echoue — activez manuellement : raspi-config → System → Boot → Desktop Autologin"
else
    warn "raspi-config absent — activez l'auto-login graphique manuellement"
fi

# ── 6. Activation des services ───────────────────────────────────────────────
info "Activation des services au démarrage..."
systemctl daemon-reload
systemctl enable plbd4-backend.service
systemctl enable plbd4-frontend.service
systemctl enable plbd4-kiosk.service
ok "Services activés (démarrage automatique au boot)"

# ── 7. Permissions port série (Arduino) ─────────────────────────────────────
info "Ajout de ${USER_PI} au groupe dialout (accès port série Arduino)..."
usermod -aG dialout "${USER_PI}"
ok "Accès port série configuré (reconnexion nécessaire pour appliquer)"

# ── 7. Configuration IP fixe ─────────────────────────────────────────────────
if [ -n "${IP_FIXE}" ]; then
    info "Configuration IP fixe : ${IP_FIXE} sur ${INTERFACE}..."

    # Détecter si NetworkManager ou dhcpcd est utilisé
    if systemctl is-active --quiet NetworkManager 2>/dev/null; then
        # RPi OS Bookworm (≥ 2023) : NetworkManager
        CONN_NAME="HealthGate-Static"
        nmcli con delete "${CONN_NAME}" 2>/dev/null || true
        nmcli con add type ethernet con-name "${CONN_NAME}" ifname "${INTERFACE}" \
            ipv4.method manual \
            ipv4.addresses "${IP_FIXE}/24" \
            ipv4.gateway "${IP_FIXE%.*}.1" \
            ipv4.dns "8.8.8.8 8.8.4.4" \
            connection.autoconnect yes
        nmcli con up "${CONN_NAME}"
        ok "IP fixe configurée via NetworkManager : ${IP_FIXE}"

    elif [ -f /etc/dhcpcd.conf ]; then
        # RPi OS Bullseye et antérieur : dhcpcd
        # Supprimer une éventuelle config précédente pour cette interface
        sed -i "/^# HealthGate/,/^$/d" /etc/dhcpcd.conf

        cat >> /etc/dhcpcd.conf << EOF

# HealthGate — IP fixe configurée par install_services.sh
interface ${INTERFACE}
static ip_address=${IP_FIXE}/24
static routers=${IP_FIXE%.*}.1
static domain_name_servers=8.8.8.8 8.8.4.4
EOF
        systemctl restart dhcpcd
        ok "IP fixe configurée via dhcpcd : ${IP_FIXE}"

    else
        warn "Ni NetworkManager ni dhcpcd détectés. Configurez l'IP fixe manuellement."
    fi
else
    warn "Aucune IP fournie → IP fixe non configurée. Relancez avec : sudo $0 192.168.1.100"
fi

# ── 9. Démarrage immédiat ─────────────────────────────────────────────────────
info "Démarrage des services..."
systemctl start plbd4-backend.service
systemctl start plbd4-frontend.service
# plbd4-kiosk.service requiert un DISPLAY actif — il démarrera au prochain boot graphique
sleep 2

echo ""
echo -e "${VERT}╔══════════════════════════════════════════════════════╗${RESET}"
echo -e "${VERT}║              Installation terminée !                ║${RESET}"
echo -e "${VERT}╚══════════════════════════════════════════════════════╝${RESET}"
echo ""
echo -e "  Backend  : ${BLEU}http://${IP_FIXE:-<IP_PI>}:8000${RESET}"
echo -e "  Borne    : ${BLEU}http://${IP_FIXE:-<IP_PI>}:5173/${RESET}"
echo -e "  Salle    : ${BLEU}http://${IP_FIXE:-<IP_PI>}:5173/salle${RESET}"
echo -e "  Médecin  : ${BLEU}http://${IP_FIXE:-<IP_PI>}:5173/medecin/M1${RESET}"
echo ""
echo -e "  Logs backend  : ${JAUNE}journalctl -u plbd4-backend -f${RESET}"
echo -e "  Logs frontend : ${JAUNE}journalctl -u plbd4-frontend -f${RESET}"
echo -e "  Logs kiosque  : ${JAUNE}journalctl -u plbd4-kiosk -f${RESET}"
echo ""
echo -e "${JAUNE}[!] Redémarrez le Pi pour lancer le kiosque Chromium : sudo reboot${RESET}"
echo ""
systemctl status plbd4-backend.service --no-pager -l | head -8
systemctl status plbd4-frontend.service --no-pager -l | head -8
