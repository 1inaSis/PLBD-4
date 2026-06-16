// Étape 3 / 5 — Mesure séquentielle des constantes vitales
//
// Flux par étape :
//   ATTENTE (polling GET /api/constantes toutes les 3s)
//   → STABILISATION (valeur reçue, compte à rebours 8s)
//   → COMPLET (résultat + badge couleur + bouton "Mesure suivante")
//
// 3 étapes : Température → Oxymètre (SpO₂ + FC) → Tension
// L'étape Oxymètre est "double" : SpO₂ et fréquence cardiaque
// sont mesurés simultanément par le même capteur (MAX30105).
// Après les 3 étapes → RECAP (BiometrieDisplay complet + "Continuer")

import { useState, useEffect, useRef, useCallback } from 'react'
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

// ── 3 étapes de mesure (température / oxymètre / tension) ────────────────────
// typeMesure : commande envoyée à l'Arduino via POST /api/constantes/mesurer
const ETAPES = [
  {
    cle:          'temperature',
    typeMesure:   'temperature',   // commande Arduino
    label:        'Température',
    instruction:  'Placez le capteur thermique sur votre front et restez immobile.',
    unite:        '°C',
    icone:        '🌡️',
    illustration: IllustrationThermometre,
    formatter:    (v) => Number(v).toFixed(1),
  },

  // Étape fusionnée : SpO₂ + fréquence cardiaque — même capteur MAX30105
  {
    cle:          'spo2',         // clé primaire : déclenche la transition ATTENTE → STABILISATION
    typeMesure:   'spo2',          // commande Arduino
    double:       true,            // deux valeurs affichées ensemble
    label:        'Oxymétrie de pouls',
    instruction:  'Placez votre index sur le capteur de la borne et restez immobile.',
    icone:        '🫁',
    illustration: IllustrationSpo2,
    // Descriptif des deux sous-mesures (ordre d'affichage)
    valeurs: [
      { cle: 'spo2',       label: 'SpO₂',               unite: '%',   formatter: (v) => Number(v).toFixed(1) },
      { cle: 'heart_rate', label: 'Fréquence cardiaque', unite: 'bpm', formatter: (v) => Math.round(Number(v)) },
    ],
  },

  {
    cle:          'bp_systolic',
    typeMesure:   'tension',       // simulée côté backend
    label:        'Tension artérielle',
    instruction:  'Passez le brassard autour de votre bras gauche et restez immobile.',
    unite:        'mmHg',
    icone:        '💉',
    illustration: IllustrationTension,
    formatter:    (v, all) => `${Math.round(v)} / ${Math.round(all?.bp_diastolic ?? 0)}`,
  },
]

// Toutes les clés vitales — utilisées dans le récap pour détecter une valeur critique
// (heart_rate n'est plus une clé primaire d'étape mais reste surveillée)
const CLES_VITALES = ['temperature', 'spo2', 'heart_rate', 'bp_systolic']

// Durée du compte à rebours de stabilisation par constante (secondes)
const DUREE_STABILISATION = 8

// Phases globales de la page
const PHASE = { MESURE: 'mesure', RECAP: 'recap' }

// États d'une étape individuelle
const ETAT  = { ATTENTE: 'attente', STABILISATION: 'stabilisation', COMPLET: 'complet' }

// ═════════════════════════════════════════════════════════════════════════════
export default function ConstantesPage() {
  const navigate = useNavigate()
  const { patient, setConstantes } = usePatient()

  const [phase, setPhase]                = useState(PHASE.MESURE)
  const [indexEtape, setIndexEtape]      = useState(0)
  const [etat, setEtat]                  = useState(ETAT.ATTENTE)
  // Accumulateur de toutes les valeurs reçues (merge progressif)
  const [constantes, setConstantesLocal] = useState({})
  const [secondes, setSecondes]          = useState(DUREE_STABILISATION)
  const [erreur, setErreur]              = useState(null)

  // Anti-requête concurrente (mesure Arduino peut prendre jusqu'à 20s)
  const enFetchRef = useRef(false)

  const etapeActuelle  = ETAPES[indexEtape]
  // Valeur de la clé primaire — suffit pour déclencher la stabilisation
  // (pour l'étape double, spo2 et heart_rate arrivent du même appel API)
  const valeurActuelle = constantes?.[etapeActuelle?.cle]

  // ── Lifecycle Arduino : démarrage au mount, arrêt au unmount ────────────────
  useEffect(() => {
    demarrerArduino().catch(() => {})   // non bloquant, erreur silencieuse
    return () => { arreterArduino() }   // keepalive : survit à la navigation
  }, [])  // une seule fois au mount/unmount de la page

  // ── Mesure unitaire : une commande par étape, pas de polling ────────────────
  useEffect(() => {
    if (etat !== ETAT.ATTENTE || enFetchRef.current) return

    enFetchRef.current = true
    mesurerConstante(etapeActuelle.typeMesure, patient.session_id)
      .then(res => {
        // Merge : conserve les valeurs déjà acquises, ajoute les nouvelles non-nulles
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
  }, [etat, indexEtape])  // une mesure par étape, pas de polling

  // ── Transition ATTENTE → STABILISATION dès que la valeur primaire arrive ─────
  useEffect(() => {
    if (etat === ETAT.ATTENTE && valeurActuelle != null) {
      setEtat(ETAT.STABILISATION)
      setSecondes(DUREE_STABILISATION)
    }
  }, [etat, valeurActuelle])

  // ── Compte à rebours de stabilisation (8s) ──────────────────────────────────
  useEffect(() => {
    if (etat !== ETAT.STABILISATION) return

    const timer = setInterval(() => {
      setSecondes(s => {
        if (s <= 1) {
          clearInterval(timer)
          setEtat(ETAT.COMPLET)
          return 0
        }
        return s - 1
      })
    }, 1000)

    return () => clearInterval(timer)
  }, [etat])

  // ── Passer à l'étape suivante ou afficher le récap ──────────────────────────
  const etapeSuivante = () => {
    if (indexEtape < ETAPES.length - 1) {
      setIndexEtape(i => i + 1)
      setEtat(ETAT.ATTENTE)
      setSecondes(DUREE_STABILISATION)
    } else {
      setPhase(PHASE.RECAP)
    }
  }

  // ── Relancer toutes les mesures ──────────────────────────────────────────────
  const recommencer = () => {
    setConstantesLocal({})
    setIndexEtape(0)
    setEtat(ETAT.ATTENTE)
    setSecondes(DUREE_STABILISATION)
    setPhase(PHASE.MESURE)
  }

  // ── Continuer vers l'étape 4 ────────────────────────────────────────────────
  const continuer = () => {
    setConstantes(constantes)
    navigate('/questions')
  }

  // ── Progression de la barre de stabilisation ─────────────────────────────────
  const pctStabilisation = Math.round(
    ((DUREE_STABILISATION - secondes) / DUREE_STABILISATION) * 100
  )

  // ── Rendu ────────────────────────────────────────────────────────────────────
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
          secondes={secondes}
          pctStabilisation={pctStabilisation}
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
// Sous-vue : une mesure en cours (étape simple ou étape double)
// ═════════════════════════════════════════════════════════════════════════════
function VueMesure({
  etape, indexEtape, total, etat, valeur, constantes,
  secondes, pctStabilisation, erreur,
  onEtapeSuivante, onRetour,
}) {
  // ── Étape simple : couleur et valeur formatée ──────────────────────────────
  const couleur  = evaluerCouleur(etape.cle, valeur)
  const affichee = !etape.double && valeur != null
    ? etape.formatter(valeur, constantes)
    : null

  // ── Étape double : couleur "pire" parmi les sous-mesures ──────────────────
  const couleurDouble = etape.double
    ? pireCouleur(...etape.valeurs.map(sv => evaluerCouleur(sv.cle, constantes?.[sv.cle])))
    : null

  // Badge couleur final (simple ou double)
  const couleurBadge = etape.double ? couleurDouble : couleur

  const estDerniere  = indexEtape === total - 1
  const Illustration = etape.illustration

  return (
    <div className="kiosk-center">
      <div className="kiosk-card constante-sequentielle">

        {/* ── En-tête : étiquette + compteur ──────────────────── */}
        <div className="seq-header">
          <span className="eyebrow">Étape 3 / 5 · Constantes vitales</span>
          <span className="seq-compteur">{indexEtape + 1} / {total}</span>
        </div>

        {/* ── Nom de la constante + icône ──────────────────────── */}
        <div className="seq-titre-wrapper">
          <span className="seq-icone" aria-hidden="true">{etape.icone}</span>
          <h2 className="kiosk-titre-sm">{etape.label}</h2>
        </div>

        {/* ── Illustration du geste (phase ATTENTE uniquement) ─── */}
        {etat === ETAT.ATTENTE && Illustration && (
          <div className="illustration-wrapper">
            <Illustration />
          </div>
        )}

        {/* ── Instruction au patient ────────────────────────────── */}
        <p className="kiosk-soustitre">{etape.instruction}</p>

        {/* ── Phase ATTENTE : spinner ───────────────────────────── */}
        {etat === ETAT.ATTENTE && (
          <div className="seq-attente">
            <div className="kiosk-spinner" aria-label="Mesure en cours" />
            <p className="kiosk-note">Mesure en cours…</p>
          </div>
        )}

        {/* ── Phase STABILISATION ───────────────────────────────── */}
        {etat === ETAT.STABILISATION && (
          <div className="seq-stabilisation">
            {etape.double
              ? <ValeursDouble valeurs={etape.valeurs} constantes={constantes} />
              : affichee && (
                  <div className="seq-valeur-grande">
                    {affichee}
                    <span className="seq-unite">{etape.unite}</span>
                  </div>
                )
            }
            <div className="stabilisation-bloc">
              <div className="stabilisation-header">
                <span className="stabilisation-label">Stabilisation de la mesure…</span>
                <span className="stabilisation-timer">{secondes} s</span>
              </div>
              <div
                className="stabilisation-barre"
                role="progressbar"
                aria-valuenow={pctStabilisation}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <div
                  className="stabilisation-progression"
                  style={{ width: `${pctStabilisation}%` }}
                />
              </div>
            </div>
          </div>
        )}

        {/* ── Phase COMPLET : résultat + badge + bouton ────────── */}
        {etat === ETAT.COMPLET && (
          <div className="seq-complet">
            {etape.double
              ? <ValeursDouble valeurs={etape.valeurs} constantes={constantes} avecCouleur />
              : affichee && (
                  <div className={`seq-valeur-grande seq-valeur-grande--${couleur}`}>
                    {affichee}
                    <span className="seq-unite">{etape.unite}</span>
                  </div>
                )
            }

            <div className={`bio-badge bio-badge--${couleurBadge}`}>
              <span className="bio-badge-dot" />
              {LIBELLES_COULEUR[couleurBadge]}
            </div>

            <div className="seq-ok" role="status">✓ Mesure effectuée</div>

            <button className="kiosk-btn kiosk-btn--primary" onClick={onEtapeSuivante}>
              {estDerniere ? 'Voir le bilan des mesures →' : 'Mesurer la constante suivante →'}
            </button>
          </div>
        )}

        {/* ── Erreur capteur ────────────────────────────────────── */}
        {erreur && (
          <div className="kiosk-alerte" role="alert">{erreur}</div>
        )}

        {/* ── Bouton retour (1re étape, ATTENTE uniquement) ────── */}
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
// Sous-composant : affiche deux valeurs côte à côte (étape oxymètre)
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
  // Vérifie toutes les clés vitales, y compris heart_rate (plus de clé primaire)
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
