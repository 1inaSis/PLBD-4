import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePatient } from '../context/PatientContext'
import { scannerCIN } from '../services/api'
import IndicateurEtape from '../components/IndicateurEtape'
import ConfirmationPatient from '../components/ConfirmationPatient'
import { IllustrationScanCIN } from '../components/IllustrationsGestes'
import '../styles/kiosk.css'

// États internes de cette page
const VUE = {
  ACCUEIL:      'accueil',      // Écran de bienvenue + bouton scan
  SCAN:         'scan',         // Scan en cours (spinner)
  CONFIRMATION: 'confirmation', // Données extraites à valider
}

export default function AccueilPage() {
  const navigate = useNavigate()
  const { setIdentite, connecterBorne, reinitialiser } = usePatient()

  const [vue, setVue]           = useState(VUE.ACCUEIL)
  const [donneesScan, setDonneesScan] = useState(null)
  const [erreur, setErreur]     = useState(null)
  const [wsConnecte, setWsConnecte] = useState(false)

  // Connexion WebSocket role=borne dès l'arrivée sur la page.
  // Le contexte garde la référence vivante pour tout le parcours.
  useEffect(() => {
    reinitialiser() // Nettoie toute session précédente

    const ws = connecterBorne((msg) => {
      // La borne écoute : constantes_update, patient_pris_en_charge
      if (msg.event === 'constantes_update') {
        console.log('[WS borne] Constantes reçues :', msg.data)
      }
    })

    ws.onopen  = () => setWsConnecte(true)
    ws.onclose = () => setWsConnecte(false)

    // Pas de fermeture ici : la WS doit survivre à la navigation
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Lancer le scan CIN ──────────────────────────────────────────────────────
  const lancerScan = async () => {
    setVue(VUE.SCAN)
    setErreur(null)
    try {
      // Sans image base64 → le backend utilise la caméra ou le mode simulation
      const data = await scannerCIN()
      setDonneesScan(data)
      setVue(VUE.CONFIRMATION)
    } catch (err) {
      setErreur(`Erreur lors du scan : ${err.message}. Veuillez réessayer.`)
      setVue(VUE.ACCUEIL)
    }
  }

  // ── Valider l'identité et passer à l'étape 2 ────────────────────────────────
  const confirmer = () => {
    setIdentite({
      session_id:  donneesScan.session_id,
      nom:         donneesScan.nom,
      prenom:      donneesScan.prenom,
      age:         donneesScan.age,
      sexe:        donneesScan.sexe,
      numero_cin:  donneesScan.numero_cin,
    })
    navigate('/questionnaire')
  }

  const recommencer = () => {
    setDonneesScan(null)
    setVue(VUE.ACCUEIL)
  }

  return (
    <div className="kiosk-shell">
      {/* Indicateur de progression */}
      <IndicateurEtape etapeCourante={1} />

      {/* Indicateur de connexion WebSocket (discret, coin bas-droit) */}
      <div className={`ws-badge ${wsConnecte ? 'ws-badge--ok' : 'ws-badge--off'}`}>
        {wsConnecte ? '● Connecté' : '○ Hors ligne'}
      </div>

      {/* Vue : Accueil */}
      {vue === VUE.ACCUEIL && (
        <div className="kiosk-center">
          <div className="kiosk-card">
            <span className="eyebrow">HealthGate · Urgences</span>
            <h1 className="kiosk-titre">Bienvenue</h1>
            <p className="kiosk-soustitre">
              Pour commencer votre prise en charge, veuillez scanner votre carte
              d'identité nationale.
            </p>

            {/* Illustration : positionnement de la carte sur le scanner */}
            <div className="illustration-wrapper">
              <IllustrationScanCIN />
            </div>

            {erreur && (
              <div className="kiosk-alerte" role="alert">
                {erreur}
              </div>
            )}

            <button
              className="kiosk-btn kiosk-btn--primary"
              onClick={lancerScan}
            >
              <svg className="kiosk-btn-icone" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="2" y="5" width="20" height="14" rx="2" />
                <path d="M2 10h20" />
              </svg>
              Scanner ma carte d'identité
            </button>

            <p className="kiosk-note">
              Pas de lecteur physique ? Le système utilisera le mode simulation.
            </p>
          </div>
        </div>
      )}

      {/* Vue : Scan en cours */}
      {vue === VUE.SCAN && (
        <div className="kiosk-center">
          <div className="kiosk-card kiosk-card--centree">
            {/* Indicateur caméra active */}
            <div className="camera-active-badge" role="status" aria-live="polite">
              <span className="camera-active-dot" aria-hidden="true" />
              Caméra active
            </div>
            <div className="kiosk-spinner" aria-label="Chargement" />
            <h2 className="kiosk-titre-sm">Scan en cours…</h2>
            <p className="kiosk-soustitre">
              Veuillez maintenir votre carte face au lecteur.
            </p>
          </div>
        </div>
      )}

      {/* Vue : Confirmation des données */}
      {vue === VUE.CONFIRMATION && (
        <ConfirmationPatient
          donnees={donneesScan}
          onConfirmer={confirmer}
          onRecommencer={recommencer}
        />
      )}
    </div>
  )
}
