#!/bin/bash
# =============================================================================
# start_dev.sh — Lancement rapide en mode développement
# Projet PLBD-4 | Centrale Casablanca | 2025-2026
#
# Lance le backend FastAPI + le frontend Vite en parallèle
# avec des logs colorés et préfixés.
#
# Usage :
#   chmod +x scripts/start_dev.sh
#   ./scripts/start_dev.sh
# =============================================================================

# Répertoire racine du projet (parent du dossier scripts/)
PROJET_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="${PROJET_DIR}/.venv"

# ── Couleurs ─────────────────────────────────────────────────────────────────
C_RESET="\033[0m"
C_BACKEND="\033[1;36m"    # cyan  → backend
C_FRONTEND="\033[1;35m"   # violet → frontend
C_INFO="\033[1;33m"       # jaune → messages généraux

PREFIX_B="${C_BACKEND}[BACKEND] ${C_RESET}"
PREFIX_F="${C_FRONTEND}[FRONTEND]${C_RESET}"

# ── Arrêt propre à Ctrl+C ───────────────────────────────────────────────────
PID_BACKEND=0
PID_FRONTEND=0

cleanup() {
    echo -e "\n${C_INFO}[INFO] Arrêt des serveurs...${C_RESET}"
    [ $PID_BACKEND  -ne 0 ] && kill "$PID_BACKEND"  2>/dev/null
    [ $PID_FRONTEND -ne 0 ] && kill "$PID_FRONTEND" 2>/dev/null
    wait
    echo -e "${C_INFO}[INFO] Serveurs arrêtés.${C_RESET}"
    exit 0
}
trap cleanup SIGINT SIGTERM

# ── Vérifications ────────────────────────────────────────────────────────────
[ ! -f "${PROJET_DIR}/backend/main.py" ] && \
    echo -e "${C_INFO}[ERR] backend/main.py introuvable. Lancez depuis la racine du projet.${C_RESET}" && exit 1

[ ! -d "${VENV_DIR}" ] && \
    echo -e "${C_INFO}[WARN] Virtualenv absent. Création...${C_RESET}" && \
    python3 -m venv "${VENV_DIR}" && \
    "${VENV_DIR}/bin/pip" install -r "${PROJET_DIR}/backend/requirements.txt" -q

# ── Sélection de l'exécutable Python ────────────────────────────────────────
if [ -f "${VENV_DIR}/bin/uvicorn" ]; then
    UVICORN="${VENV_DIR}/bin/uvicorn"
else
    UVICORN="uvicorn"
fi

# ── En-tête ──────────────────────────────────────────────────────────────────
clear
echo -e "${C_INFO}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║         HealthGate — Mode développement             ║"
echo "║  Backend  → http://localhost:8000                   ║"
echo "║  Frontend → http://localhost:5173                   ║"
echo "║  Ctrl+C pour arrêter les deux serveurs              ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${C_RESET}"

# ── Lancement du backend (FastAPI + uvicorn --reload) ────────────────────────
echo -e "${PREFIX_B} Démarrage uvicorn (reload activé)..."
(
    cd "${PROJET_DIR}"
    export PYTHONPATH="${PROJET_DIR}"
    "${UVICORN}" backend.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --reload \
        --reload-dir backend \
        --reload-dir ml \
        2>&1 | while IFS= read -r ligne; do
            echo -e "${PREFIX_B} ${ligne}"
        done
) &
PID_BACKEND=$!

# ── Lancement du frontend (Vite dev server) ───────────────────────────────────
echo -e "${PREFIX_F} Démarrage Vite (hot-reload activé)..."
(
    cd "${PROJET_DIR}/frontend"
    npm run dev -- --host 0.0.0.0 --port 5173 \
        2>&1 | while IFS= read -r ligne; do
            echo -e "${PREFIX_F} ${ligne}"
        done
) &
PID_FRONTEND=$!

# ── Attente de la fin (Ctrl+C déclenche cleanup) ─────────────────────────────
wait $PID_BACKEND $PID_FRONTEND
