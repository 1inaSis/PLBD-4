#!/bin/bash
# =============================================================================
# launch_kiosk.sh — Lancement de Chromium en mode kiosque (HealthGate)
# Projet PLBD-4 | Centrale Casablanca | 2025-2026
#
# Affiche http://localhost:5173 (borne patient) en plein écran 800x480.
# Ce script tourne dans la session graphique (DISPLAY=:0).
# Il est géré par plbd4-kiosk.service (redémarrage automatique inclus).
#
# Usage direct (test, session graphique active) :
#   chmod +x scripts/launch_kiosk.sh
#   DISPLAY=:0 ./scripts/launch_kiosk.sh
# =============================================================================

set -e

URL_BORNE="http://localhost:5173"
TIMEOUT_FRONTEND=120   # secondes max à attendre avant que le frontend réponde
DELAI_CRASH=5          # secondes avant relance si Chromium plante

# ── 1. Désactiver l'économiseur d'écran et la gestion d'énergie X11 ──────────
xset -dpms       2>/dev/null || true   # désactive DPMS (extinction auto de l'écran)
xset s off        2>/dev/null || true   # désactive l'économiseur d'écran
xset s noblank    2>/dev/null || true   # empêche le noircissement de l'écran

# ── 2. Masquer le curseur de la souris (kiosque tactile, pas de souris) ──────
# unclutter n'est pas toujours installé → ne pas planter si absent
unclutter -idle 0 -root &>/dev/null &
UNCLUTTER_PID=$!
trap 'kill $UNCLUTTER_PID 2>/dev/null; exit' SIGINT SIGTERM

# ── 3. Adapter la résolution à 800×480 (résolution native Nextion / 7") ──────
# Essai sur toutes les sorties connues (HDMI-1, HDMI-2, DSI-1, etc.)
for SORTIE in HDMI-1 HDMI-2 HDMI-A-1 HDMI-A-2 DSI-1 VGA-1; do
    if xrandr 2>/dev/null | grep -q "^${SORTIE} connected"; then
        # Vérifier si le mode 800x480 est déjà disponible
        if xrandr 2>/dev/null | grep -q "800x480"; then
            xrandr --output "${SORTIE}" --mode 800x480 2>/dev/null && \
                echo "[KIOSK] Resolution 800x480 appliquee sur ${SORTIE}" && break
        else
            # Créer le mode manuellement si absent (Modeline calculée pour 800×480@60Hz)
            MODELINE="40.73 800 816 896 1040 480 481 484 497 -hsync +vsync"
            xrandr --newmode "800x480_60" ${MODELINE} 2>/dev/null || true
            xrandr --addmode "${SORTIE}" "800x480_60"  2>/dev/null || true
            xrandr --output  "${SORTIE}" --mode "800x480_60" 2>/dev/null && \
                echo "[KIOSK] Mode 800x480 cree et applique sur ${SORTIE}" && break
        fi
    fi
done

# ── 4. Attendre que le frontend soit disponible ───────────────────────────────
echo "[KIOSK] Attente du frontend sur ${URL_BORNE}..."
SECONDES=0
until curl -s --max-time 2 "${URL_BORNE}" > /dev/null 2>&1; do
    sleep 2
    SECONDES=$((SECONDES + 2))
    if [ "${SECONDES}" -ge "${TIMEOUT_FRONTEND}" ]; then
        echo "[KIOSK] Timeout : le frontend ne repond pas apres ${TIMEOUT_FRONTEND}s"
        echo "[KIOSK] Lancement de Chromium quand meme (page de retry integree)"
        break
    fi
done
echo "[KIOSK] Frontend disponible — lancement de Chromium"

# ── 5. Supprimer le flag "crash" laissé par une session précédente ────────────
# Sans ça, Chromium affiche une bannière "Chromium n'a pas été fermé correctement"
PROFIL_DIR="${HOME}/.config/chromium"
if [ -f "${PROFIL_DIR}/Default/Preferences" ]; then
    # Remplacer "exit_type":"Crashed" par "exit_type":"Normal"
    sed -i 's/"exit_type":"Crashed"/"exit_type":"Normal"/g' \
        "${PROFIL_DIR}/Default/Preferences" 2>/dev/null || true
fi

# ── 6. Boucle de lancement Chromium (relance automatique après crash) ─────────
echo "[KIOSK] Demarrage de la boucle Chromium (auto-restart en cas de crash)"
while true; do
    chromium-browser \
        --kiosk \
        --no-sandbox \
        --disable-infobars \
        --disable-notifications \
        --disable-session-crashed-bubble \
        --disable-restore-session-state \
        --disable-translate \
        --disable-features=TranslateUI \
        --disable-pinch \
        --overscroll-history-navigation=0 \
        --check-for-update-interval=31536000 \
        --noerrdialogs \
        --incognito \
        --window-size=800,480 \
        --window-position=0,0 \
        --app="${URL_BORNE}" \
        2>/dev/null

    echo "[KIOSK] Chromium s'est arrete — relance dans ${DELAI_CRASH}s..."
    sleep "${DELAI_CRASH}"
done
