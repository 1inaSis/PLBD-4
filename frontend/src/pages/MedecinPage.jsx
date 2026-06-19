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
import { getPatientsMedecin, prendreEnCharge } from '../services/api'
import { creerWebSocket, envoyerCommande } from '../services/websocket'
import BiometrieDisplay, { evaluerCouleur } from '../components/BiometrieDisplay'
import { ZONES_MAP } from '../components/CorpsHumain'
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

// ═════════════════════════════════════════════════════════════════════════════
export default function MedecinPage() {
  const { id: medecinId } = useParams()   // 'M1' ou 'M2'

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

  const wsRef    = useRef(null)
  const pingRef  = useRef(null)
  const monteRef = useRef(true)

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
        }
        break

      // ALERTE CRITIQUE (ESI ≤ 2) — modal persistant, envoyé au médecin assigné uniquement
      case 'alerte_critique':
        setAlertesCritiques(prev => {
          // Évite les doublons par patient_id
          if (prev.some(a => a.patient_id === data.patient_id)) return prev
          return [...prev, data]
        })
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
  }, [medecinId, chargerPatients, ajouterToast])

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
          <VueListe
            patients={patients}
            onOuvrirDossier={ouvrirDossier}
          />
        )}

        {!chargement && !erreurChargement && vue === 'dossier' && patientActif && (
          <VueDossier
            patient={patientActif}
            medecinId={medecinId}
            enPriseEnCharge={enPriseEnCharge}
            onPriseEnCharge={() => handlePriseEnCharge(patientActif.patient_id)}
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
      className="medecin-carte"
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
function VueDossier({ patient, medecinId, enPriseEnCharge, onPriseEnCharge, onRetour }) {
  const esi = patient.esi_predit ?? 5
  const cfg = ESI_CFG[esi] ?? ESI_CFG[5]

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

      {/* ── Bouton "Pris en charge" ──────────────────────────────── */}
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
