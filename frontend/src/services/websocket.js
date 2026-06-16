// Utilitaire WebSocket — se connecte via le proxy Vite (/ws → ws://localhost:8000/ws)

/**
 * Crée une connexion WebSocket pour le rôle donné.
 *
 * @param {string} role        - 'borne' | 'salle' | 'medecin'
 * @param {Function} onMessage - callback({ event, data }) appelé à chaque message serveur
 * @param {string} medecin_id  - 'M1' | 'M2' (requis si role === 'medecin')
 * @returns {WebSocket}
 */
export function creerWebSocket(role, onMessage, medecin_id = '') {
  const params = new URLSearchParams({ role })
  if (medecin_id) params.set('medecin_id', medecin_id)

  const ws = new WebSocket(`/ws?${params}`)

  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data)
      onMessage(msg)
    } catch {
      // message non-JSON ignoré
    }
  }

  return ws
}

/**
 * Envoie une commande au serveur via le WebSocket.
 * @param {WebSocket} ws
 * @param {string} action - 'ping' | 'get_file'
 */
export function envoyerCommande(ws, action) {
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ action }))
  }
}
