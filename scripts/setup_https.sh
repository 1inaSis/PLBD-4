#!/bin/bash
# =============================================================================
# setup_https.sh — Génère le certificat SSL auto-signé pour PLBD-4
# Projet PLBD-4 | Centrale Casablanca | 2025-2026
#
# Usage :
#   chmod +x scripts/setup_https.sh
#   bash scripts/setup_https.sh
#
# Résultat : /home/touaregs/PLBD-4/certs/{cert.pem, key.pem}
# =============================================================================

set -e

CERT_DIR="/home/touaregs/PLBD-4/certs"

echo "[HTTPS] Création du dossier certificats : ${CERT_DIR}"
mkdir -p "${CERT_DIR}"

echo "[HTTPS] Génération du certificat auto-signé (RSA 4096, 10 ans)..."
openssl req -x509 -newkey rsa:4096 \
  -keyout "${CERT_DIR}/key.pem" \
  -out    "${CERT_DIR}/cert.pem" \
  -days   3650 \
  -nodes \
  -subj "/C=MA/ST=Casablanca/L=Casablanca/O=ECC/OU=PLBD4/CN=172.22.6.62" \
  -addext "subjectAltName=IP:172.22.6.62,IP:127.0.0.1,DNS:localhost,DNS:TOUAREG.local"

chmod 600 "${CERT_DIR}/key.pem"
chmod 644 "${CERT_DIR}/cert.pem"

echo "[HTTPS] Certificat généré avec succès :"
echo "  Clé privée : ${CERT_DIR}/key.pem"
echo "  Certificat : ${CERT_DIR}/cert.pem"
echo ""
echo "[HTTPS] Pour autoriser l'iPad :"
echo "  1. Ouvre https://172.22.6.62:5173 dans Safari"
echo "  2. Accepte l'avertissement de sécurité"
echo "  3. Installe le certificat : Réglages → Général → VPN et gestion → Certificats"
