// Interface salle d'attente (écran séparé, role=salle)
// À implémenter lors d'une prochaine session.

import { useEffect, useState } from 'react'
import { creerWebSocket } from '../services/websocket'
import '../styles/kiosk.css'

export default function FileAttentePage() {
  const [file, setFile] = useState([])
  const [horodatage, setHorodatage] = useState('')

  useEffect(() => {
    const ws = creerWebSocket('salle', (msg) => {
      if (msg.event === 'file_mise_a_jour') {
        setFile(msg.data.file ?? [])
        setHorodatage(msg.data.horodatage ?? '')
      }
    })
    return () => ws.close()
  }, [])

  return (
    <div className="kiosk-shell">
      <div className="kiosk-center">
        <div className="kiosk-card">
          <span className="eyebrow">Salle d'attente</span>
          <h2 className="kiosk-titre-sm">File d'attente — {horodatage}</h2>
          <p className="kiosk-soustitre">
            {file.length} patient(s) en attente. Interface complète à venir.
          </p>
        </div>
      </div>
    </div>
  )
}
