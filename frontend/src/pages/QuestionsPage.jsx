// Étape 4 / 5 — Questions adaptatives IA (Groq / Llama-3.3) — mode question par question
//
// Flux :
//   1. POST /api/questions/suivante (reponses=[]) → 1ère question générée
//   2. Affichage → réponse → POST /api/questions/suivante (reponses=[...])
//   3. Groq décide de continuer (min 3, max 5) ou d'arrêter → triage direct
//
// Robustesse : si Groq est lent ou plante → triage lancé immédiatement.

import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePatient } from '../context/PatientContext'
import { demanderQuestionSuivante, lancerTriage } from '../services/api'
import IndicateurEtape from '../components/IndicateurEtape'
import '../styles/kiosk.css'

const DELAI_PASSER_MS = 8_000
const MAX_QUESTIONS   = 5

const PHASE = {
  CHARGEMENT:    'chargement',
  QUESTION:      'question',
  SOUMISSION:    'soumission',
  ERREUR_TRIAGE: 'erreur_triage',
}

// ═════════════════════════════════════════════════════════════════════════════
export default function QuestionsPage() {
  const navigate = useNavigate()
  const { patient, setResultatTriage } = usePatient()

  const [phase, setPhase]                 = useState(PHASE.CHARGEMENT)
  const [questionCourante, setQ]          = useState(null)
  const [numQuestion, setNumQuestion]     = useState(0)
  const [repsCumulees, setRepsCumulees]   = useState([])  // [{question, feature_name, reponse}]
  const [repsDict, setRepsDict]           = useState({})  // {feature_name: reponse} → triage
  const [texteLibre, setTexteLibre]       = useState('')
  const [passerVisible, setPasserVisible] = useState(false)
  const [erreurTriage, setErreurTriage]   = useState(null)

  const passerTimerRef  = useRef(null)
  const lancerTriageRef = useRef(null)
  const chargerRef      = useRef(null)

  // ── Timer "Passer" — reset à chaque nouvelle question ──────────────────────
  useEffect(() => {
    if (phase !== PHASE.QUESTION || !questionCourante) return
    if (questionCourante.type === 'texte_libre') {
      setPasserVisible(true)
      return
    }
    setPasserVisible(false)
    clearTimeout(passerTimerRef.current)
    passerTimerRef.current = setTimeout(() => setPasserVisible(true), DELAI_PASSER_MS)
    return () => clearTimeout(passerTimerRef.current)
  }, [phase, questionCourante])

  // ── Lancer le triage ESI ────────────────────────────────────────────────────
  const lancerTriageAvec = useCallback(async (reponsesFinales) => {
    setPhase(PHASE.SOUMISSION)
    setErreurTriage(null)
    try {
      const res = await lancerTriage(patient.session_id, patient.constantes ?? null, reponsesFinales)
      setResultatTriage(res)
      navigate('/resultat')
    } catch (err) {
      setErreurTriage(`Erreur lors du calcul du triage : ${err.message}`)
      setPhase(PHASE.ERREUR_TRIAGE)
    }
  }, [patient.session_id, patient.constantes, setResultatTriage, navigate])

  lancerTriageRef.current = lancerTriageAvec

  // ── Charger la question suivante ────────────────────────────────────────────
  const chargerSuivante = useCallback(async (repPrecedentes, repDict) => {
    setPhase(PHASE.CHARGEMENT)
    setTexteLibre('')
    clearTimeout(passerTimerRef.current)
    setPasserVisible(false)

    try {
      const res = await demanderQuestionSuivante(
        patient.session_id,
        repPrecedentes,
        patient.constantes ?? null,
        patient.symptom_text ?? null,
      )

      if (!res.continuer) {
        lancerTriageRef.current(repDict)
      } else {
        setQ({
          question:     res.question,
          type:         res.type      || 'oui_non',
          choix:        res.choix     || [],
          feature_name: res.feature_name || `q_adaptive_${res.num_question}`,
        })
        setNumQuestion(res.num_question)
        setPhase(PHASE.QUESTION)
      }
    } catch (err) {
      console.warn('[Questions] Erreur API :', err.message)
      lancerTriageRef.current(repDict)
    }
  }, [patient.session_id, patient.constantes, patient.symptom_text])

  chargerRef.current = chargerSuivante

  // ── Démarrage au mount : demander la 1ère question ──────────────────────────
  useEffect(() => {
    chargerRef.current([], {})
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Répondre à la question courante ────────────────────────────────────────
  const repondre = useCallback((valeur) => {
    if (!questionCourante) return
    clearTimeout(passerTimerRef.current)

    const nouvelleRep       = { question: questionCourante.question, feature_name: questionCourante.feature_name, reponse: valeur }
    const nouvellesCumulees = [...repsCumulees, nouvelleRep]
    const nouveauDict       = { ...repsDict, [questionCourante.feature_name]: valeur }

    setRepsCumulees(nouvellesCumulees)
    setRepsDict(nouveauDict)
    chargerRef.current(nouvellesCumulees, nouveauDict)
  }, [questionCourante, repsCumulees, repsDict])

  // ── Passer sans répondre ────────────────────────────────────────────────────
  const passer = useCallback(() => {
    if (!questionCourante) return
    clearTimeout(passerTimerRef.current)

    const skip              = { question: questionCourante.question, feature_name: questionCourante.feature_name, reponse: 'sans réponse' }
    const nouvellesCumulees = [...repsCumulees, skip]

    setRepsCumulees(nouvellesCumulees)
    chargerRef.current(nouvellesCumulees, repsDict)
  }, [questionCourante, repsCumulees, repsDict])

  // ── Rendu ────────────────────────────────────────────────────────────────────
  return (
    <div className="kiosk-shell">
      <IndicateurEtape etapeCourante={4} />

      {phase === PHASE.CHARGEMENT && (
        <VueChargement numQuestion={numQuestion} />
      )}

      {phase === PHASE.QUESTION && questionCourante && (
        <VueQuestion
          question={questionCourante}
          numQuestion={numQuestion}
          maxQuestions={MAX_QUESTIONS}
          texteLibre={texteLibre}
          onTexteChange={setTexteLibre}
          passerVisible={passerVisible}
          onRepondre={repondre}
          onPasser={passer}
          onRetour={numQuestion === 1 ? () => navigate('/constantes') : null}
        />
      )}

      {phase === PHASE.SOUMISSION && <VueSoumission />}

      {phase === PHASE.ERREUR_TRIAGE && (
        <VueErreur
          message={erreurTriage}
          onReessayer={() => lancerTriageRef.current(repsDict)}
          onRetour={() => navigate('/constantes')}
        />
      )}
    </div>
  )
}

// ═════════════════════════════════════════════════════════════════════════════
// Sous-vues
// ═════════════════════════════════════════════════════════════════════════════

function VueChargement({ numQuestion }) {
  return (
    <div className="kiosk-center">
      <div className="kiosk-card kiosk-card--centree q-chargement">
        <div className="kiosk-spinner" aria-label="Chargement" />
        <h2 className="kiosk-titre-sm">
          {numQuestion === 0 ? 'Préparation des questions…' : 'Analyse de votre réponse…'}
        </h2>
        <p className="kiosk-soustitre">
          {numQuestion === 0
            ? "L'IA analyse vos symptômes et constantes pour personnaliser les questions."
            : "L'IA adapte la prochaine question à vos réponses précédentes."}
        </p>
      </div>
    </div>
  )
}

function VueSoumission() {
  return (
    <div className="kiosk-center">
      <div className="kiosk-card kiosk-card--centree">
        <div className="kiosk-spinner" aria-label="Calcul en cours" />
        <h2 className="kiosk-titre-sm">Calcul du niveau d'urgence…</h2>
        <p className="kiosk-soustitre">
          Le modèle de triage analyse l'ensemble de vos données.
        </p>
      </div>
    </div>
  )
}

function VueErreur({ message, onReessayer, onRetour }) {
  return (
    <div className="kiosk-center">
      <div className="kiosk-card kiosk-card--centree">
        <h2 className="kiosk-titre-sm">Une erreur est survenue</h2>
        <div className="kiosk-alerte" role="alert">{message}</div>
        <div className="kiosk-actions" style={{ marginTop: 16 }}>
          <button className="kiosk-btn kiosk-btn--primary" onClick={onReessayer}>
            Réessayer
          </button>
          <button className="kiosk-btn kiosk-btn--secondary" onClick={onRetour}>
            ← Retour aux constantes
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Vue principale : une seule question ──────────────────────────────────────
function VueQuestion({
  question, numQuestion, maxQuestions,
  texteLibre, onTexteChange,
  passerVisible, onRepondre, onPasser, onRetour,
}) {
  const pctProgression = Math.round(((numQuestion - 1) / maxQuestions) * 100)

  return (
    <div className="kiosk-center">
      <div className="kiosk-card q-carte">

        {/* En-tête + barre de progression */}
        <div className="q-progression-wrapper">
          <span className="eyebrow">Étape 4 / 5 · Questions IA</span>
          <span className="q-compteur">Question {numQuestion} / {maxQuestions} max</span>
        </div>
        <div
          className="q-barre-wrapper"
          role="progressbar"
          aria-valuenow={pctProgression}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div className="q-barre-progression" style={{ width: `${pctProgression}%` }} />
        </div>

        {/* Texte de la question */}
        <p className="q-texte">{question.question}</p>

        {/* Réponses — type oui_non */}
        {question.type === 'oui_non' && (
          <div className="q-oui-non">
            <button className="kiosk-btn q-btn-oui" onClick={() => onRepondre('oui')}>
              <span className="q-btn-icone">✓</span> OUI
            </button>
            <button className="kiosk-btn q-btn-non" onClick={() => onRepondre('non')}>
              <span className="q-btn-icone">✗</span> NON
            </button>
          </div>
        )}

        {/* Réponses — type choix */}
        {question.type === 'choix' && Array.isArray(question.choix) && (
          <div
            className="q-choix-grille"
            style={{ gridTemplateColumns: question.choix.length <= 2 ? '1fr 1fr' : '1fr' }}
          >
            {question.choix.map((option, i) => (
              <button key={i} className="kiosk-btn q-btn-choix" onClick={() => onRepondre(option)}>
                {option}
              </button>
            ))}
          </div>
        )}

        {/* Réponses — type texte_libre */}
        {question.type === 'texte_libre' && (
          <div className="q-texte-libre-wrapper">
            <textarea
              className="symptome-input"
              placeholder="Décrivez en quelques mots…"
              value={texteLibre}
              onChange={e => onTexteChange(e.target.value)}
              rows={3}
              maxLength={300}
              autoFocus
            />
            <button
              className="kiosk-btn kiosk-btn--primary"
              onClick={() => onRepondre(texteLibre || '')}
              disabled={!texteLibre.trim()}
              style={{ marginTop: 8 }}
            >
              Valider ma réponse →
            </button>
          </div>
        )}

        {/* Bouton "Passer" (après DELAI_PASSER_MS) */}
        {passerVisible && (
          <button className="q-btn-passer" onClick={onPasser}>
            Passer cette question →
          </button>
        )}

        {/* Retour (1ère question seulement) */}
        {onRetour && (
          <button className="kiosk-btn kiosk-btn--secondary q-btn-retour" onClick={onRetour}>
            ← Retour
          </button>
        )}

      </div>
    </div>
  )
}
