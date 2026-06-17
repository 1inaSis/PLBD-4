// Étape 3 / 5 — Mesure séquentielle des constantes vitales
//
// Flux par étape :
//   ATTENTE (mesure Arduino en cours)
//   → COMPLET (résultat + badge couleur + bouton "Mesure suivante")
//
// 3 étapes : Température → Oxymètre (SpO₂ + FC) → Tension (simulée client)
// L'étape Tension n'appelle pas l'Arduino : valeurs simulées côté client,
// affichage immédiat, passage automatique au récap après 5 secondes.
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

// ── Priorité des niveaux de couleur (pour badge "pire état") ─────────────────
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
    unite:        '°C',
    icone:        '🌡️',
    illustration: IllustrationThermometre,
    formatter:    (v) => Number(v).toFixed(1),
  },

  {
    cle:          'spo2',
    typeMesure:   'spo2',
    double:       true,
    label:        'Oxymétrie de pouls',
    instruction:  'Placez votre index sur le capteur de la borne et restez immobile.',
    icone:        '🫁',
    illustration: IllustrationSpo2,
    valeurs: [
      { cle: 'spo2',       label: 'SpO₂',               unite: '%',   formatter: (v) => Number(v).toFixed(1) },
      { cle: 'heart_rate', label: 'Fréquence cardiaque', unite: 'bpm', formatter: (v) => Math.round(Number(v)) },
    ],
  },

  {
    cle:          'bp_systolic',
    typeMesure:   'tension',
    simulee:      true,   // pas d'appel Arduino — simulation côté client
    label:        'Tension artérielle',
    unite:        'mmHg',
    icone:        '💉',
    illustration: IllustrationTension,
    formatter:    (v, all) => `${Math.round(v)} / ${Math.round(all?.bp_diastolic ?? 0)}`,
  },
]

const CLES_VITALES = ['temperature', 'spo2', 'heart_rate', 'bp_systolic']

const PHASE = { MESURE: 'mesure', RECAP: 'recap' }
const ETAT  = { ATTENTE: 'attente', COMPLET: 'complet' }

// ── Génère une tension artérielle simulée réaliste ───────────────────────────
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

    enFetchRef.current = true
    mesurerConstante(etapeActuelle.typeMesure, patient.session_id)
      .then(res => {
        const nouvelles = {}
        Object.entries(res.constantes ?? {}).forEach(([k, v]) => {
          if (v != null) nouvelles[k] = v
        })
        setConstantesLocal(prev => ({ ...prev, ...nouvelles }))
        setErreur(null)
      })
      .catch(err => setErreur(`Erreur capteurs : ${err.message}`))
      .finally(() => { enFetchRef.current = false })

  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [etat, indexEtape])

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

  // ── Passer à l'étape suivante ou au récap ───────────────────────────────────
  const etapeSuivante = () => {
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
          onEtapeSuivante={etapeSuivante}
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
// Sous-vue : une mesure en cours (étape simple, double, ou simulée)
// ═════════════════════════════════════════════════════════════════════════════
function VueMesure({
  etape, indexEtape, total, etat, valeur, constantes,
  erreur,
  onEtapeSuivante, onRetour,
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

        {/* ── En-tête */}
        <div className="seq-header">
          <span className="eyebrow">Étape 3 / 5 · Constantes vitales</span>
          <span className="seq-compteur">{indexEtape + 1} / {total}</span>
        </div>

        {/* ── Nom + icône */}
        <div className="seq-titre-wrapper">
          <span className="seq-icone" aria-hidden="true">{etape.icone}</span>
          <h2 className="kiosk-titre-sm">{etape.label}</h2>
        </div>

        {/* ── Illustration (ATTENTE, étapes non simulées uniquement) */}
        {etat === ETAT.ATTENTE && !estSimulee && Illustration && (
          <div className="illustration-wrapper">
            <Illustration />
          </div>
        )}

        {/* ── Instruction (étapes non simulées) */}
        {!estSimulee && (
          <p className="kiosk-soustitre">{etape.instruction}</p>
        )}

        {/* ── ATTENTE : spinner (étapes non simulées) */}
        {etat === ETAT.ATTENTE && !estSimulee && (
          <div className="seq-attente">
            <div className="kiosk-spinner" aria-label="Mesure en cours" />
            <p className="kiosk-note">Mesure en cours…</p>
          </div>
        )}

        {/* ── COMPLET : résultat + badge */}
        {etat === ETAT.COMPLET && (
          <div className="seq-complet">

            {/* Message tension simulée */}
            {estSimulee && (
              <p className="kiosk-note kiosk-note--info">
                Tension artérielle simulée — tensiomètre manuel non connecté
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

            {/* Mesures réelles : confirmation + bouton */}
            {!estSimulee && (
              <>
                <div className="seq-ok" role="status">✓ Mesure effectuée</div>
                <button className="kiosk-btn kiosk-btn--primary" onClick={onEtapeSuivante}>
                  {estDerniere ? 'Voir le bilan des mesures →' : 'Mesurer la constante suivante →'}
                </button>
              </>
            )}

            {/* Tension simulée : avance automatique */}
            {estSimulee && (
              <p className="kiosk-note" role="status">
                Passage automatique dans quelques secondes…
              </p>
            )}
          </div>
        )}

        {/* ── Erreur capteur */}
        {erreur && (
          <div className="kiosk-alerte" role="alert">{erreur}</div>
        )}

        {/* ── Bouton retour (1re étape, ATTENTE uniquement) */}
        {indexEtape === 0 && etat === ETAT.ATTENTE && (
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
// Sous-composant : deux valeurs côte à côte (étape oxymètre)
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
// Sous-vue : récapitulatif des constantes
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
