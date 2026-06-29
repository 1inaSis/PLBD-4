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

// ── Raw SR pour mode illettré (évite speechSynthesis.cancel de useVoiceInput) ─
const SR_API_Q = typeof window !== 'undefined'
  ? (window.SpeechRecognition || window.webkitSpeechRecognition)
  : null

function parlerEnMorceauxQ(texte, langue) {
  if (!texte || typeof window === 'undefined' || !window.speechSynthesis) return 2000
  const lang = { fr: 'fr-FR', en: 'en-US', ar: 'ar-SA' }[langue] ?? 'fr-FR'
  const mots = texte.split(/\s+/)
  const morceaux = []
  let courant = ''
  for (const m of mots) {
    const test = courant ? courant + ' ' + m : m
    if (test.length <= 50) { courant = test }
    else { if (courant) morceaux.push(courant); courant = m }
  }
  if (courant) morceaux.push(courant)
  const durée = morceaux.reduce((acc, m) => acc + Math.max(700, m.length * 75), 0) + 500
  window.speechSynthesis.cancel()
  let i = 0
  function lireChunk() {
    if (i >= morceaux.length) return
    const utt = new SpeechSynthesisUtterance(morceaux[i++])
    utt.lang = lang; utt.rate = 0.9; utt.volume = 1.0
    utt.onend = lireChunk
    utt.onerror = () => setTimeout(lireChunk, 100)
    window.speechSynthesis.speak(utt)
  }
  setTimeout(lireChunk, 50)
  return durée
}

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

  // Mode illettré : layout épuré — question géante + boutons géants seuls
  if (modeIllettré) {
    return (
      <div className="kiosk-center" style={{ flexDirection: 'column', gap: 28, padding: '24px 16px' }}>
        <style>{`@keyframes pulse-q{0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,.7)}70%{box-shadow:0 0 0 18px rgba(239,68,68,0)}}`}</style>
        <p style={{ fontSize: '2rem', fontWeight: 700, color: '#f8fafc', textAlign: 'center', lineHeight: 1.4, margin: 0, maxWidth: 460 }}>
          {question.question}
        </p>
        {question.type === 'oui_non' && (
          <ModeIlletréOuiNon langue={langue} question={question.question} onRepondre={onRepondre} />
        )}
        {question.type === 'choix' && Array.isArray(question.choix) && (
          <ModeIlletréChoix langue={langue} choix={question.choix} question={question.question} onRepondre={onRepondre} />
        )}
        {question.type === 'texte_libre' && (
          <ModeIlletréTexteLibre langue={langue} onFin={(texte) => onRepondre(texte || '')} />
        )}
      </div>
    )
  }

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
          modeIllettré ? (
            <ModeIlletréChoix
              langue={langue}
              choix={question.choix}
              question={question.question}
              onRepondre={onRepondre}
            />
          ) : (
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
          )
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
// OUI/NON géants — raw SR (pas useVoiceInput → pas de cancel TTS) — mode illettré
// ─────────────────────────────────────────────────────────────────────────────
function ModeIlletréOuiNon({ langue, question, onRepondre }) {
  const { t }       = useTranslation()
  const [ecoute, setEcoute] = useState(false)
  const recoRef   = useRef(null)
  const noResRef  = useRef(null)
  const timers    = useRef([])
  const lancerRef = useRef(null)
  const ecouteRef = useRef(false)

  const clearAll = () => { timers.current.forEach(clearTimeout); timers.current = []; clearTimeout(noResRef.current) }
  const after    = (ms, fn) => { const id = setTimeout(fn, ms); timers.current.push(id); return id }
  const stopReco = () => {
    clearTimeout(noResRef.current); ecouteRef.current = false; setEcoute(false)
    if (!recoRef.current) return
    recoRef.current.onresult = null; recoRef.current.onend = null; recoRef.current.onerror = null
    try { recoRef.current.stop() } catch { /* ignoré */ }
    recoRef.current = null
  }

  const lancerReco = () => {
    if (!SR_API_Q) return
    stopReco(); window.speechSynthesis?.cancel()
    const reco = new SR_API_Q()
    reco.lang = { fr: 'fr-FR', en: 'en-US', ar: 'ar-SA' }[langue] ?? 'fr-FR'
    reco.continuous = false; reco.interimResults = false; reco.maxAlternatives = 3
    recoRef.current = reco; ecouteRef.current = true; setEcoute(true)

    // 15s sans réponse → relecture question
    noResRef.current = setTimeout(() => {
      stopReco()
      const d = parlerEnMorceauxQ(question, langue)
      after(d, () => lancerRef.current?.())
    }, 15000)

    reco.onresult = (e) => {
      clearTimeout(noResRef.current)
      const txt = Array.from(e.results).filter(r => r.isFinal).map(r => r[0].transcript).join(' ').toLowerCase().trim()
      stopReco()
      if (MOTS_OUI.some(m => txt.includes(m))) { clearAll(); onRepondre('oui') }
      else if (MOTS_NON.some(m => txt.includes(m))) { clearAll(); onRepondre('non') }
      else { after(600, () => lancerRef.current?.()) } // non reconnu → relance
    }
    reco.onerror = () => { clearTimeout(noResRef.current); stopReco(); after(800, () => lancerRef.current?.()) }
    reco.onend   = () => {
      clearTimeout(noResRef.current)
      if (!ecouteRef.current) return
      recoRef.current = null; ecouteRef.current = false; setEcoute(false)
      after(500, () => lancerRef.current?.())
    }
    reco.start()
  }
  lancerRef.current = lancerReco

  // TTS question → lancer reco (la TTS est déjà lancée par VueQuestion useEffect)
  useEffect(() => {
    const d = parlerEnMorceauxQ(question, langue)
    after(d, () => lancerRef.current?.())
    return () => { clearAll(); stopReco() }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question])

  const repondreAvec = (rep) => { clearAll(); stopReco(); onRepondre(rep) }

  return (
    <div style={{ display: 'flex', gap: 20, justifyContent: 'center', marginTop: 8, position: 'relative' }}>
      {ecoute && (
        <div style={{ position: 'absolute', top: -52, left: '50%', transform: 'translateX(-50%)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 36, height: 36, borderRadius: '50%', background: '#ef4444', animation: 'pulse-q 1.3s ease-out infinite' }} />
          <span style={{ color: '#f8fafc', fontSize: '1rem' }}>{t('ill_ecoute')}</span>
        </div>
      )}
      <button onClick={() => repondreAvec('oui')} style={{
        width: 160, height: 130, borderRadius: 20, border: 'none',
        background: 'rgba(16,185,129,0.25)', color: '#10b981',
        fontSize: '4rem', cursor: 'pointer', display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', gap: 4,
        WebkitTapHighlightColor: 'transparent',
      }}>
        👍<span style={{ fontSize: '1rem', fontWeight: 700 }}>OUI</span>
      </button>
      <button onClick={() => repondreAvec('non')} style={{
        width: 160, height: 130, borderRadius: 20, border: 'none',
        background: 'rgba(239,68,68,0.25)', color: '#ef4444',
        fontSize: '4rem', cursor: 'pointer', display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', gap: 4,
        WebkitTapHighlightColor: 'transparent',
      }}>
        👎<span style={{ fontSize: '1rem', fontWeight: 700 }}>NON</span>
      </button>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Choix multiple géant — raw SR — mode illettré
// ─────────────────────────────────────────────────────────────────────────────
function ModeIlletréChoix({ langue, choix, question, onRepondre }) {
  const { t }       = useTranslation()
  const [ecoute, setEcoute] = useState(false)
  const recoRef   = useRef(null)
  const noResRef  = useRef(null)
  const timers    = useRef([])
  const lancerRef = useRef(null)
  const ecouteRef = useRef(false)
  const norm = s => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').trim()

  const clearAll = () => { timers.current.forEach(clearTimeout); timers.current = []; clearTimeout(noResRef.current) }
  const after    = (ms, fn) => { const id = setTimeout(fn, ms); timers.current.push(id); return id }
  const stopReco = () => {
    clearTimeout(noResRef.current); ecouteRef.current = false; setEcoute(false)
    if (!recoRef.current) return
    recoRef.current.onresult = null; recoRef.current.onend = null; recoRef.current.onerror = null
    try { recoRef.current.stop() } catch { /* ignoré */ }
    recoRef.current = null
  }

  const lancerReco = () => {
    if (!SR_API_Q) return
    stopReco(); window.speechSynthesis?.cancel()
    const reco = new SR_API_Q()
    reco.lang = { fr: 'fr-FR', en: 'en-US', ar: 'ar-SA' }[langue] ?? 'fr-FR'
    reco.continuous = false; reco.interimResults = false; reco.maxAlternatives = 3
    recoRef.current = reco; ecouteRef.current = true; setEcoute(true)

    noResRef.current = setTimeout(() => {
      stopReco()
      const d = parlerEnMorceauxQ(question, langue)
      after(d, () => lancerRef.current?.())
    }, 15000)

    reco.onresult = (e) => {
      clearTimeout(noResRef.current)
      const tn = norm(Array.from(e.results).filter(r => r.isFinal).map(r => r[0].transcript).join(' '))
      stopReco()
      const match = choix.find(opt => opt && tn.includes(norm(opt)))
      if (match) { clearAll(); onRepondre(match) }
      else { after(600, () => lancerRef.current?.()) }
    }
    reco.onerror = () => { clearTimeout(noResRef.current); stopReco(); after(800, () => lancerRef.current?.()) }
    reco.onend   = () => {
      clearTimeout(noResRef.current)
      if (!ecouteRef.current) return
      recoRef.current = null; ecouteRef.current = false; setEcoute(false)
      after(500, () => lancerRef.current?.())
    }
    reco.start()
  }
  lancerRef.current = lancerReco

  useEffect(() => {
    const d = parlerEnMorceauxQ(question, langue)
    after(d, () => lancerRef.current?.())
    return () => { clearAll(); stopReco() }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question])

  const choisir = (option) => { clearAll(); stopReco(); onRepondre(option) }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, width: '100%', maxWidth: 440, alignItems: 'center', position: 'relative' }}>
      {ecoute && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <div style={{ width: 32, height: 32, borderRadius: '50%', background: '#ef4444', animation: 'pulse-q 1.3s ease-out infinite' }} />
          <span style={{ color: '#f8fafc', fontSize: '1rem' }}>{t('ill_ecoute')}</span>
        </div>
      )}
      {choix.map((option, i) => (
        <button key={i} onClick={() => choisir(option)} style={{
          width: '100%', padding: '22px 24px', borderRadius: 16,
          border: '2px solid rgba(0,212,255,0.3)',
          background: 'rgba(0,212,255,0.1)', color: '#f8fafc',
          fontSize: '1.3rem', fontWeight: 700, cursor: 'pointer',
          textAlign: 'center', lineHeight: 1.3,
          WebkitTapHighlightColor: 'transparent',
        }}>
          {option}
        </button>
      ))}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Texte libre — raw SR — mode illettré
// ─────────────────────────────────────────────────────────────────────────────
function ModeIlletréTexteLibre({ langue, onFin }) {
  const { t }    = useTranslation()
  const [texte, setTexte] = useState('')
  const [ecoute, setEcoute] = useState(false)
  const recoRef      = useRef(null)
  const ecouteRef    = useRef(false)
  const silenceRef   = useRef(null)
  const timers       = useRef([])
  const accumuléRef  = useRef('')
  const lancerRef    = useRef(null)

  const clearAll = () => { timers.current.forEach(clearTimeout); timers.current = []; clearTimeout(silenceRef.current) }
  const after    = (ms, fn) => { const id = setTimeout(fn, ms); timers.current.push(id); return id }
  const stopReco = () => {
    ecouteRef.current = false; setEcoute(false); clearTimeout(silenceRef.current)
    if (!recoRef.current) return
    recoRef.current.onresult = null; recoRef.current.onend = null; recoRef.current.onerror = null
    try { recoRef.current.stop() } catch { /* ignoré */ }
    recoRef.current = null
  }

  const lancerReco = () => {
    if (!SR_API_Q) return
    stopReco(); window.speechSynthesis?.cancel()
    const reco = new SR_API_Q()
    reco.lang = { fr: 'fr-FR', en: 'en-US', ar: 'ar-SA' }[langue] ?? 'fr-FR'
    reco.continuous = false; reco.interimResults = false; reco.maxAlternatives = 1
    recoRef.current = reco; ecouteRef.current = true; setEcoute(true)

    reco.onresult = (e) => {
      const tr = Array.from(e.results).filter(r => r.isFinal).map(r => r[0].transcript).join(' ').trim()
      if (tr) {
        const nouveau = accumuléRef.current ? accumuléRef.current + ' ' + tr : tr
        accumuléRef.current = nouveau; setTexte(nouveau)
      }
      stopReco()
      // 3s silence → valider automatiquement
      silenceRef.current = setTimeout(() => onFin(accumuléRef.current), 3000)
      // Ou relancer la reco pour accumuler plus
      after(200, () => lancerRef.current?.())
    }
    reco.onerror = () => { stopReco(); after(800, () => lancerRef.current?.()) }
    reco.onend   = () => {
      if (!ecouteRef.current) return
      recoRef.current = null; ecouteRef.current = false; setEcoute(false)
      after(400, () => lancerRef.current?.())
    }
    reco.start()
  }
  lancerRef.current = lancerReco

  useEffect(() => {
    const d = parlerEnMorceauxQ(t('ill_symptomes_voix'), langue)
    after(d, () => lancerRef.current?.())
    return () => { clearAll(); stopReco() }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const valider = () => { clearAll(); stopReco(); onFin(accumuléRef.current) }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, alignItems: 'center', width: '100%', maxWidth: 440 }}>
      {/* Indicateur écoute */}
      {ecoute && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 40, height: 40, borderRadius: '50%', background: '#ef4444', animation: 'pulse-q 1.3s ease-out infinite' }} />
          <span style={{ color: '#f8fafc', fontSize: '1.1rem' }}>{t('ill_ecoute')}</span>
        </div>
      )}
      {/* Transcription */}
      <div style={{
        minHeight: 80, width: '100%', padding: '16px',
        background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.15)',
        borderRadius: 14, fontSize: '1.4rem', color: '#f8fafc', lineHeight: 1.6,
        direction: langue === 'ar' ? 'rtl' : 'ltr',
      }}>
        {texte || <span style={{ color: 'rgba(255,255,255,0.3)', fontStyle: 'italic' }}>{t('saisie_ecoute')}</span>}
      </div>
      {/* Bouton valider géant */}
      {texte && (
        <button onClick={valider} style={{
          width: 160, height: 90, borderRadius: 20, border: 'none',
          background: 'rgba(16,185,129,0.25)', color: '#10b981',
          fontSize: '2.5rem', fontWeight: 900, cursor: 'pointer',
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4,
          WebkitTapHighlightColor: 'transparent',
        }}>
          <span>✓</span>
          <span style={{ fontSize: '0.9rem', fontWeight: 700 }}>OK</span>
        </button>
      )}
    </div>
  )
}
