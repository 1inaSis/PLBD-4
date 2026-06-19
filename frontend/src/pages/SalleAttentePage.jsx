// Écran salle d'attente — grand affichage public (TV / moniteur mural)
//
// Connexion WebSocket ?role=salle :
//   - À la connexion : le serveur envoie immédiatement file_mise_a_jour
//   - Mise à jour automatique à chaque action clinique (triage, prise en charge, etc.)
//   - Ping toutes les 30 s pour maintenir la connexion
//   - Reconnexion automatique après 5 s en cas de coupure

import { useState, useEffect, useRef, useCallback } from 'react'
import { creerWebSocket, envoyerCommande } from '../services/websocket'
import { reinitialiserFile, getStats } from '../services/api'
import BoutonPleinEcran from '../components/BoutonPleinEcran'
import '../styles/kiosk.css'

// ── Calcul temps d'attente depuis heure "HH:MM" ───────────────────────────────
function minutesEcoulees(heureArrivee) {
  if (!heureArrivee) return null
  const [h, m] = heureArrivee.split(':').map(Number)
  const arrivee = new Date()
  arrivee.setHours(h, m, 0, 0)
  const diff = Math.floor((Date.now() - arrivee.getTime()) / 60000)
  return diff < 0 ? 0 : diff
}

function classeAttente(min) {
  if (min == null) return ''
  if (min < 15) return 'attente-vert'
  if (min < 30) return 'attente-orange'
  return 'attente-rouge'
}

// ── Configuration des niveaux ESI (couleurs + libellés) ──────────────────────
const ESI_CONFIG = {
  1: { libelle: 'CRITIQUE',    fond: 'rgba(239,68,68,0.14)',   bordure: '#ef4444', texte: '#f87171' },
  2: { libelle: 'TRÈS URGENT', fond: 'rgba(249,115,22,0.13)',  bordure: '#f97316', texte: '#fb923c' },
  3: { libelle: 'URGENT',      fond: 'rgba(251,191,36,0.11)',  bordure: '#fbbf24', texte: '#fbbf24' },
  4: { libelle: 'SEMI-URGENT', fond: 'rgba(52,211,153,0.10)',  bordure: '#34d399', texte: '#34d399' },
  5: { libelle: 'NON URGENT',  fond: 'rgba(56,189,248,0.09)',  bordure: '#38bdf8', texte: '#38bdf8' },
}

// Noms des médecins (correspondance identique au backend MEDECINS dict)
const NOM_MEDECIN = {
  M1: 'Dr. El Amrani',
  M2: 'Dr. Bensouda',
}

// ── Compteur d'ID pour les toasts ─────────────────────────────────────────────
let _toastId = 0

// ── Heure locale HH:MM ────────────────────────────────────────────────────────
function heureLocale() {
  return new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

// ═════════════════════════════════════════════════════════════════════════════
export default function SalleAttentePage() {
  const [file, setFile]             = useState([])
  const [alertes, setAlertes]       = useState([])
  const [horodatage, setHorodatage] = useState('')
  const [nbPatients, setNbPatients] = useState(0)
  const [toasts, setToasts]         = useState([])
  const [wsEtat, setWsEtat]         = useState('connexion')  // connexion | connecte | deconnecte
  const [heureLive, setHeureLive]   = useState(heureLocale())
  const [resetEnCours, setResetEnCours] = useState(false)
  const [tempsCourant, setTempsCourant] = useState(Date.now())
  const [degradBanner, setDegradBanner] = useState(null)
  const [stats, setStats]           = useState({
    patients_en_attente: 0,
    patients_traites_aujourd_hui: 0,
    temps_moyen_attente_minutes: 0,
    esi_critique_actifs: 0,
  })

  const wsRef    = useRef(null)
  const pingRef  = useRef(null)
  const monteRef = useRef(true)   // false après le démontage du composant

  // ── Horloge en direct (toutes les 10 s) ────────────────────────────────────
  useEffect(() => {
    const id = setInterval(() => setHeureLive(heureLocale()), 10_000)
    return () => clearInterval(id)
  }, [])

  // ── Stats + temps d'attente en direct (toutes les 30 s) ─────────────────────
  useEffect(() => {
    const rafraichir = async () => {
      try {
        const s = await getStats()
        if (monteRef.current) setStats(s)
      } catch { /* silencieux */ }
      if (monteRef.current) setTempsCourant(Date.now())
    }
    rafraichir()
    const id = setInterval(rafraichir, 30_000)
    return () => clearInterval(id)
  }, [])

  // ── Afficher une notification toast (5 s) ─────────────────────────────────
  const ajouterToast = useCallback((message, type = 'info') => {
    const id = ++_toastId
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => {
      if (monteRef.current) setToasts(prev => prev.filter(t => t.id !== id))
    }, 5000)
  }, [])

  // ── Réinitialisation de la file (admin démo) ────────────────────────────────
  const reinitialiser = async () => {
    if (!window.confirm('Confirmer la réinitialisation ? Tous les patients seront supprimés.')) return
    setResetEnCours(true)
    try {
      await reinitialiserFile()
    } catch {
      alert('Erreur lors de la réinitialisation')
    } finally {
      setResetEnCours(false)
    }
  }

  // ── Gestionnaire d'événements WebSocket ────────────────────────────────────
  const gererEvenement = useCallback((msg) => {
    const { event, data } = msg

    switch (event) {

      // Remplacement complet de la file (déclenché à la connexion + toutes actions)
      case 'file_mise_a_jour':
        setWsEtat('connecte')
        setFile(data.file      ?? [])
        setAlertes(data.alertes ?? [])
        setHorodatage(data.horodatage ?? '')
        setNbPatients(data.nb_patients ?? 0)
        break

      // Nouveau patient triage → toast d'information
      case 'nouveau_patient':
        ajouterToast(
          `Nouveau patient : ${data.prenom} ${data.nom} — ESI ${data.esi}`,
          'nouveau',
        )
        break

      // Patient pris en charge → toast de confirmation
      case 'patient_pris_en_charge':
        ajouterToast(
          `Pris en charge par ${data.medecin} à ${data.heure}`,
          'prise_en_charge',
        )
        break

      // Dégradation clinique → bannière + toast
      case 'degradation':
        setDegradBanner({
          nom: data.nom,
          ancien: data.ancien_esi,
          nouvel: data.nouvel_esi,
          auto: data.auto,
        })
        setTimeout(() => {
          if (monteRef.current) setDegradBanner(null)
        }, 10_000)
        ajouterToast(
          `⚠️ Dégradation : ${data.nom} — ESI ${data.ancien_esi} → ${data.nouvel_esi}`,
          'degradation',
        )
        break

      default:
        break
    }
  }, [ajouterToast])

  // ── Connexion WebSocket avec reconnexion automatique ───────────────────────
  useEffect(() => {
    monteRef.current = true

    const connecter = () => {
      if (!monteRef.current) return

      setWsEtat('connexion')

      const ws = creerWebSocket('salle', (msg) => {
        if (monteRef.current) gererEvenement(msg)
      })

      ws.onopen = () => {
        if (!monteRef.current) return
        setWsEtat('connecte')
        // Ping toutes les 30 s pour maintenir la connexion
        pingRef.current = setInterval(() => {
          envoyerCommande(ws, 'ping')
        }, 30_000)
      }

      ws.onclose = () => {
        if (!monteRef.current) return
        setWsEtat('deconnecte')
        clearInterval(pingRef.current)
        // Reconnexion après 5 s
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
  }, [gererEvenement])

  // ── Rendu ────────────────────────────────────────────────────────────────────
  return (
    <div className="salle-shell">

      {/* ── En-tête barre supérieure ─────────────────────────────── */}
      <header className="salle-header">
        <div className="salle-header-gauche">
          <span className="salle-nom-hopital">🏥 HealthGate — Salle d'attente</span>
          <span className="salle-sous-titre">
            {horodatage ? `Mis à jour à ${horodatage}` : 'Connexion au serveur…'}
          </span>
        </div>
        <div className="salle-header-droite">
          <BoutonPleinEcran />
          <div className="salle-header-infos">
            <span className="salle-heure">{heureLive}</span>
            <span className={`salle-ws-badge salle-ws-badge--${wsEtat}`}>
              {wsEtat === 'connecte'   && '● Connecté'}
              {wsEtat === 'connexion'  && '◌ Connexion…'}
              {wsEtat === 'deconnecte' && '● Déconnecté'}
            </span>
          </div>
          <img
            src="/logo-ecc.png"
            alt="École Centrale Casablanca"
            className="salle-logo-ecc"
            onError={(e) => { e.currentTarget.style.display = 'none' }}
          />
        </div>
      </header>

      {/* ── Bande statistiques temps réel ────────────────────────── */}
      <div className="salle-stats-bande">
        <div className="salle-stat-item">
          <span className="salle-stat-valeur">{nbPatients}</span>
          <span className="salle-stat-label">En attente</span>
        </div>
        <div className="salle-stat-sep" />
        <div className="salle-stat-item">
          <span className="salle-stat-valeur">{stats.patients_traites_aujourd_hui}</span>
          <span className="salle-stat-label">Traités aujourd'hui</span>
        </div>
        <div className="salle-stat-sep" />
        <div className="salle-stat-item">
          <span className="salle-stat-valeur">
            {stats.temps_moyen_attente_minutes > 0 ? `${stats.temps_moyen_attente_minutes} min` : '—'}
          </span>
          <span className="salle-stat-label">Temps moyen</span>
        </div>
        {stats.esi_critique_actifs > 0 && (
          <>
            <div className="salle-stat-sep" />
            <div className="salle-stat-badge-critique">
              🚨 {stats.esi_critique_actifs} ESI CRITIQUE{stats.esi_critique_actifs > 1 ? 'S' : ''}
            </div>
          </>
        )}
      </div>

      {/* ── Alertes priorité maximale (ESI 1 / 2 actifs) ────────── */}
      {alertes.length > 0 && (
        <div className="salle-alertes" role="alert" aria-live="assertive">
          {alertes.map(a => (
            <div key={a.patient_id} className="salle-alerte-critique">
              🚨 PRIORITÉ MAXIMALE — {a.prenom} {a.nom} · ESI {a.esi_actuel ?? a.esi_predit}
            </div>
          ))}
        </div>
      )}

      {/* ── Bannière dégradation automatique ───────────────────── */}
      {degradBanner && (
        <div className="salle-degradation-banner" role="alert">
          ⚠️ Dégradation{degradBanner.auto ? ' automatique' : ''} — {degradBanner.nom} : ESI {degradBanner.ancien} → {degradBanner.nouvel}
          <button
            onClick={() => setDegradBanner(null)}
            aria-label="Fermer"
            style={{
              marginLeft: 16, background: 'transparent', border: 'none',
              color: 'inherit', cursor: 'pointer', fontSize: '1rem',
            }}
          >✕</button>
        </div>
      )}

      {/* ── Liste des patients ───────────────────────────────────── */}
      <main className="salle-main">
        {file.length === 0 ? (
          <div className="salle-vide">
            <span className="salle-vide-icone" aria-hidden="true">🏥</span>
            <p className="salle-vide-texte">Aucun patient en salle d'attente</p>
          </div>
        ) : (
          <div className="salle-liste" role="list">
            {/* Ligne d'en-tête colonnes */}
            <div className="salle-ligne salle-ligne--entete" aria-hidden="true">
              <span className="salle-col-pos">N°</span>
              <span className="salle-col-esi">Priorité</span>
              <span className="salle-col-ticket">Ticket</span>
              <span className="salle-col-patient">Patient</span>
              <span className="salle-col-attente">Attente</span>
              <span className="salle-col-medecin">Médecin</span>
            </div>

            {/* Une ligne par patient */}
            {file.map(p => (
              <LignePatient key={p.patient_id} patient={p} tempsCourant={tempsCourant} />
            ))}
          </div>
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

      {/* ── Bouton admin réinitialisation (bas-gauche, discret) ──── */}
      <button
        onClick={reinitialiser}
        disabled={resetEnCours}
        style={{
          position: 'fixed', bottom: 12, left: 12,
          padding: '4px 10px', fontSize: '0.72rem',
          background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.15)',
          borderRadius: 6, color: 'rgba(255,255,255,0.4)', cursor: 'pointer',
          opacity: resetEnCours ? 0.4 : 1,
        }}
      >
        {resetEnCours ? 'Réinitialisation…' : 'Réinitialiser la file'}
      </button>

    </div>
  )
}

// ═════════════════════════════════════════════════════════════════════════════
// Ligne d'un patient dans la file
// ═════════════════════════════════════════════════════════════════════════════
function LignePatient({ patient, tempsCourant }) {
  const esi     = patient.esi_actuel ?? patient.esi_predit ?? 5
  const cfg     = ESI_CONFIG[esi]   ?? ESI_CONFIG[5]
  const medecin = NOM_MEDECIN[patient.medecin_id] ?? '—'
  // Temps d'attente calculé en direct depuis heure_arrivee
  // tempsCourant est mis à jour toutes les 30s pour forcer le re-render
  void tempsCourant
  const attente = minutesEcoulees(patient.heure_arrivee)
  const classeA = classeAttente(attente)

  return (
    <div
      className="salle-ligne"
      role="listitem"
      style={{ background: cfg.fond, borderLeftColor: cfg.bordure }}
      aria-label={`Position ${patient.position} — ESI ${esi} — ${patient.prenom}`}
    >
      {/* Position dans la file */}
      <span className="salle-col-pos">
        <span className="salle-pos-bulle">{patient.position}</span>
      </span>

      {/* Badge ESI + libellé */}
      <span className="salle-col-esi">
        <span
          className="salle-esi-badge"
          style={{ borderColor: cfg.bordure, color: cfg.texte }}
        >
          {esi}
        </span>
        <span className="salle-esi-libelle" style={{ color: cfg.texte }}>
          {cfg.libelle}
        </span>
      </span>

      {/* Numéro de ticket */}
      <span className="salle-col-ticket salle-ticket-id">{patient.patient_id}</span>

      {/* Prénom du patient (affiché publiquement) */}
      <span className="salle-col-patient">{patient.prenom || '—'}</span>

      {/* Temps d'attente en direct depuis l'arrivée */}
      <span className={`salle-col-attente ${classeA}`}>
        {attente != null
          ? `${attente} min`
          : patient.heure_arrivee
            ? `Arrivé à ${patient.heure_arrivee}`
            : '—'
        }
      </span>

      {/* Médecin assigné */}
      <span className="salle-col-medecin">{medecin}</span>
    </div>
  )
}
