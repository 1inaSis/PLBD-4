// Étape 3 / 5 — Mesure séquentielle des constantes vitales
//
// Flux par étape réelle :
//   PRET → (clic Mesurer) → COMPTE (5→1) → ATTENTE → (valeur valide) → COMPLET
//   ATTENTE → (null retourné) → message + Réessayer → COMPTE → ATTENTE
//   ATTENTE → (30s sans valeur) → valeur simulée injectée + COMPLET auto (3s)
//
// Flux étape simulée (spo2, tension) :
//   PRET → (auto) → ATTENTE → valeurs générées → COMPLET → passage auto (5s)
//
// 3 étapes : Température → Oxymètre (SpO₂ + FC, simulé) → Tension (simulée)
// Après les 3 étapes → RECAP (BiometrieDisplay complet + "Continuer")

import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePatient } from '../context/PatientContext'
import { demarrerArduino, arreterArduino, mesurerConstante, abandonnerSession } from '../services/api'
import IndicateurEtape from '../components/IndicateurEtape'
import BiometrieDisplay, { evaluerCouleur, LIBELLES_COULEUR } from '../components/BiometrieDisplay'
import {
  IllustrationThermometre,
  IllustrationSpo2,
  IllustrationTension,
} from '../components/IllustrationsGestes'
import SelecteurLangue from '../components/SelecteurLangue'
import GuideEtape from '../components/GuideEtape'
import ModalInactivite from '../components/ModalInactivite'
import { useTranslation } from '../hooks/useTranslation'
import { useInactivite } from '../hooks/useInactivite'
import '../styles/kiosk.css'

const PRIORITE_COULEUR = { rouge: 5, orange: 4, jaune: 3, vert: 2, gris: 1 }

function pireCouleur(...couleurs) {
  return couleurs.reduce(
    (pire, c) => (PRIORITE_COULEUR[c] ?? 0) > (PRIORITE_COULEUR[pire] ?? 0) ? c : pire,
    'gris',
  )
}

function simulerSpo2() {
  return {
    spo2:       Math.round((96 + Math.random() * 3) * 10) / 10,
    heart_rate: Math.round(65 + Math.random() * 20),
  }
}

function simulerTension() {
  const sys = Math.round(110 + Math.random() * 30)
  const dia = Math.round(sys * (0.55 + Math.random() * 0.13))
  return { bp_systolic: sys, bp_diastolic: dia }
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
    cle:           'spo2',
    typeMesure:    'spo2',
    simulee:       true,
    simulerValeurs: simulerSpo2,
    messageSimule: 'Capteur MAX30102 non connecté — valeurs simulées',
    double:        true,
    label:         'Oxymétrie de pouls',
    icone:         '🫁',
    illustration:  IllustrationSpo2,
    valeurs: [
      { cle: 'spo2',       label: 'SpO₂',               unite: '%',   formatter: (v) => Number(v).toFixed(1) },
      { cle: 'heart_rate', label: 'Fréquence cardiaque', unite: 'bpm', formatter: (v) => Math.round(Number(v)) },
    ],
  },

  {
    cle:           'bp_systolic',
    typeMesure:    'tension',
    simulee:       true,
    simulerValeurs: simulerTension,
    messageSimule: 'Tension artérielle simulée — tensiomètre manuel non connecté',
    label:         'Tension artérielle',
    unite:         'mmHg',
    icone:         '💉',
    illustration:  IllustrationTension,
    formatter:     (v, all) => `${Math.round(v)} / ${Math.round(all?.bp_diastolic ?? 0)}`,
  },
]

const CLES_VITALES      = ['temperature', 'spo2', 'heart_rate', 'bp_systolic']
const TIMEOUT_MESURE_MS = 30_000   // 30s avant injection valeur simulée

const PHASE = { MESURE: 'mesure', RECAP: 'recap' }
const ETAT  = { PRET: 'pret', COMPTE: 'compte', ATTENTE: 'attente', COMPLET: 'complet' }

// ═════════════════════════════════════════════════════════════════════════════
export default function ConstantesPage() {
  const navigate = useNavigate()
  const { patient, setConstantes, reinitialiser } = usePatient()
  const { t, langue } = useTranslation()
  const handleExpiration = useCallback(async () => {
    if (patient.session_id) await abandonnerSession(patient.session_id)
    reinitialiser(); navigate('/')
  }, [patient.session_id, reinitialiser, navigate])
  const { avertissement, compte, reset } = useInactivite({ onExpiration: handleExpiration })

  const [phase, setPhase]                = useState(PHASE.MESURE)
  const [indexEtape, setIndexEtape]      = useState(0)
  const [etat, setEtat]                  = useState(ETAT.PRET)
  const [compte, setCompte]              = useState(null)
  const [constantes, setConstantesLocal] = useState({})
  const [erreur, setErreur]              = useState(null)
  const [messageCapture, setMessageCapture] = useState(null)
  const [sortie, setSortie]              = useState(false)

  const enFetchRef   = useRef(false)
  const completedRef = useRef(false)

  const navigerVers = useCallback((path) => {
    setSortie(true)
    setTimeout(() => navigate(path), 350)
  }, [navigate])

  // Abandon si le visiteur quitte avant d'avoir terminé les constantes
  useEffect(() => {
    const sid = patient.session_id
    return () => {
      if (!completedRef.current && sid) {
        fetch('/api/session/abandon', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sid }),
          keepalive: true,
        }).catch(() => {})
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const etapeActuelle  = ETAPES[indexEtape]
  const valeurActuelle = constantes?.[etapeActuelle?.cle]

  // ── Lifecycle Arduino ────────────────────────────────────────────────────────
  useEffect(() => {
    demarrerArduino().catch(() => {})
    return () => { arreterArduino() }
  }, [])

  // ── Compte à rebours : 5 → 0 puis lance ATTENTE ─────────────────────────────
  useEffect(() => {
    if (etat !== ETAT.COMPTE) return
    if (compte <= 0) {
      setEtat(ETAT.ATTENTE)
      return
    }
    const t = setTimeout(() => setCompte(c => c - 1), 1000)
    return () => clearTimeout(t)
  }, [etat, compte])

  // ── Auto-lancer les étapes simulées (skip PRET/COMPTE) ──────────────────────
  useEffect(() => {
    if (etat === ETAT.PRET && etapeActuelle.simulee) {
      setEtat(ETAT.ATTENTE)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [etat, indexEtape])

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
  }, [etat, indexEtape])

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
  }, [etat, indexEtape])

  // ── Auto-avance 3s après un timeout (valeur simulée affichée brièvement) ────
  useEffect(() => {
    if (messageCapture !== 'timeout' || etat !== ETAT.COMPLET) return

    const t = setTimeout(() => {
      setMessageCapture(null)
      if (indexEtape < ETAPES.length - 1) {
        setIndexEtape(i => i + 1)
        setEtat(ETAT.PRET)
      } else {
        setPhase(PHASE.RECAP)
      }
    }, 3000)
    return () => clearTimeout(t)

  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messageCapture, etat, indexEtape])

  // ── Étapes simulées : génère les valeurs immédiatement ──────────────────────
  // Séparé du timer : setEtat(COMPLET) dans le même effet annulerait le setTimeout
  // via le cleanup React avant qu'il ne se déclenche.
  useEffect(() => {
    if (etat !== ETAT.ATTENTE || !etapeActuelle.simulee) return
    const valeurs = etapeActuelle.simulerValeurs ? etapeActuelle.simulerValeurs() : {}
    setConstantesLocal(prev => ({ ...prev, ...valeurs }))
    setEtat(ETAT.COMPLET)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [etat, indexEtape])

  // ── Étapes simulées : passage auto en 5s une fois COMPLET ────────────────────
  useEffect(() => {
    if (etat !== ETAT.COMPLET || !etapeActuelle.simulee) return
    const timer = setTimeout(() => {
      if (indexEtape < ETAPES.length - 1) {
        setIndexEtape(i => i + 1)
        setEtat(ETAT.PRET)
      } else {
        setPhase(PHASE.RECAP)
      }
    }, 5000)
    return () => clearTimeout(timer)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [etat, indexEtape])

  // ── ATTENTE → COMPLET dès que la valeur primaire arrive ─────────────────────
  useEffect(() => {
    if (etat === ETAT.ATTENTE && valeurActuelle != null) {
      setEtat(ETAT.COMPLET)
    }
  }, [etat, valeurActuelle])

  // ── Lancer la mesure (clic bouton "Mesurer") ─────────────────────────────────
  const lancerMesure = () => {
    setCompte(5)
    setEtat(ETAT.COMPTE)
  }

  // ── Réessayer après null (repart du compte à rebours) ───────────────────────
  const reessayer = () => {
    setMessageCapture(null)
    setCompte(5)
    setEtat(ETAT.COMPTE)
  }

  // ── Passer à l'étape suivante ou au récap ───────────────────────────────────
  const etapeSuivante = () => {
    setMessageCapture(null)
    if (indexEtape < ETAPES.length - 1) {
      setIndexEtape(i => i + 1)
      setEtat(ETAT.PRET)
    } else {
      setPhase(PHASE.RECAP)
    }
  }

  // ── Relancer toutes les mesures ──────────────────────────────────────────────
  const recommencer = () => {
    setConstantesLocal({})
    setIndexEtape(0)
    setEtat(ETAT.PRET)
    setPhase(PHASE.MESURE)
    setMessageCapture(null)
  }

  // ── Continuer vers l'étape 4 ────────────────────────────────────────────────
  const continuer = () => {
    completedRef.current = true
    setConstantes(constantes)
    navigerVers('/questions')
  }

  return (
    <div className={`kiosk-shell${sortie ? ' page-exit' : ''}`} dir={langue === 'ar' ? 'rtl' : 'ltr'}>
      <IndicateurEtape etapeCourante={3} />
      <SelecteurLangue />
      <ModalInactivite avertissement={avertissement} compte={compte} onContinuer={reset} />
      <GuideEtape
        etape={3}
        sousEtape={
          etapeActuelle?.cle === 'temperature' ? 'temp' :
          etapeActuelle?.cle === 'spo2'        ? 'spo2' : 'tension'
        }
      />

      {phase === PHASE.MESURE && (
        <VueMesure
          etape={etapeActuelle}
          indexEtape={indexEtape}
          total={ETAPES.length}
          etat={etat}
          compte={compte}
          valeur={valeurActuelle}
          constantes={constantes}
          erreur={erreur}
          messageCapture={messageCapture}
          onLancerMesure={lancerMesure}
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
  etape, indexEtape, total, etat, compte, valeur, constantes,
  erreur, messageCapture,
  onLancerMesure, onEtapeSuivante, onReessayer, onRetour,
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

        {/* PRET : illustration + instruction + bouton Mesurer (étapes réelles seulement) */}
        {etat === ETAT.PRET && !estSimulee && (
          <>
            {Illustration && (
              <div className="illustration-wrapper">
                <Illustration />
              </div>
            )}
            <p className="kiosk-soustitre">{etape.instruction}</p>
            <button className="kiosk-btn kiosk-btn--primary" onClick={onLancerMesure}>
              Mesurer
            </button>
          </>
        )}

        {/* COMPTE : compte à rebours 5→1 */}
        {etat === ETAT.COMPTE && (
          <div className="seq-attente">
            <p className="kiosk-soustitre">Préparez-vous…</p>
            <div className="seq-compte" role="status" aria-live="assertive">{compte}</div>
          </div>
        )}

        {/* ATTENTE : spinner (mesure en cours) */}
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

            {/* Étape simulée */}
            {estSimulee && (
              <p className="kiosk-note kiosk-note--info">
                {etape.messageSimule ?? 'Valeurs simulées'}
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

            {/* Auto-avance (étape simulée ou timeout) */}
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

        {indexEtape === 0 && etat === ETAT.PRET && (
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
