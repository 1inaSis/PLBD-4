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
import BoutonAudio from '../components/BoutonAudio'
import { useTranslation } from '../hooks/useTranslation'
import { useTextToSpeech } from '../hooks/useTextToSpeech'
import { useInactivite } from '../hooks/useInactivite'
import '../styles/kiosk.css'
import { useVoiceInput } from '../hooks/useVoiceInput'
import ZoneSaisieMixte from '../components/ZoneSaisieMixte'

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
  const { patient, setResultatTriage, reinitialiser, modeIllettré } = usePatient()
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
  const [repsCumulees, setRepsCumulees]   = useState([])
  const [repsDict, setRepsDict]           = useState({})
  const [texteLibre, setTexteLibre]       = useState('')
  const [passerVisible, setPasserVisible] = useState(false)
  const [erreurTriage, setErreurTriage]   = useState(null)

  const passerTimerRef  = useRef(null)
  const lancerTriageRef = useRef(null)
  const chargerRef      = useRef(null)
  const completedRef    = useRef(false)

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

  // ── Timer "Passer" ──────────────────────────────────────────────────────────
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

  useEffect(() => {
    chargerRef.current([], {})
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Répondre à la question courante ────────────────────────────────────────
  const repondre = useCallback((valeur) => {
    if (!questionCourante) return
    clearTimeout(passerTimerRef.current)

    const nouvelleRep       = {
      question:     questionCourante.question,
      feature_name: questionCourante.feature_name,
      reponse:      valeur,
      type:         questionCourante.type,   // transmis à Groq pour suivi des types
    }
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

    const skip              = {
      question:     questionCourante.question,
      feature_name: questionCourante.feature_name,
      reponse:      'sans réponse',
      type:         questionCourante.type,
    }
    const nouvellesCumulees = [...repsCumulees, skip]

    setRepsCumulees(nouvellesCumulees)
    chargerRef.current(nouvellesCumulees, repsDict)
  }, [questionCourante, repsCumulees, repsDict])

  // ── Rendu ────────────────────────────────────────────────────────────────────
  return (
    <div className={`kiosk-shell${sortie ? ' page-exit' : ''}`} dir={langue === 'ar' ? 'rtl' : 'ltr'}>
      <IndicateurEtape etapeCourante={4} />
      <SelecteurLangue />
      <BoutonAudio />
      <ModalInactivite avertissement={avertissement} compte={compte} onContinuer={reset} />
      <GuideEtape etape={4} />

      {/* Badge Mode Assisté */}
      {modeIllettré && (
        <div style={{
          position: 'fixed', top: 8, right: 8, zIndex: 2000,
          background: 'rgba(0,212,255,0.15)', border: '1px solid rgba(0,212,255,0.3)',
          borderRadius: 20, padding: '4px 12px', fontSize: '0.78rem', color: '#00d4ff',
        }}>
          🤝 {t('illettré_mode_badge')}
        </div>
      )}

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

function PasserTexte() {
  const { t } = useTranslation()
  return t('passer_question')
}

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

// ── Constantes pour la reconnaissance vocale (oui_non / choix) ───────────────
const MOTS_OUI  = ['oui', 'yes', 'نعم', "d'accord", 'ok', 'ouais']
const MOTS_NON  = ['non', 'no', 'لا', 'pas', 'jamais', 'nope']
const normaliser = s =>
  s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').trim()

// ── Vue principale : une seule question ──────────────────────────────────────
function VueQuestion({
  question, numQuestion, maxQuestions,
  texteLibre, onTexteChange,
  passerVisible, onRepondre, onPasser, onRetour,
}) {
  const { t, langue }  = useTranslation()
  const { audioActif, modeIllettré } = usePatient()
  const { parler, arreter, estEnTrainDeParler, supporte } = useTextToSpeech()
  const pctProgression = Math.round(((numQuestion - 1) / maxQuestions) * 100)

  // ── Reconnaissance vocale pour oui_non et choix ───────────────────────────
  const voixQ = useVoiceInput({
    langue,
    onResult: (transcript) => {
      if (question.type === 'oui_non') {
        const txt = transcript.toLowerCase().trim()
        if (MOTS_OUI.some(m => txt.includes(m)))      onRepondre('oui')
        else if (MOTS_NON.some(m => txt.includes(m))) onRepondre('non')
        // Sinon : ignore silencieusement
      } else if (question.type === 'choix') {
        const tn    = normaliser(transcript)
        const match = question.choix?.find(opt => opt && tn.includes(normaliser(opt)))
        if (match) onRepondre(match)
        // Sinon : ignore silencieusement
      }
    },
  })

  // Lecture automatique de la question (conditionnel via audioActif dans parler)
  useEffect(() => {
    if (question?.question) {
      const timer = setTimeout(() => parler(question.question, langue), 300)
      return () => { clearTimeout(timer); arreter() }
    }
    return arreter
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question?.question, langue])

  // Re-lecture quand l'audio est (ré)activé
  useEffect(() => {
    if (!audioActif || !question?.question) return
    parler(question.question, langue)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audioActif])

  return (
    <div className="kiosk-center">
      <div className="kiosk-card q-carte">

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
          modeIllettré ? (
            <ModeIlletréOuiNon
              langue={langue}
              question={question.question}
              onRepondre={onRepondre}
            />
          ) : (
            <div>
              <div className="q-oui-non">
                <button className="kiosk-btn q-btn-oui" onClick={() => onRepondre('oui')}>
                  <span className="q-btn-icone">✓</span> OUI
                </button>
                <button className="kiosk-btn q-btn-non" onClick={() => onRepondre('non')}>
                  <span className="q-btn-icone">✗</span> NON
                </button>
              </div>
              {voixQ.supporte && (
                <div style={{ textAlign: 'center', marginTop: 8 }}>
                  <button
                    type="button"
                    className={`voice-btn${voixQ.ecoute ? ' voice-btn--actif' : ''}`}
                    onClick={voixQ.ecoute ? voixQ.arreter : voixQ.demarrer}
                    aria-label={voixQ.ecoute ? t('voice_arreter') : t('voice_demarrer')}
                    title={voixQ.ecoute ? t('voice_arreter') : t('voice_demarrer')}
                  >
                    {voixQ.ecoute ? '⏹' : '🎤'}
                  </button>
                  {voixQ.ecoute && (
                    <span style={{ fontSize: '0.85rem', color: '#94a3b8', marginLeft: 8 }}>
                      {t('voice_ecoute')}
                    </span>
                  )}
                </div>
              )}
            </div>
          )
        )}

        {/* Réponses — type choix */}
        {question.type === 'choix' && Array.isArray(question.choix) && (
          <div>
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
            {voixQ.supporte && (
              <div style={{ textAlign: 'center', marginTop: 8 }}>
                <button
                  type="button"
                  className={`voice-btn${voixQ.ecoute ? ' voice-btn--actif' : ''}`}
                  onClick={voixQ.ecoute ? voixQ.arreter : voixQ.demarrer}
                  aria-label={voixQ.ecoute ? t('voice_arreter') : t('voice_demarrer')}
                  title={voixQ.ecoute ? t('voice_arreter') : t('voice_demarrer')}
                >
                  {voixQ.ecoute ? '⏹' : '🎤'}
                </button>
                {voixQ.ecoute && (
                  <span style={{ fontSize: '0.85rem', color: '#94a3b8', marginLeft: 8 }}>
                    {t('voice_ecoute')}
                  </span>
                )}
              </div>
            )}
          </div>
        )}

        {/* Réponses — type texte_libre */}
        {question.type === 'texte_libre' && (
          modeIllettré ? (
            <ModeIlletréTexteLibre
              langue={langue}
              onFin={(texte) => onRepondre(texte || '')}
            />
          ) : (
            <div className="q-texte-libre-wrapper">
              <ZoneSaisieMixte
                value={texteLibre}
                onChange={onTexteChange}
                langue={langue}
                placeholder={t('decrivez_mots')}
                rows={3}
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
          )
        )}

        {passerVisible && (
          <button className="q-btn-passer" onClick={onPasser}>
            <PasserTexte />
          </button>
        )}

        {onRetour && (
          <button className="kiosk-btn kiosk-btn--secondary q-btn-retour" onClick={onRetour}>
            {t('retour')}
          </button>
        )}

      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Boutons OUI/NON géants avec reconnaissance vocale — mode illettré
// ─────────────────────────────────────────────────────────────────────────────
function ModeIlletréOuiNon({ langue, question, onRepondre }) {
  const { t }      = useTranslation()
  const { parler } = useTextToSpeech()
  const relireTimerRef = useRef(null)

  const MOTS_OUI = ['oui', 'yes', 'نعم', "d'accord", 'ok', 'ouais']
  const MOTS_NON = ['non', 'no', 'لا', 'pas', 'jamais', 'nope']

  const voix = useVoiceInput({
    langue,
    timeout: 15000,
    onResult: (transcript) => {
      const txt = transcript.toLowerCase()
      if (MOTS_OUI.some(m => txt.includes(m))) {
        clearTimeout(relireTimerRef.current)
        onRepondre('oui')
      } else if (MOTS_NON.some(m => txt.includes(m))) {
        clearTimeout(relireTimerRef.current)
        onRepondre('non')
      }
    },
    onEnd: () => {
      // Timeout sans réponse reconnue → relire la question et relancer
      relireTimerRef.current = setTimeout(() => {
        parler(`${t('illettré_relecture')} ${question}`, langue)
        setTimeout(() => voix.demarrer(), 2000)
      }, 500)
    },
  })

  useEffect(() => {
    const timer = setTimeout(() => voix.demarrer(), 500)
    return () => {
      clearTimeout(timer)
      clearTimeout(relireTimerRef.current)
      voix.arreter()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div style={{ display: 'flex', gap: 16, justifyContent: 'center', marginTop: 16 }}>
      <button
        onClick={() => { clearTimeout(relireTimerRef.current); voix.arreter(); onRepondre('oui') }}
        style={{
          width: 120, height: 120, borderRadius: 16, border: 'none',
          background: 'rgba(16,185,129,0.3)', color: '#10b981',
          fontSize: '3rem', cursor: 'pointer', display: 'flex',
          flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4,
        }}
      >
        👍<span style={{ fontSize: '0.9rem' }}>OUI</span>
      </button>
      <button
        onClick={() => { clearTimeout(relireTimerRef.current); voix.arreter(); onRepondre('non') }}
        style={{
          width: 120, height: 120, borderRadius: 16, border: 'none',
          background: 'rgba(239,68,68,0.3)', color: '#ef4444',
          fontSize: '3rem', cursor: 'pointer', display: 'flex',
          flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4,
        }}
      >
        👎<span style={{ fontSize: '0.9rem' }}>NON</span>
      </button>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Saisie vocale texte libre — mode illettré (questions adaptatives)
// ─────────────────────────────────────────────────────────────────────────────
function ModeIlletréTexteLibre({ langue, onFin }) {
  const { t }      = useTranslation()
  const { parler } = useTextToSpeech()
  const [texte, setTexte]  = useState('')
  const silenceTimerRef    = useRef(null)
  const texteAccumuléRef   = useRef('')

  const voix = useVoiceInput({
    langue,
    onResult: (transcript) => {
      const nouveau = texteAccumuléRef.current
        ? texteAccumuléRef.current + ' ' + transcript
        : transcript
      texteAccumuléRef.current = nouveau
      setTexte(nouveau)
      clearTimeout(silenceTimerRef.current)
      silenceTimerRef.current = setTimeout(() => {
        voix.arreter()
        setTimeout(() => onFin(texteAccumuléRef.current), 500)
      }, 5000)
    },
  })

  useEffect(() => {
    const t1 = setTimeout(() => parler(t('illettré_symptomes'), langue), 300)
    const t2 = setTimeout(() => voix.demarrer(), 1800)
    return () => {
      clearTimeout(t1)
      clearTimeout(t2)
      clearTimeout(silenceTimerRef.current)
      voix.arreter()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, alignItems: 'center' }}>
      <div style={{
        minHeight: 80, width: '100%', padding: '14px 16px',
        background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.15)',
        borderRadius: 12, fontSize: '1.3rem', color: '#f8fafc', lineHeight: 1.6,
        direction: langue === 'ar' ? 'rtl' : 'ltr',
      }}>
        {texte || (
          <span style={{ color: 'rgba(255,255,255,0.3)', fontStyle: 'italic' }}>
            {t('saisie_ecoute')}
          </span>
        )}
      </div>
      {voix.ecoute && (
        <div style={{ color: '#00d4ff', fontSize: '0.9rem' }}>
          🎙 {t('illettré_symptomes')}
        </div>
      )}
      <button
        onClick={() => {
          clearTimeout(silenceTimerRef.current)
          voix.arreter()
          setTimeout(() => onFin(texteAccumuléRef.current), 300)
        }}
        style={{
          padding: '12px 28px', borderRadius: 10, border: '1px solid rgba(0,212,255,0.3)',
          background: 'rgba(0,212,255,0.15)', color: '#00d4ff', fontSize: '1rem', cursor: 'pointer',
        }}
      >
        ⏹ {t('saisie_stop')}
      </button>
    </div>
  )
}
