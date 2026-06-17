// Étape 3 / 5 — Mesure séquentielle des constantes vitales
//
// Flux par étape :
//   ATTENTE → (valeur valide) → COMPLET
//   ATTENTE → (null retourné) → message + bouton Réessayer
//   ATTENTE → (30s sans valeur) → valeur simulée injectée + COMPLET auto (3s)
//
// 3 étapes : Température → Oxymètre (SpO₂ + FC) → Tension (simulée client)
// Après les 3 étapes → RECAP (BiometrieDisplay complet + "Continuer")

import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePatient } from '../context/PatientContext'
import { demarrerArduino, arreterArduino, mesurerConstante } from '../services/api'
import IndicateurEtape from '../components/IndicateurEtape'
import BiometrieDisplay, { evaluerCouleur, LIBELLES_COULEUR } from '../components/BiometrieDisplay'
import {
  IllustrationThermometre,
  IllustrationSpo2,
  IllustrationTension,
} from '../components/IllustrationsGestes'
import '../styles/kiosk.css'

const PRIORITE_COULEUR = { rouge: 5, orange: 4, jaune: 3, vert: 2, gris: 1 }

function pireCouleur(...couleurs) {
  return couleurs.reduce(
    (pire, c) => (PRIORITE_COULEUR[c] ?? 0) > (PRIORITE_COULEUR[pire] ?? 0) ? c : pire,
    'gris',
  )
}

// ── 3 étapes de mesure ────────────────────────────────────────────────────────
const ETAPES = [
  {
    cle:          'temperature',
    typeMesure:   'temperature',
    label:        'Température',
    instruction:  'Placez le capteur thermique sur votre front et restez immobile.',
    messageNull:  'Veuillez pointer le capteur face à votre front à 2-3 cm',
    unite:        '°C',
    icone:        '🌡️',
    illustration: IllustrationThermometre,
    formatter:    (v) => Number(v).toFixed(1),
    fallback:     { temperature: 36.5 },
  },

  {
    cle:          'spo2',
    typeMesure:   'spo2',
    double:       true,
    label:        'Oxymétrie de pouls',
    instruction:  'Placez votre index sur le capteur de la borne et restez immobile.',
    messageNull:  'Positionnez bien votre index sur le capteur et maintenez immobile',
    icone:        '🫁',
    illustration: IllustrationSpo2,
    valeurs: [
      { cle: 'spo2',       label: 'SpO₂',               unite: '%',   formatter: (v) => Number(v).toFixed(1) },
      { cle: 'heart_rate', label: 'Fréquence cardiaque', unite: 'bpm', formatter: (v) => Math.round(Number(v)) },
    ],
    fallback: { spo2: 97.0, heart_rate: 75 },
  },

  {
    cle:          'bp_systolic',
    typeMesure:   'tension',
    simulee:      true,
    label:        'Tension artérielle',
    unite:        'mmHg',
    icone:        '💉',
    illustration: IllustrationTension,
    formatter:    (v, all) => `${Math.round(v)} / ${Math.round(all?.bp_diastolic ?? 0)}`,
  },
]

const CLES_VITALES      = ['temperature', 'spo2', 'heart_rate', 'bp_systolic']
const TIMEOUT_MESURE_MS = 30_000   // 30s avant injection valeur simulée

const PHASE = { MESURE: 'mesure', RECAP: 'recap' }
const ETAT  = { ATTENTE: 'attente', COMPLET: 'complet' }

function simulerTension() {
  const sys = Math.round(110 + Math.random() * 30)
  const dia = Math.round(sys * (0.55 + Math.random() * 0.13))
  return { bp_systolic: sys, bp_diastolic: dia }
}

// ═════════════════════════════════════════════════════════════════════════════
export default function ConstantesPage() {
  const navigate = useNavigate()
  const { patient, setConstantes } = usePatient()

  const [phase, setPhase]                = useState(PHASE.MESURE)
  const [indexEtape, setIndexEtape]      = useState(0)
  const [etat, setEtat]                  = useState(ETAT.ATTENTE)
  const [constantes, setConstantesLocal] = useState({})
  const [erreur, setErreur]              = useState(null)
  // 'null' = capteur non pointé  |  'timeout' = 30s dépassés  |  null = RAS
  const [messageCapture, setMessageCapture] = useState(null)
  const [tentative, setTentative]           = useState(0)

  const enFetchRef = useRef(false)

  const etapeActuelle  = ETAPES[indexEtape]
  const valeurActuelle = constantes?.[etapeActuelle?.cle]

  // ── Lifecycle Arduino ────────────────────────────────────────────────────────
  useEffect(() => {
    demarrerArduino().catch(() => {})
    return () => { arreterArduino() }
  }, [])

  // ── Mesure Arduino (ignorée pour les étapes simulées) ───────────────────────
  useEffect(() => {
    if (etat !== ETAT.ATTENTE || enFetchRef.current || etapeActuelle.simulee) return

    setMessageCapture(null)
    enFetchRef.current = true
    mesurerConstante(etapeActuelle.typeMesure, patient.session_id)
      .then(res => {
        const nouvelles = {}
        Object.entries(res.constantes ?? {}).forEach(([k, v]) => {
          if (v != null) nouvelles[k] = v
        })
        // Valeur primaire toujours null → capteur non pointé
        if (nouvelles[etapeActuelle.cle] == null) {
          setMessageCapture('null')
        } else {
          setConstantesLocal(prev => ({ ...prev, ...nouvelles }))
          setErreur(null)
        }
      })
      .catch(err => setErreur(`Erreur capteurs : ${err.message}`))
      .finally(() => { enFetchRef.current = false })

  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [etat, indexEtape, tentative])

  // ── Timeout 30s : injecte valeur simulée si toujours en attente ─────────────
  useEffect(() => {
    if (etat !== ETAT.ATTENTE || etapeActuelle.simulee) return

    const timer = setTimeout(() => {
      setConstantesLocal(prev => ({ ...prev, ...(etapeActuelle.fallback ?? {}) }))
      setMessageCapture('timeout')
      setEtat(ETAT.COMPLET)
    }, TIMEOUT_MESURE_MS)

    return () => clearTimeout(timer)

  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [etat, indexEtape, tentative])

  // ── Auto-avance 3s après un timeout (valeur simulée affichée brièvement) ────
  useEffect(() => {
    if (messageCapture !== 'timeout' || etat !== ETAT.COMPLET) return

    const t = setTimeout(() => {
      setMessageCapture(null)
      if (indexEtape < ETAPES.length - 1) {
        setIndexEtape(i => i + 1)
        setEtat(ETAT.ATTENTE)
      } else {
        setPhase(PHASE.RECAP)
      }
    }, 3000)
    return () => clearTimeout(t)

  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messageCapture, etat, indexEtape])

  // ── Tension simulée : résultat immédiat + passage auto au récap dans 5s ─────
  useEffect(() => {
    if (etat !== ETAT.ATTENTE || !etapeActuelle.simulee) return

    setConstantesLocal(prev => ({ ...prev, ...simulerTension() }))
    setEtat(ETAT.COMPLET)

    const timer = setTimeout(() => setPhase(PHASE.RECAP), 5000)
    return () => clearTimeout(timer)

  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [etat, indexEtape])

  // ── ATTENTE → COMPLET dès que la valeur primaire arrive ─────────────────────
  useEffect(() => {
    if (etat === ETAT.ATTENTE && valeurActuelle != null) {
      setEtat(ETAT.COMPLET)
    }
  }, [etat, valeurActuelle])

  // ── Réessayer après null ─────────────────────────────────────────────────────
  const reessayer = () => {
    setMessageCapture(null)
    setTentative(t => t + 1)
  }

  // ── Passer à l'étape suivante ou au récap ───────────────────────────────────
  const etapeSuivante = () => {
    setMessageCapture(null)
    if (indexEtape < ETAPES.length - 1) {
      setIndexEtape(i => i + 1)
      setEtat(ETAT.ATTENTE)
    } else {
      setPhase(PHASE.RECAP)
    }
  }

  // ── Relancer toutes les mesures ──────────────────────────────────────────────
  const recommencer = () => {
    setConstantesLocal({})
    setIndexEtape(0)
    setEtat(ETAT.ATTENTE)
    setPhase(PHASE.MESURE)
    setMessageCapture(null)
    setTentative(0)
  }

  // ── Continuer vers l'étape 4 ────────────────────────────────────────────────
  const continuer = () => {
    setConstantes(constantes)
    navigate('/questions')
  }

  return (
    <div className="kiosk-shell">
      <IndicateurEtape etapeCourante={3} />

      {phase === PHASE.MESURE && (
        <VueMesure
          etape={etapeActuelle}
          indexEtape={indexEtape}
          total={ETAPES.length}
          etat={etat}
          valeur={valeurActuelle}
          constantes={constantes}
          erreur={erreur}
          messageCapture={messageCapture}
          onEtapeSuivante={etapeSuivante}
          onReessayer={reessayer}
          onRetour={() => navigate('/questionnaire')}
        />
      )}

      {phase === PHASE.RECAP && (
        <VueRecap
          constantes={constantes}
          onContinuer={continuer}
          onRecommencer={recommencer}
        />
      )}
    </div>
  )
}

// ═════════════════════════════════════════════════════════════════════════════
function VueMesure({
  etape, indexEtape, total, etat, valeur, constantes,
  erreur, messageCapture,
  onEtapeSuivante, onReessayer, onRetour,
}) {
  const estSimulee    = !!etape.simulee
  const couleur       = evaluerCouleur(etape.cle, valeur)
  const affichee      = !etape.double && valeur != null
    ? etape.formatter(valeur, constantes)
    : null

  const couleurDouble = etape.double
    ? pireCouleur(...etape.valeurs.map(sv => evaluerCouleur(sv.cle, constantes?.[sv.cle])))
    : null
  const couleurBadge  = etape.double ? couleurDouble : couleur

  const estDerniere   = indexEtape === total - 1
  const Illustration  = etape.illustration

  return (
    <div className="kiosk-center">
      <div className="kiosk-card constante-sequentielle">

        <div className="seq-header">
          <span className="eyebrow">Étape 3 / 5 · Constantes vitales</span>
          <span className="seq-compteur">{indexEtape + 1} / {total}</span>
        </div>

        <div className="seq-titre-wrapper">
          <span className="seq-icone" aria-hidden="true">{etape.icone}</span>
          <h2 className="kiosk-titre-sm">{etape.label}</h2>
        </div>

        {/* Illustration (ATTENTE, mesures réelles uniquement) */}
        {etat === ETAT.ATTENTE && !estSimulee && messageCapture !== 'null' && Illustration && (
          <div className="illustration-wrapper">
            <Illustration />
          </div>
        )}

        {/* Instruction normale */}
        {!estSimulee && messageCapture !== 'null' && (
          <p className="kiosk-soustitre">{etape.instruction}</p>
        )}

        {/* ATTENTE : spinner (mesure en cours, pas encore de retour null) */}
        {etat === ETAT.ATTENTE && !estSimulee && messageCapture !== 'null' && (
          <div className="seq-attente">
            <div className="kiosk-spinner" aria-label="Mesure en cours" />
            <p className="kiosk-note">Mesure en cours…</p>
          </div>
        )}

        {/* ATTENTE : capteur non pointé → message + Réessayer */}
        {etat === ETAT.ATTENTE && messageCapture === 'null' && (
          <div className="seq-attente">
            <div className="kiosk-alerte" role="alert">
              {etape.messageNull ?? 'Vérifiez le positionnement du capteur'}
            </div>
            <button className="kiosk-btn kiosk-btn--primary" onClick={onReessayer}>
              Réessayer
            </button>
          </div>
        )}

        {/* COMPLET */}
        {etat === ETAT.COMPLET && (
          <div className="seq-complet">

            {/* Tension simulée */}
            {estSimulee && (
              <p className="kiosk-note kiosk-note--info">
                Tension artérielle simulée — tensiomètre manuel non connecté
              </p>
            )}

            {/* Timeout : valeur simulée injectée */}
            {messageCapture === 'timeout' && (
              <p className="kiosk-alerte" role="alert">
                Mesure impossible — valeur simulée utilisée
              </p>
            )}

            {/* Valeur(s) */}
            {etape.double
              ? <ValeursDouble valeurs={etape.valeurs} constantes={constantes} avecCouleur />
              : affichee && (
                  <div className={`seq-valeur-grande seq-valeur-grande--${couleur}`}>
                    {affichee}
                    <span className="seq-unite">{etape.unite}</span>
                  </div>
                )
            }

            {/* Badge couleur */}
            <div className={`bio-badge bio-badge--${couleurBadge}`}>
              <span className="bio-badge-dot" />
              {LIBELLES_COULEUR[couleurBadge]}
            </div>

            {/* Mesure réelle réussie : confirmation + bouton */}
            {!estSimulee && messageCapture !== 'timeout' && (
              <>
                <div className="seq-ok" role="status">✓ Mesure effectuée</div>
                <button className="kiosk-btn kiosk-btn--primary" onClick={onEtapeSuivante}>
                  {estDerniere ? 'Voir le bilan des mesures →' : 'Mesurer la constante suivante →'}
                </button>
              </>
            )}

            {/* Auto-avance (tension simulée ou timeout) */}
            {(estSimulee || messageCapture === 'timeout') && (
              <p className="kiosk-note" role="status">
                Passage automatique dans quelques secondes…
              </p>
            )}
          </div>
        )}

        {erreur && (
          <div className="kiosk-alerte" role="alert">{erreur}</div>
        )}

        {indexEtape === 0 && etat === ETAT.ATTENTE && messageCapture !== 'null' && (
          <button
            className="kiosk-btn kiosk-btn--secondary"
            onClick={onRetour}
            style={{ alignSelf: 'flex-start' }}
          >
            ← Retour
          </button>
        )}
      </div>
    </div>
  )
}

// ═════════════════════════════════════════════════════════════════════════════
function ValeursDouble({ valeurs, constantes, avecCouleur = false }) {
  return (
    <div className="seq-double-valeurs">
      {valeurs.map(({ cle, label, unite, formatter }) => {
        const v       = constantes?.[cle]
        const fmt     = v != null ? formatter(v) : '…'
        const couleur = avecCouleur ? evaluerCouleur(cle, v) : null

        return (
          <div key={cle} className="seq-double-item">
            <span className="seq-double-label">{label}</span>
            <div className={`seq-valeur-grande${couleur ? ` seq-valeur-grande--${couleur}` : ''}`}>
              {fmt}
              <span className="seq-unite">{unite}</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ═════════════════════════════════════════════════════════════════════════════
function VueRecap({ constantes, onContinuer, onRecommencer }) {
  const alerteCritique = CLES_VITALES.some(
    cle => evaluerCouleur(cle, constantes?.[cle]) === 'rouge'
  )

  return (
    <div className="constantes-layout">

      <div className="constantes-header">
        <span className="eyebrow">Étape 3 / 5 · Constantes vitales</span>
        <h2 className="kiosk-titre-sm">Bilan des mesures</h2>
        <p className="kiosk-soustitre">Toutes les constantes ont été enregistrées.</p>
      </div>

      <div className="stabilisation-ok" role="status">
        ✅ Toutes les mesures sont complètes
      </div>

      {alerteCritique && (
        <div className="kiosk-alerte kiosk-alerte--urgence" role="alert">
          ⚠️ Valeur critique détectée — le personnel soignant est alerté automatiquement.
        </div>
      )}

      <BiometrieDisplay constantes={constantes} enCours={false} />

      <div className="kiosk-actions constantes-actions">
        <button className="kiosk-btn kiosk-btn--primary" onClick={onContinuer}>
          Continuer →
        </button>
        <button className="kiosk-btn kiosk-btn--secondary" onClick={onRecommencer}>
          ↩ Refaire les mesures
        </button>
      </div>

    </div>
  )
}
