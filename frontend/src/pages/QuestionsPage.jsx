// Étape 4 / 5 — Questions adaptatives générées par IA (Groq / Llama-3.3)
//
// Flux :
//   1. POST /api/questions → 4 questions (15 s de timeout max)
//   2. Affichage une par une avec UI adaptée au type (oui_non / choix / texte_libre)
//   3. Bouton "Passer" après 8 s (toujours disponible pour texte_libre)
//   4. Dernière question répondue → POST /api/triage → navigate /resultat
//
// Invariant de robustesse : le patient n'est jamais bloqué.
//   - Si Groq est lent ou indisponible : fallback silencieux, triage sans questions.
//   - Si le triage échoue : écran d'erreur avec bouton "Réessayer".

import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePatient } from '../context/PatientContext'
import { genererQuestions, lancerTriage } from '../services/api'
import IndicateurEtape from '../components/IndicateurEtape'
import '../styles/kiosk.css'

// ── Constantes de timing ──────────────────────────────────────────────────────
const TIMEOUT_GROQ_MS  = 15_000   // délai max pour que Groq réponde
const DELAI_PASSER_MS  =  8_000   // délai avant apparition du bouton "Passer"

// ── Phases internes ───────────────────────────────────────────────────────────
const PHASE = {
  CHARGEMENT:    'chargement',
  QUESTION:      'question',
  SOUMISSION:    'soumission',
  ERREUR_TRIAGE: 'erreur_triage',
}

// ═════════════════════════════════════════════════════════════════════════════
export default function QuestionsPage() {
  const navigate = useNavigate()
  const { patient, setQuestions, setReponse, setResultatTriage } = usePatient()

  const [phase, setPhase]               = useState(PHASE.CHARGEMENT)
  const [questions, setQuestionsLocal]  = useState([])
  const [index, setIndex]               = useState(0)
  const [reponsesLocal, setReponsesLocal] = useState({})
  const [texteLibre, setTexteLibre]     = useState('')
  const [passerVisible, setPasserVisible] = useState(false)
  const [erreurTriage, setErreurTriage] = useState(null)

  const passerTimerRef      = useRef(null)
  // Ref vers soumettreTriage pour éviter les closures rassies dans les callbacks mémoïsés
  const soumettreTriageRef  = useRef(null)

  // ── 1. Chargement des questions avec timeout ────────────────────────────────
  useEffect(() => {
    let annule = false

    const demarrer = async () => {
      const timeoutId = setTimeout(() => {
        if (!annule) {
          console.warn('[Questions] Timeout Groq — triage sans questions')
          chargerQuestions([], annule)
        }
      }, TIMEOUT_GROQ_MS)

      try {
        const res = await genererQuestions(patient.session_id, patient.constantes)
        clearTimeout(timeoutId)
        const qs = Array.isArray(res?.questions) ? res.questions : []
        chargerQuestions(qs, annule)
      } catch (err) {
        clearTimeout(timeoutId)
        console.warn('[Questions] Erreur API :', err.message)
        chargerQuestions([], annule)
      }
    }

    const chargerQuestions = (qs, annule) => {
      if (annule) return
      setQuestionsLocal(qs)
      setQuestions(qs)
      setPhase(PHASE.QUESTION)
    }

    demarrer()
    return () => { annule = true }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── 2. Timer "Passer" — reset à chaque nouvelle question ───────────────────
  useEffect(() => {
    if (phase !== PHASE.QUESTION) return
    const q = questions[index]

    // Pour texte_libre le bouton "Passer" est toujours visible immédiatement
    if (!q || q.type === 'texte_libre') {
      setPasserVisible(true)
      return
    }

    setPasserVisible(false)
    clearTimeout(passerTimerRef.current)
    passerTimerRef.current = setTimeout(() => setPasserVisible(true), DELAI_PASSER_MS)
    return () => clearTimeout(passerTimerRef.current)
  }, [phase, index, questions])

  // ── Dérivés ─────────────────────────────────────────────────────────────────
  const questionCourante = questions[index] ?? null
  const estDerniere      = index >= questions.length - 1
  const sansQuestion     = questions.length === 0

  // ── 3. Enregistrer la réponse et avancer ────────────────────────────────────
  const repondre = useCallback((valeur) => {
    if (!questionCourante) return

    const cle = questionCourante.feature_name ?? questionCourante.id
    const nouvellesReponses = { ...reponsesLocal, [cle]: valeur }
    setReponsesLocal(nouvellesReponses)
    setReponse(cle, valeur)       // persiste dans PatientContext
    setTexteLibre('')

    if (estDerniere || sansQuestion) {
      soumettreTriageRef.current(nouvellesReponses)
    } else {
      setIndex(i => i + 1)
    }
  }, [questionCourante, reponsesLocal, estDerniere, sansQuestion, setReponse])

  // Passer sans répondre
  const passer = useCallback(() => {
    setTexteLibre('')
    if (estDerniere || sansQuestion) {
      soumettreTriageRef.current(reponsesLocal)
    } else {
      setIndex(i => i + 1)
    }
  }, [reponsesLocal, estDerniere, sansQuestion])

  // ── 4. Soumettre le triage ESI ──────────────────────────────────────────────
  const soumettreTriage = useCallback(async (reponsesFin) => {
    setPhase(PHASE.SOUMISSION)
    setErreurTriage(null)
    try {
      const res = await lancerTriage(
        patient.session_id,
        patient.constantes ?? null,
        reponsesFin,
      )
      setResultatTriage(res)
      navigate('/resultat')
    } catch (err) {
      setErreurTriage(`Erreur lors du calcul du triage : ${err.message}`)
      setPhase(PHASE.ERREUR_TRIAGE)
    }
  }, [patient.session_id, patient.constantes, setResultatTriage, navigate])

  // Sync ref pour usage dans les callbacks mémoïsés
  soumettreTriageRef.current = soumettreTriage

  // ── Rendu ────────────────────────────────────────────────────────────────────
  return (
    <div className="kiosk-shell">
      <IndicateurEtape etapeCourante={4} />

      {/* Phase : chargement Groq */}
      {phase === PHASE.CHARGEMENT && <VueChargement />}

      {/* Phase : affichage question */}
      {phase === PHASE.QUESTION && (
        sansQuestion
          ? <VueSansQuestion onTerminer={() => soumettreTriageRef.current({})} />
          : <VueQuestion
              question={questionCourante}
              index={index}
              total={questions.length}
              texteLibre={texteLibre}
              onTexteChange={setTexteLibre}
              passerVisible={passerVisible}
              onRepondre={repondre}
              onPasser={passer}
              onRetour={() => navigate('/constantes')}
            />
      )}

      {/* Phase : soumission triage */}
      {phase === PHASE.SOUMISSION && <VueSoumission />}

      {/* Phase : erreur triage */}
      {phase === PHASE.ERREUR_TRIAGE && (
        <VueErreur
          message={erreurTriage}
          onReessayer={() => soumettreTriageRef.current(reponsesLocal)}
          onRetour={() => navigate('/constantes')}
        />
      )}
    </div>
  )
}

// ═════════════════════════════════════════════════════════════════════════════
// Sous-vues
// ═════════════════════════════════════════════════════════════════════════════

function VueChargement() {
  return (
    <div className="kiosk-center">
      <div className="kiosk-card kiosk-card--centree q-chargement">
        <div className="kiosk-spinner" aria-label="Chargement" />
        <h2 className="kiosk-titre-sm">Préparation des questions…</h2>
        <p className="kiosk-soustitre">
          L'IA analyse vos symptômes et constantes pour personnaliser les questions.
        </p>
        <p className="kiosk-note">Cela prend quelques secondes.</p>
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

function VueSansQuestion({ onTerminer }) {
  return (
    <div className="kiosk-center">
      <div className="kiosk-card kiosk-card--centree">
        <span className="eyebrow">Étape 4 / 5 · Questions IA</span>
        <h2 className="kiosk-titre-sm">Informations suffisantes</h2>
        <p className="kiosk-soustitre">
          Vos données sont complètes. Vous pouvez passer directement au résultat.
        </p>
        <div className="kiosk-actions" style={{ marginTop: 16 }}>
          <button className="kiosk-btn kiosk-btn--primary" onClick={onTerminer}>
            Obtenir mon résultat →
          </button>
        </div>
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

// ── Vue principale : une question ─────────────────────────────────────────────
function VueQuestion({
  question, index, total,
  texteLibre, onTexteChange,
  passerVisible, onRepondre, onPasser, onRetour,
}) {
  const pctProgression = Math.round(((index) / total) * 100)

  return (
    <div className="kiosk-center">
      <div className="kiosk-card q-carte">

        {/* En-tête + progression */}
        <div className="q-progression-wrapper">
          <span className="eyebrow">Étape 4 / 5 · Questions IA</span>
          <span className="q-compteur">{index + 1} / {total}</span>
        </div>
        <div className="q-barre-wrapper" role="progressbar"
             aria-valuenow={pctProgression} aria-valuemin={0} aria-valuemax={100}>
          <div className="q-barre-progression" style={{ width: `${pctProgression}%` }} />
        </div>

        {/* Texte de la question */}
        <p className="q-texte">{question.texte}</p>

        {/* Réponses selon le type */}
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

        {question.type === 'choix' && Array.isArray(question.choix) && (
          <div className="q-choix-grille" style={{
            gridTemplateColumns: question.choix.length <= 2 ? '1fr 1fr' : '1fr',
          }}>
            {question.choix.map((option, i) => (
              <button
                key={i}
                className="kiosk-btn q-btn-choix"
                onClick={() => onRepondre(option)}
              >
                {option}
              </button>
            ))}
          </div>
        )}

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

        {/* Bouton "Passer" (appara ît après DELAI_PASSER_MS) */}
        {passerVisible && (
          <button className="q-btn-passer" onClick={onPasser}>
            Passer cette question →
          </button>
        )}

        {/* Retour discret */}
        {index === 0 && (
          <button className="kiosk-btn kiosk-btn--secondary q-btn-retour" onClick={onRetour}>
            ← Retour
          </button>
        )}

      </div>
    </div>
  )
}
