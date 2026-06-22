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
import { demanderQuestionSuivante, lancerTriage, abandonnerSession } from '../services/api'
import IndicateurEtape from '../components/IndicateurEtape'
import SelecteurLangue from '../components/SelecteurLangue'
import GuideEtape from '../components/GuideEtape'
import ModalInactivite from '../components/ModalInactivite'
import { useTranslation } from '../hooks/useTranslation'
import { useTextToSpeech } from '../hooks/useTextToSpeech'
import { useInactivite } from '../hooks/useInactivite'
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
  const { patient, setResultatTriage, reinitialiser } = usePatient()
  const { t, langue } = useTranslation()
  const handleExpiration = useCallback(async () => {
    if (patient.session_id) await abandonnerSession(patient.session_id)
    reinitialiser(); navigate('/')
  }, [patient.session_id, reinitialiser, navigate])
  const { avertissement, compte, reset } = useInactivite({ onExpiration: handleExpiration })

  useEffect(() => {
    if (!patient.session_id) navigate('/', { replace: true })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const [phase, setPhase]                 = useState(PHASE.CHARGEMENT)
  const [sortie, setSortie]               = useState(false)

  const navigerVers = useCallback((path) => {
    setSortie(true)
    setTimeout(() => navigate(path), 350)
  }, [navigate])
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
  const completedRef    = useRef(false)

  // Abandon si le visiteur quitte avant la fin du triage
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
      completedRef.current = true
      navigerVers('/resultat')
    } catch (err) {
      setErreurTriage(`Erreur lors du calcul du triage : ${err.message}`)
      setPhase(PHASE.ERREUR_TRIAGE)
    }
  }, [patient.session_id, patient.constantes, setResultatTriage, navigerVers])

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
        langue,
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
  }, [patient.session_id, patient.constantes, patient.symptom_text, langue])

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
    <div className={`kiosk-shell${sortie ? ' page-exit' : ''}`} dir={langue === 'ar' ? 'rtl' : 'ltr'}>
      <IndicateurEtape etapeCourante={4} />
      <SelecteurLangue />
      <ModalInactivite avertissement={avertissement} compte={compte} onContinuer={reset} />
      <GuideEtape etape={4} />

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
          onRetour={numQuestion === 1 ? () => { completedRef.current = true; navigate('/constantes') } : null}
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

// Petit helper pour éviter d'appeler useTranslation dans un callback
function PasserTexte() {
  const { t } = useTranslation()
  return t('passer_question')
}

// ═════════════════════════════════════════════════════════════════════════════
// Sous-vues
// ═════════════════════════════════════════════════════════════════════════════

function VueChargement({ numQuestion }) {
  const { t } = useTranslation()
  return (
    <div className="kiosk-center">
      <div className="kiosk-card kiosk-card--centree q-chargement">
        <div className="kiosk-spinner" aria-label="Chargement" />
        <h2 className="kiosk-titre-sm">
          {numQuestion === 0 ? t('prep_questions') : t('analyse_reponse')}
        </h2>
        <p className="kiosk-soustitre">
          {numQuestion === 0
            ? t('ia_analyse_symptomes')
            : t('ia_adapte_question')}
        </p>
      </div>
    </div>
  )
}

function VueSoumission() {
  const { t } = useTranslation()
  return (
    <div className="kiosk-center">
      <div className="kiosk-card kiosk-card--centree">
        <div className="kiosk-spinner" aria-label="Calcul en cours" />
        <h2 className="kiosk-titre-sm">{t('calcul_urgence')}</h2>
        <p className="kiosk-soustitre">
          {t('modele_triage_analyse')}
        </p>
      </div>
    </div>
  )
}

function VueErreur({ message, onReessayer, onRetour }) {
  const { t } = useTranslation()
  return (
    <div className="kiosk-center">
      <div className="kiosk-card kiosk-card--centree">
        <h2 className="kiosk-titre-sm">{t('erreur_generique')}</h2>
        <div className="kiosk-alerte" role="alert">{message}</div>
        <div className="kiosk-actions" style={{ marginTop: 16 }}>
          <button className="kiosk-btn kiosk-btn--primary" onClick={onReessayer}>
            {t('const_reessayer')}
          </button>
          <button className="kiosk-btn kiosk-btn--secondary" onClick={onRetour}>
            {t('retour')}
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
  const { t, langue }  = useTranslation()
  const { parler, arreter, estEnTrainDeParler, supporte } = useTextToSpeech()
  const pctProgression = Math.round(((numQuestion - 1) / maxQuestions) * 100)

  // Lecture automatique de chaque nouvelle question
  useEffect(() => {
    if (question?.question) parler(question.question, langue)
    return arreter
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question?.question, langue])

  return (
    <div className="kiosk-center">
      <div className="kiosk-card q-carte">

        {/* En-tête + barre de progression */}
        <div className="q-progression-wrapper">
          <span className="eyebrow">{t('etape4_titre')}</span>
          <span className="q-compteur">{t('question_compteur', { x: numQuestion, y: maxQuestions })}</span>
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

        {/* Texte de la question + bouton relire */}
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
          <p className="q-texte" style={{ margin: 0, flex: 1 }}>{question.question}</p>
          {supporte && (
            <button
              className={`tts-btn${estEnTrainDeParler ? ' tts-btn--actif' : ''}`}
              onClick={() => parler(question.question, langue)}
              aria-label={t('tts_ecouter')}
              title={t('tts_ecouter')}
              style={{ marginTop: 2 }}
            >🔊</button>
          )}
        </div>

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
              placeholder={t('decrivez_mots')}
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
              {t('valider_reponse')}
            </button>
          </div>
        )}

        {/* Bouton "Passer" (après DELAI_PASSER_MS) */}
        {passerVisible && (
          <button className="q-btn-passer" onClick={onPasser}>
            <PasserTexte />
          </button>
        )}

        {/* Retour (1ère question seulement) */}
        {onRetour && (
          <button className="kiosk-btn kiosk-btn--secondary q-btn-retour" onClick={onRetour}>
            {t('retour')}
          </button>
        )}

      </div>
    </div>
  )
}
