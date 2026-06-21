// Interface médecin — dossiers patients assignés + prise en charge
// Route : /medecin/:id  (ex: /medecin/M1 ou /medecin/M2)
//
// Flux :
//   1. Chargement initial via GET /api/medecin/{id} (rapport complet par patient)
//   2. WebSocket ?role=medecin&medecin_id={id} maintenu en arrière-plan
//   3. Sur file_mise_a_jour → re-fetch GET /api/medecin/{id}
//   4. Sur alerte_critique  → banner modal persistant (ESI ≤ 2)
//   5. Clic patient → Vue DOSSIER (données déjà chargées)
//   6. Bouton "Pris en charge" → POST /api/prise_en_charge → re-fetch liste

import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { getPatientsMedecin, prendreEnCharge, getHistoriqueMedecin, getRapportPatient, modifierESI } from '../services/api'
import { creerWebSocket, envoyerCommande } from '../services/websocket'
import { useNotificationPush } from '../hooks/useNotificationPush'
import BiometrieDisplay, { evaluerCouleur } from '../components/BiometrieDisplay'
import { ZONES_MAP } from '../components/CorpsHumain'
import BoutonPleinEcran from '../components/BoutonPleinEcran'
import '../styles/kiosk.css'

// ── Configuration niveaux ESI ─────────────────────────────────────────────────
const ESI_CFG = {
  1: { libelle: 'CRITIQUE',    fond: 'rgba(239,68,68,0.14)',   bordure: '#ef4444', texte: '#f87171' },
  2: { libelle: 'TRÈS URGENT', fond: 'rgba(249,115,22,0.13)',  bordure: '#f97316', texte: '#fb923c' },
  3: { libelle: 'URGENT',      fond: 'rgba(251,191,36,0.11)',  bordure: '#fbbf24', texte: '#fbbf24' },
  4: { libelle: 'SEMI-URGENT', fond: 'rgba(52,211,153,0.10)',  bordure: '#34d399', texte: '#34d399' },
  5: { libelle: 'NON URGENT',  fond: 'rgba(56,189,248,0.09)',  bordure: '#38bdf8', texte: '#38bdf8' },
}

// ── Labels françaises pour les features NLP actives ───────────────────────────
const NLP_LABELS = {
  nlp_chest_pain:            'Douleur thoracique',
  nlp_dyspnea:               'Dyspnée / Essoufflement',
  nlp_loss_of_consciousness: 'Perte de connaissance',
  nlp_severe_bleeding:       'Saignement important',
  nlp_neurological:          'Symptômes neurologiques',
  nlp_abdominal_pain:        'Douleur abdominale',
  nlp_fever:                 'Fièvre',
  nlp_trauma:                'Traumatisme',
  nlp_urgence_critique:      'Urgence critique détectée',
}

// Compteur toast
let _toastId = 0

// ── Audio via AudioContext partagé (initialisé après interaction utilisateur) ──
function jouerBipChat(audioCtxRef) {
  const ctx = audioCtxRef?.current
  if (!ctx) return
  try {
    ctx.resume().then(() => {
      const osc  = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.type = 'sine'
      osc.frequency.value = 440
      gain.gain.setValueAtTime(0.12, ctx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.45)
      osc.start(ctx.currentTime)
      osc.stop(ctx.currentTime + 0.5)
    })
  } catch { /* AudioContext non disponible */ }
}

function jouerBip(nbFois = 1, audioCtxRef) {
  const ctx = audioCtxRef?.current
  if (!ctx) return
  try {
    ctx.resume().then(() => {
      for (let i = 0; i < nbFois; i++) {
        const osc  = ctx.createOscillator()
        const gain = ctx.createGain()
        osc.connect(gain)
        gain.connect(ctx.destination)
        osc.type = 'sine'
        osc.frequency.value = i % 2 === 0 ? 880 : 660
        gain.gain.setValueAtTime(0.35, ctx.currentTime + i * 0.5)
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.5 + 0.3)
        osc.start(ctx.currentTime + i * 0.5)
        osc.stop(ctx.currentTime + i * 0.5 + 0.4)
      }
    })
  } catch { /* AudioContext non disponible */ }
}

// ═════════════════════════════════════════════════════════════════════════════
export default function MedecinPage() {
  const { id: medecinId } = useParams()   // 'M1' ou 'M2'

  // ── Notifications push ──────────────────────────────────────────────────────
  const { permission: notifPermission, demander: demanderNotif } = useNotificationPush()

  // ── État principal ──────────────────────────────────────────────────────────
  const [medecin, setMedecin]             = useState(null)
  const [patients, setPatients]           = useState([])
  const [chargement, setChargement]       = useState(true)
  const [erreurChargement, setErreur]     = useState(null)

  // Vue active : 'liste' | 'dossier'
  const [vue, setVue]                     = useState('liste')
  const [patientActif, setPatientActif]   = useState(null)

  // Alertes critiques (ESI ≤ 2) — modal persistant
  const [alertesCritiques, setAlertesCritiques] = useState([])

  // Prise en charge en cours
  const [enPriseEnCharge, setEnPriseEnCharge]   = useState(false)

  // Toasts événements WS
  const [toasts, setToasts]               = useState([])

  // WebSocket état
  const [wsEtat, setWsEtat]               = useState('connexion')

  // Alerte sonore
  const [sonActif, setSonActif]           = useState(true)
  const sonActifRef                       = useRef(true)

  // Onglet actif : 'attente' | 'historique'
  const [onglet, setOnglet]               = useState('attente')
  const [historique, setHistorique]       = useState([])
  const [chargHistorique, setChargH]      = useState(false)

  // ── Chat inter-médecins ─────────────────────────────────────────────────────
  const [chatOuvert, setChatOuvert]       = useState(false)
  const [chatMessages, setChatMessages]   = useState([])
  const [chatInput, setChatInput]         = useState('')
  const [chatNonLus, setChatNonLus]       = useState(0)
  const chatOuvertRef                     = useRef(false)
  const chatFinRef                        = useRef(null)

  // ── Audio — initialisé après première interaction utilisateur ───────────────
  const audioCtxRef                       = useRef(null)
  const [sonDebloque, setSonDebloque]     = useState(false)

  const wsRef    = useRef(null)
  const pingRef  = useRef(null)
  const monteRef = useRef(true)

  const basculerSon = () => {
    const val = !sonActifRef.current
    sonActifRef.current = val
    setSonActif(val)
  }

  // ── Chat inter-médecins ─────────────────────────────────────────────────────
  const autreMedecinId = medecinId === 'M1' ? 'M2' : 'M1'

  const basculerChat = () => {
    const v = !chatOuvertRef.current
    chatOuvertRef.current = v
    setChatOuvert(v)
    if (v) setChatNonLus(0)
  }

  const envoyerMessageChat = () => {
    const texte = chatInput.trim()
    if (!texte || wsRef.current?.readyState !== WebSocket.OPEN) return
    wsRef.current.send(JSON.stringify({
      action: 'message',
      destinataire: autreMedecinId,
      texte,
    }))
    setChatInput('')
  }

  // ── Init AudioContext au premier clic/touch ────────────────────────────────
  useEffect(() => {
    const initAudio = () => {
      if (audioCtxRef.current) return
      try {
        audioCtxRef.current = new (window.AudioContext || window.webkitAudioContext)()
        if (monteRef.current) setSonDebloque(true)
      } catch {}
      document.removeEventListener('click', initAudio)
      document.removeEventListener('touchstart', initAudio)
    }
    document.addEventListener('click', initAudio)
    document.addEventListener('touchstart', initAudio)
    return () => {
      document.removeEventListener('click', initAudio)
      document.removeEventListener('touchstart', initAudio)
    }
  }, [])

  // Scroll vers le bas quand de nouveaux messages arrivent
  useEffect(() => {
    if (chatOuvert && chatFinRef.current) {
      chatFinRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [chatMessages, chatOuvert])

  // ── Chargement de la liste patients ────────────────────────────────────────
  const chargerPatients = useCallback(async () => {
    if (!monteRef.current) return
    try {
      const res = await getPatientsMedecin(medecinId)
      if (!monteRef.current) return
      setMedecin(res.medecin ?? null)
      setPatients(res.patients ?? [])
      setErreur(null)
    } catch (err) {
      if (monteRef.current) setErreur(`Erreur chargement : ${err.message}`)
    } finally {
      if (monteRef.current) setChargement(false)
    }
  }, [medecinId])

  // Chargement initial
  useEffect(() => {
    chargerPatients()
  }, [chargerPatients])

  // ── Historique patients traités ────────────────────────────────────────────
  const chargerHistorique = useCallback(async () => {
    if (!monteRef.current) return
    setChargH(true)
    try {
      const res = await getHistoriqueMedecin(medecinId)
      if (monteRef.current) setHistorique(res.historique ?? [])
    } catch { /* silencieux */ }
    finally { if (monteRef.current) setChargH(false) }
  }, [medecinId])

  // ── Toasts ─────────────────────────────────────────────────────────────────
  const ajouterToast = useCallback((message, type = 'info') => {
    const id = ++_toastId
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => {
      if (monteRef.current) setToasts(prev => prev.filter(t => t.id !== id))
    }, 5000)
  }, [])

  // ── Gestionnaire d'événements WebSocket ────────────────────────────────────
  const gererEvenement = useCallback((msg) => {
    const { event, data } = msg

    switch (event) {

      // Mise à jour de la file → recharger les patients assignés
      case 'file_mise_a_jour':
        setWsEtat('connecte')
        chargerPatients()
        break

      // Nouveau patient → toast si assigné à ce médecin
      case 'nouveau_patient':
        if (data.medecin_id === medecinId) {
          ajouterToast(
            `Nouveau patient : ${data.prenom} ${data.nom} — ESI ${data.esi}`,
            'nouveau',
          )
          if (sonActifRef.current && data.esi <= 2) {
            jouerBip(data.esi === 1 ? 3 : 1, audioCtxRef)
          }
        }
        break

      // ALERTE CRITIQUE (ESI ≤ 2) — modal persistant, envoyé au médecin assigné uniquement
      case 'alerte_critique':
        setAlertesCritiques(prev => {
          if (prev.some(a => a.patient_id === data.patient_id)) return prev
          return [...prev, data]
        })
        if (sonActifRef.current) {
          jouerBip(3, audioCtxRef)
        }
        // Notification push si la page est en arrière-plan
        if (document.hidden && typeof Notification !== 'undefined' && Notification.permission === 'granted') {
          const titre = data.esi <= 1 ? '🚨 URGENCE ESI 1 — HealthGate' : '⚠️ Priorité ESI 2 — HealthGate'
          const corps = data.esi <= 1
            ? `Patient ${data.prenom} ${data.nom} nécessite une prise en charge immédiate`
            : `${data.prenom} ${data.nom} en attente`
          try { new Notification(titre, { body: corps, icon: '/favicon.ico', requireInteraction: true, tag: `alerte-${data.patient_id}` }) } catch {}
        }
        break

      // Message inter-médecins
      case 'message_medecin':
        setChatMessages(prev => [...prev.slice(-49), data])
        if (!chatOuvertRef.current) setChatNonLus(n => n + 1)
        if (sonActifRef.current) jouerBipChat(audioCtxRef)
        break

      // Priorité modifiée manuellement → toast + reload
      case 'priorite_modifiee':
        ajouterToast(
          `Priorité modifiée : ${data.nom} ESI ${data.ancien_esi} → ${data.nouvel_esi}`,
          'degradation',
        )
        chargerPatients()
        break

      // Patient pris en charge → toast + refresh historique
      case 'patient_pris_en_charge':
        ajouterToast(
          `Pris en charge : ${data.patient_id} par ${data.medecin} à ${data.heure}`,
          'prise_en_charge',
        )
        chargerHistorique()
        break

      // Dégradation clinique → toast d'alerte
      case 'degradation':
        ajouterToast(
          `⚠️ Dégradation : ${data.nom} — ESI ${data.ancien_esi} → ${data.nouvel_esi}`,
          'degradation',
        )
        break

      default:
        break
    }
  }, [medecinId, chargerPatients, ajouterToast, chargerHistorique])

  // ── Connexion WebSocket avec reconnexion automatique ───────────────────────
  useEffect(() => {
    monteRef.current = true

    const connecter = () => {
      if (!monteRef.current) return
      setWsEtat('connexion')

      const ws = creerWebSocket('medecin', (msg) => {
        if (monteRef.current) gererEvenement(msg)
      }, medecinId)

      ws.onopen = () => {
        if (!monteRef.current) return
        setWsEtat('connecte')
        pingRef.current = setInterval(() => envoyerCommande(ws, 'ping'), 30_000)
      }

      ws.onclose = () => {
        if (!monteRef.current) return
        setWsEtat('deconnecte')
        clearInterval(pingRef.current)
        setTimeout(connecter, 5000)
      }

      ws.onerror = () => {
        if (monteRef.current) setWsEtat('deconnecte')
      }

      wsRef.current = ws
    }

    connecter()

    return () => {
      monteRef.current = false
      clearInterval(pingRef.current)
      wsRef.current?.close()
    }
  }, [gererEvenement, medecinId])

  // ── Modification manuelle de l'ESI ────────────────────────────────────────
  const handleModifierESI = async (patientId, nouvelEsi, raison) => {
    try {
      await modifierESI(patientId, nouvelEsi, raison)
      ajouterToast(`ESI ${nouvelEsi} appliqué`, 'info')
      await chargerPatients()
    } catch (err) {
      ajouterToast(`Erreur modification ESI : ${err.message}`, 'degradation')
    }
  }

  // ── Prise en charge d'un patient ───────────────────────────────────────────
  const handlePriseEnCharge = async (patientId) => {
    setEnPriseEnCharge(true)
    try {
      await prendreEnCharge(patientId, medecinId)
      // Retour à la liste + rechargement
      setVue('liste')
      setPatientActif(null)
      await chargerPatients()
    } catch (err) {
      ajouterToast(`Erreur prise en charge : ${err.message}`, 'degradation')
    } finally {
      if (monteRef.current) setEnPriseEnCharge(false)
    }
  }

  // ── Ouvrir le dossier d'un patient ─────────────────────────────────────────
  const ouvrirDossier = (patient) => {
    setPatientActif(patient)
    setVue('dossier')
  }

  // ── Ouvrir le dossier d'un patient de l'historique ───────────────────────
  const voirDossierHistorique = useCallback(async (h) => {
    let p
    try {
      const data = await getRapportPatient(h.session_id)
      p = { ...data.rapport, patient_id: h.patient_id_display, _depuis_historique: true }
    } catch {
      p = {
        patient_id: h.patient_id_display,
        nom: h.nom, prenom: h.prenom, age: h.age,
        esi_predit: h.esi,
        heure_arrivee: h.heure_arrivee,
        _depuis_historique: true,
      }
    }
    setPatientActif(p)
    setVue('dossier')
  }, [])

  // ── Ouvrir le dossier depuis une alerte critique ────────────────────────────
  const ouvrirAlerte = (alerte) => {
    // Le rapport est inclus dans l'événement alerte_critique
    const p = alerte.rapport ?? alerte
    ouvrirDossier(p)
    dismisserAlerte(alerte.patient_id)
  }

  const dismisserAlerte = (patient_id) => {
    setAlertesCritiques(prev => prev.filter(a => a.patient_id !== patient_id))
  }

  // ── Rendu ────────────────────────────────────────────────────────────────────
  return (
    <div className="medecin-shell">

      {/* ── En-tête ──────────────────────────────────────────────── */}
      <header className="medecin-header">
        <div className="medecin-header-info">
          <span className="medecin-nom">
            👨‍⚕️ {medecin?.nom ?? `Médecin ${medecinId}`}
          </span>
          <span className="medecin-specialite">{medecin?.specialite ?? ''}</span>
        </div>
        <div className="medecin-header-droite">
          <BoutonPleinEcran />
          <button
            onClick={notifPermission !== 'granted' ? demanderNotif : undefined}
            title={notifPermission === 'granted' ? 'Notifications push activées' : 'Activer les notifications push (ESI 1/2)'}
            style={{
              background: notifPermission === 'granted' ? 'rgba(20,184,166,0.12)' : 'rgba(148,163,184,0.10)',
              border: `1px solid ${notifPermission === 'granted' ? 'rgba(20,184,166,0.3)' : 'rgba(148,163,184,0.2)'}`,
              borderRadius: 8, padding: '5px 12px',
              cursor: notifPermission !== 'granted' ? 'pointer' : 'default',
              color: notifPermission === 'granted' ? '#2dd4bf' : '#64748b', fontSize: '0.82rem', fontWeight: 600,
            }}
          >
            {notifPermission === 'granted' ? '🔔 Notifs activées' : '🔕 Notifs désactivées'}
          </button>
          <button
            onClick={basculerSon}
            title={sonActif ? 'Couper le son' : 'Activer le son'}
            style={{
              background: sonActif ? 'rgba(20,184,166,0.12)' : 'rgba(148,163,184,0.10)',
              border: `1px solid ${sonActif ? 'rgba(20,184,166,0.3)' : 'rgba(148,163,184,0.2)'}`,
              borderRadius: 8, padding: '5px 12px', cursor: 'pointer',
              color: sonActif ? '#2dd4bf' : '#64748b', fontSize: '0.82rem', fontWeight: 600,
            }}
          >
            {sonActif ? '🔊 Son actif' : '🔇 Son coupé'}
          </button>
          <button
            onClick={() => {
              if (!audioCtxRef.current) {
                try {
                  audioCtxRef.current = new (window.AudioContext || window.webkitAudioContext)()
                  setSonDebloque(true)
                } catch {}
              }
              if (sonActif) jouerBip(1, audioCtxRef)
            }}
            title="Tester le son"
            style={{
              background: 'rgba(148,163,184,0.10)',
              border: '1px solid rgba(148,163,184,0.2)',
              borderRadius: 8, padding: '5px 12px', cursor: 'pointer',
              color: '#94a3b8', fontSize: '0.82rem', fontWeight: 600,
            }}
          >
            🔊 Test
          </button>
          <span className="medecin-nb-patients">
            {patients.length} patient{patients.length !== 1 ? 's' : ''} assigné{patients.length !== 1 ? 's' : ''}
          </span>
          <span className={`salle-ws-badge salle-ws-badge--${wsEtat}`}>
            {wsEtat === 'connecte'   && '● Connecté'}
            {wsEtat === 'connexion'  && '◌ Connexion…'}
            {wsEtat === 'deconnecte' && '● Déconnecté'}
          </span>
        </div>
      </header>

      {/* ── Hint activation son ──────────────────────────────────── */}
      {!sonDebloque && (
        <div className="medecin-audio-hint" role="status" aria-live="polite">
          🔈 Cliquez n'importe où pour activer le son des alertes
        </div>
      )}

      {/* ── Alertes critiques — banner modal persistant ──────────── */}
      {alertesCritiques.map(alerte => (
        <div key={alerte.patient_id} className="medecin-alerte-critique" role="alert">
          <div className="medecin-alerte-corps">
            <span className="medecin-alerte-icone">🚨</span>
            <div>
              <strong>ALERTE CRITIQUE — ESI {alerte.esi}</strong>
              <br />
              {alerte.prenom} {alerte.nom} — prise en charge immédiate requise
            </div>
          </div>
          <div className="medecin-alerte-actions">
            <button
              className="kiosk-btn medecin-btn-voir-alerte"
              onClick={() => ouvrirAlerte(alerte)}
            >
              Voir le dossier
            </button>
            <button
              className="medecin-btn-fermer-alerte"
              onClick={() => dismisserAlerte(alerte.patient_id)}
              aria-label="Fermer l'alerte"
            >
              ✕
            </button>
          </div>
        </div>
      ))}

      {/* ── Contenu principal ────────────────────────────────────── */}
      <main className="medecin-main">

        {chargement && (
          <div className="kiosk-center">
            <div className="kiosk-card kiosk-card--centree" style={{ maxWidth: 400 }}>
              <div className="kiosk-spinner" />
              <p className="kiosk-soustitre">Chargement des dossiers…</p>
            </div>
          </div>
        )}

        {!chargement && erreurChargement && (
          <div className="kiosk-center">
            <div className="kiosk-card kiosk-card--centree" style={{ maxWidth: 480 }}>
              <div className="kiosk-alerte" role="alert">{erreurChargement}</div>
              <button className="kiosk-btn kiosk-btn--primary" onClick={chargerPatients}>
                Réessayer
              </button>
            </div>
          </div>
        )}

        {!chargement && !erreurChargement && vue === 'liste' && (
          <>
            {/* Onglets attente / historique */}
            <div className="medecin-tabs">
              <button
                className={`medecin-tab${onglet === 'attente' ? ' medecin-tab--actif' : ''}`}
                onClick={() => setOnglet('attente')}
              >
                Patients en attente
                <span className="medecin-tab-badge">{patients.length}</span>
              </button>
              <button
                className={`medecin-tab${onglet === 'historique' ? ' medecin-tab--actif' : ''}`}
                onClick={() => { setOnglet('historique'); chargerHistorique() }}
              >
                Historique
                <span className="medecin-tab-badge">{historique.length}</span>
              </button>
            </div>

            {onglet === 'attente' && (
              <>
                <GraphiqueESI patients={patients} />
                <VueListe patients={patients} onOuvrirDossier={ouvrirDossier} />
              </>
            )}
            {onglet === 'historique' && (
              <VueHistorique
                historique={historique}
                chargement={chargHistorique}
                onVoirDossier={voirDossierHistorique}
              />
            )}
          </>
        )}

        {!chargement && !erreurChargement && vue === 'dossier' && patientActif && (
          <VueDossier
            patient={patientActif}
            medecinId={medecinId}
            enPriseEnCharge={enPriseEnCharge}
            onPriseEnCharge={() => handlePriseEnCharge(patientActif.patient_id)}
            onModifierESI={(esi, raison) => handleModifierESI(patientActif.patient_id, esi, raison)}
            onRetour={() => { setVue('liste'); setPatientActif(null) }}
          />
        )}

      </main>

      {/* ── Toasts (bas-droite) ──────────────────────────────────── */}
      {toasts.length > 0 && (
        <div className="salle-toasts" aria-live="polite">
          {toasts.map(t => (
            <div key={t.id} className={`salle-toast salle-toast--${t.type}`}>
              {t.message}
            </div>
          ))}
        </div>
      )}

      {/* ── Chat inter-médecins ──────────────────────────────────── */}
      <div className="medecin-chat-container">
        {chatOuvert && (
          <div className="medecin-chat-panel">
            <div className="medecin-chat-header">
              <span className="medecin-chat-titre">
                💬 Dr. {autreMedecinId === 'M1' ? 'El Amrani' : 'Bensouda'}
              </span>
              <button
                className="medecin-chat-fermer"
                onClick={basculerChat}
                aria-label="Fermer le chat"
              >
                ✕
              </button>
            </div>

            <div className="medecin-chat-messages">
              {chatMessages.length === 0 && (
                <p className="medecin-chat-vide">Aucun message — démarrez la conversation</p>
              )}
              {chatMessages.map((msg, i) => (
                <div
                  key={i}
                  className={`chat-bubble chat-bubble--${msg.de === medecinId ? 'moi' : 'autre'}`}
                >
                  <div className="chat-bubble-meta">
                    <span className="chat-bubble-emetteur">Dr. {msg.de}</span>
                    <span className="chat-bubble-heure">{msg.horodatage}</span>
                  </div>
                  <div className="chat-bubble-texte">{msg.texte}</div>
                </div>
              ))}
              <div ref={chatFinRef} />
            </div>

            <div className="medecin-chat-saisie">
              <input
                type="text"
                className="medecin-chat-input"
                placeholder="Message…"
                value={chatInput}
                onChange={e => setChatInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && envoyerMessageChat()}
                maxLength={500}
              />
              <button
                className="medecin-chat-envoyer"
                onClick={envoyerMessageChat}
              >
                Envoyer
              </button>
            </div>
          </div>
        )}

        <button
          className="medecin-chat-toggle"
          onClick={basculerChat}
          aria-label={chatOuvert ? 'Fermer le chat' : 'Ouvrir le chat inter-médecins'}
        >
          💬
          {chatNonLus > 0 && !chatOuvert && (
            <span className="chat-badge">{chatNonLus}</span>
          )}
        </button>
      </div>

    </div>
  )
}

// ═════════════════════════════════════════════════════════════════════════════
// Vue liste — grille de cartes patients
// ═════════════════════════════════════════════════════════════════════════════
function VueListe({ patients, onOuvrirDossier }) {
  if (patients.length === 0) {
    return (
      <div className="medecin-vide">
        <span className="salle-vide-icone" aria-hidden="true">✅</span>
        <p className="salle-vide-texte">Aucun patient assigné</p>
      </div>
    )
  }

  return (
    <div className="medecin-patients-grille">
      {patients.map(p => (
        <CartePatient key={p.patient_id} patient={p} onOuvrirDossier={onOuvrirDossier} />
      ))}
    </div>
  )
}

// ── Graphique ESI temps réel (barres animées) ─────────────────────────────────
const ESI_COLORS = { 1:'#ef4444', 2:'#f97316', 3:'#fbbf24', 4:'#34d399', 5:'#38bdf8' }

function GraphiqueESI({ patients }) {
  if (!patients.length) return null
  const counts = { 1:0, 2:0, 3:0, 4:0, 5:0 }
  patients.forEach(p => { const e = p.esi_predit ?? 5; counts[e] = (counts[e] || 0) + 1 })
  const max = Math.max(...Object.values(counts), 1)
  return (
    <div style={{ padding:'0 16px 10px', display:'flex', flexDirection:'column', gap:4 }}>
      <span style={{ fontSize:'0.7rem', color:'rgba(255,255,255,0.38)', textTransform:'uppercase', letterSpacing:'0.1em' }}>
        Répartition ESI
      </span>
      <div className="medecin-esi-chart">
        {[1,2,3,4,5].map(e => (
          <div key={e} className="medecin-esi-bar-col">
            <span className="medecin-esi-chart-num">{counts[e]}</span>
            <div
              className="medecin-esi-bar"
              style={{
                height: `${Math.max(4, (counts[e]/max)*64)}px`,
                background: ESI_COLORS[e],
                animationDelay: `${(e-1)*0.1}s`,
                opacity: counts[e] ? 1 : 0.25,
              }}
            />
            <span className="medecin-esi-chart-label">ESI{e}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Carte résumé patient ──────────────────────────────────────────────────────
function CartePatient({ patient, onOuvrirDossier }) {
  const esi = patient.esi_predit ?? 5
  const cfg = ESI_CFG[esi] ?? ESI_CFG[5]
  const attente = patient.temps_attente_actuel ?? patient.temps_attente_min

  // Détecte si une constante critique est présente
  const alerteVitale = patient.constantes && (
    evaluerCouleur('spo2',       patient.constantes.spo2)        === 'rouge' ||
    evaluerCouleur('heart_rate', patient.constantes.heart_rate)  === 'rouge' ||
    evaluerCouleur('temperature',patient.constantes.temperature) === 'rouge' ||
    evaluerCouleur('bp_systolic',patient.constantes.bp_systolic) === 'rouge'
  )

  return (
    <div
      className="medecin-carte medecin-patient-card"
      data-esi={esi}
      style={{ borderLeftColor: cfg.bordure, background: cfg.fond }}
      role="article"
      aria-label={`Patient ${patient.prenom} ${patient.nom} — ESI ${esi}`}
    >
      {/* Ligne ESI + identité */}
      <div className="medecin-carte-top">
        <span className="medecin-carte-esi" style={{ borderColor: cfg.bordure, color: cfg.texte }}>
          {esi}
        </span>
        <div className="medecin-carte-identite">
          <span className="medecin-carte-nom">{patient.prenom} {patient.nom}</span>
          <span className="medecin-carte-sous">
            {patient.age} ans · {patient.sexe} · Arrivé à {patient.heure_arrivee}
          </span>
        </div>
        {alerteVitale && (
          <span className="medecin-badge-alerte" title="Constante critique">⚠️</span>
        )}
      </div>

      {/* Niveau urgence + ticket */}
      <div className="medecin-carte-meta">
        <span style={{ color: cfg.texte, fontWeight: 600 }}>{patient.niveau_urgence}</span>
        <span className="medecin-carte-ticket">{patient.patient_id}</span>
      </div>

      {/* Temps d'attente + position */}
      <div className="medecin-carte-meta">
        <span className="medecin-carte-info">
          📍 Position {patient.position_file ?? '—'} en file
        </span>
        {attente != null && (
          <span className="medecin-carte-info">
            ⏱ {Math.round(attente)} min d'attente
          </span>
        )}
      </div>

      {/* Aperçu symptômes */}
      {patient.symptom_text && (
        <p className="medecin-carte-symptomes">
          {patient.symptom_text.length > 90
            ? `${patient.symptom_text.slice(0, 90)}…`
            : patient.symptom_text
          }
        </p>
      )}

      {/* Bouton dossier */}
      <button
        className="kiosk-btn kiosk-btn--primary medecin-carte-btn"
        onClick={() => onOuvrirDossier(patient)}
      >
        Voir le dossier complet →
      </button>
    </div>
  )
}

// ═════════════════════════════════════════════════════════════════════════════
// Vue dossier — rapport médical complet
// ═════════════════════════════════════════════════════════════════════════════
function VueDossier({ patient, medecinId, enPriseEnCharge, onPriseEnCharge, onModifierESI, onRetour }) {
  const esi = patient.esi_predit ?? 5
  const cfg = ESI_CFG[esi] ?? ESI_CFG[5]
  const [esiChoisi, setEsiChoisi]   = useState(esi)
  const [raison, setRaison]         = useState('')
  const [enMod, setEnMod]           = useState(false)

  const nlpActifs = Object.keys(patient.features_nlp_actives ?? {}).filter(
    k => patient.features_nlp_actives[k] > 0 && NLP_LABELS[k]
  )

  const zonesLabels = (patient.zones_corps ?? []).map(id => ZONES_MAP[id] ?? id)

  return (
    <div className="dossier-layout">

      {/* ── Barre de navigation ──────────────────────────────────── */}
      <div className="dossier-nav">
        <button className="kiosk-btn kiosk-btn--secondary dossier-btn-retour" onClick={onRetour}>
          ← Retour à la liste
        </button>
        <span className="dossier-ticket">{patient.patient_id}</span>
      </div>

      {/* ── Badge ESI + Niveau urgence ───────────────────────────── */}
      <div
        className="dossier-esi-bande"
        style={{ background: cfg.fond, borderColor: cfg.bordure }}
      >
        <span className="dossier-esi-numero" style={{ color: cfg.texte }}>{esi}</span>
        <div>
          <div className="dossier-esi-libelle" style={{ color: cfg.texte }}>
            {cfg.libelle}
          </div>
          <div className="dossier-esi-urgence">{patient.niveau_urgence}</div>
        </div>
        <div className="dossier-esi-meta">
          <span>Confiance modèle : {patient.confiance_modele != null
            ? `${Math.round(patient.confiance_modele)} %`
            : '—'
          }</span>
          <span>Score priorité : {patient.score_priorite ?? '—'}</span>
        </div>
      </div>

      {/* ── Grille principale ─────────────────────────────────────── */}
      <div className="dossier-grille-principale">

        {/* ── COLONNE GAUCHE ─────────────────────────────────────── */}
        <div className="dossier-colonne">

          {/* Identité */}
          <section className="dossier-section">
            <h3 className="dossier-section-titre">Identité</h3>
            <div className="dossier-meta-grille">
              <InfoLigne label="Nom"          valeur={`${patient.prenom} ${patient.nom}`} />
              <InfoLigne label="Âge"          valeur={`${patient.age} ans`} />
              <InfoLigne label="Sexe"         valeur={patient.sexe} />
              <InfoLigne label="Arrivée"      valeur={patient.heure_arrivee} />
              <InfoLigne label="Position file" valeur={`${patient.position_file ?? '—'}`} />
              <InfoLigne label="En attente"
                valeur={patient.temps_attente_actuel != null
                  ? `${Math.round(patient.temps_attente_actuel)} min`
                  : '—'
                }
              />
            </div>
          </section>

          {/* Symptômes */}
          <section className="dossier-section">
            <h3 className="dossier-section-titre">Symptômes déclarés</h3>
            {patient.symptom_text ? (
              <p className="dossier-symptome-texte">« {patient.symptom_text} »</p>
            ) : (
              <p className="kiosk-note">Aucune description saisie</p>
            )}
            {zonesLabels.length > 0 && (
              <div className="dossier-zones">
                {zonesLabels.map((z, i) => (
                  <span key={i} className="dossier-zone-tag">{z}</span>
                ))}
              </div>
            )}
          </section>

          {/* Explications décision ESI */}
          {(patient.explications ?? []).length > 0 && (
            <section className="dossier-section">
              <h3 className="dossier-section-titre">Facteurs ayant influencé l'ESI</h3>
              <ul className="dossier-explications">
                {patient.explications.map((e, i) => (
                  <li key={i} className="dossier-expl-item">
                    <span className="dossier-expl-check">✓</span> {e}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Analyse NLP */}
          {nlpActifs.length > 0 && (
            <section className="dossier-section">
              <h3 className="dossier-section-titre">Signaux cliniques détectés (IA)</h3>
              <div className="dossier-nlp-tags">
                {nlpActifs.map(k => (
                  <span key={k} className="dossier-nlp-tag">
                    {NLP_LABELS[k]}
                  </span>
                ))}
              </div>
            </section>
          )}

        </div>

        {/* ── COLONNE DROITE ────────────────────────────────────────── */}
        <div className="dossier-colonne">

          {/* Constantes vitales */}
          <section className="dossier-section">
            <h3 className="dossier-section-titre">Constantes vitales</h3>
            {patient.constantes
              ? <BiometrieDisplay constantes={patient.constantes} enCours={false} />
              : <p className="kiosk-note">Constantes non disponibles</p>
            }
          </section>

          {/* Rapport horodatage */}
          {patient.horodatage_rapport && (
            <p className="dossier-horodatage">
              Rapport généré le {patient.horodatage_rapport}
            </p>
          )}

        </div>
      </div>

      {/* ── Modifier priorité ESI manuellement ──────────────────── */}
      {!patient._depuis_historique && (
        <section className="dossier-section dossier-esi-override">
          <h3 className="dossier-section-titre">Modifier la priorité ESI</h3>
          <div className="esi-override-form">
            <div className="esi-override-selects">
              {[1, 2, 3, 4, 5].map(n => {
                const c = ESI_CFG[n]
                return (
                  <button
                    key={n}
                    className={`esi-override-btn${esiChoisi === n ? ' esi-override-btn--actif' : ''}`}
                    style={{
                      borderColor: esiChoisi === n ? c.bordure : 'rgba(255,255,255,0.1)',
                      color: esiChoisi === n ? c.texte : 'rgba(255,255,255,0.5)',
                      background: esiChoisi === n ? c.fond : 'transparent',
                    }}
                    onClick={() => setEsiChoisi(n)}
                  >
                    ESI {n}
                  </button>
                )
              })}
            </div>
            <input
              className="esi-override-raison"
              type="text"
              placeholder="Raison (optionnel)"
              value={raison}
              onChange={e => setRaison(e.target.value)}
              maxLength={120}
            />
            <button
              className="kiosk-btn kiosk-btn--secondary esi-override-appliquer"
              disabled={enMod || esiChoisi === esi}
              onClick={async () => {
                setEnMod(true)
                await onModifierESI(esiChoisi, raison)
                setRaison('')
                setEnMod(false)
              }}
            >
              {enMod ? '…' : `Appliquer ESI ${esiChoisi}`}
            </button>
          </div>

          {/* Historique des modifications */}
          {patient.historique_esi?.length > 0 && (
            <div className="esi-historique">
              <p className="esi-historique-titre">Modifications ESI</p>
              {patient.historique_esi.map((h, i) => (
                <div key={i} className="esi-historique-ligne">
                  <span className="esi-histo-heure">{h.heure}</span>
                  <span>ESI {h.ancien_esi} → {h.nouvel_esi}</span>
                  {h.raison && <span className="esi-histo-raison"> — {h.raison}</span>}
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* ── Bouton "Pris en charge" (masqué pour l'historique) ──── */}
      {!patient._depuis_historique && (
        <div className="dossier-action">
          <button
            className="kiosk-btn dossier-btn-pec"
            style={{
              background: cfg.fond,
              border: `2px solid ${cfg.bordure}`,
              color: cfg.texte,
            }}
            onClick={onPriseEnCharge}
            disabled={enPriseEnCharge}
          >
            {enPriseEnCharge
              ? <><span className="kiosk-spinner" style={{ width: 24, height: 24, borderWidth: 3 }} /> En cours…</>
              : '✓ Marquer comme pris en charge'
            }
          </button>
        </div>
      )}

    </div>
  )
}

// ═════════════════════════════════════════════════════════════════════════════
// Vue historique — tableau des patients traités
// ═════════════════════════════════════════════════════════════════════════════
function VueHistorique({ historique, chargement, onVoirDossier }) {
  if (chargement) {
    return (
      <div className="kiosk-center" style={{ padding: 40 }}>
        <div className="kiosk-spinner" />
      </div>
    )
  }
  if (historique.length === 0) {
    return (
      <div className="medecin-vide">
        <span className="salle-vide-icone" aria-hidden="true">📋</span>
        <p className="salle-vide-texte">Aucun patient traité aujourd'hui</p>
      </div>
    )
  }
  return (
    <div className="medecin-historique">
      <table className="historique-table">
        <thead>
          <tr>
            <th>Patient</th>
            <th>ESI</th>
            <th>Arrivée</th>
            <th>Pris en charge</th>
            <th>Attente</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {historique.map(h => {
            const esi = h.esi
            const cfg = ESI_CFG[esi] ?? ESI_CFG[5]
            return (
              <tr key={h.session_id || h.patient_id_display} className="historique-ligne">
                <td className="historique-cell historique-cell--nom">
                  {h.prenom} {h.nom}
                  <span className="historique-age">{h.age} ans</span>
                </td>
                <td className="historique-cell">
                  <span className="medecin-carte-esi" style={{ borderColor: cfg.bordure, color: cfg.texte }}>
                    {esi}
                  </span>
                </td>
                <td className="historique-cell">{h.heure_arrivee}</td>
                <td className="historique-cell">{h.heure_prise_en_charge}</td>
                <td className="historique-cell">
                  {h.duree_attente_minutes != null && h.duree_attente_minutes !== '?'
                    ? `${h.duree_attente_minutes} min`
                    : '—'}
                </td>
                <td className="historique-cell">
                  <button
                    className="kiosk-btn kiosk-btn--secondary historique-btn-dossier"
                    onClick={() => onVoirDossier(h)}
                  >
                    Voir dossier
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ── Ligne d'information identité ──────────────────────────────────────────────
function InfoLigne({ label, valeur }) {
  return (
    <div className="dossier-info-ligne">
      <span className="dossier-info-label">{label}</span>
      <span className="dossier-info-valeur">{valeur ?? '—'}</span>
    </div>
  )
}
