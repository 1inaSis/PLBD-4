// Étape 3 / 5 — Mesure séquentielle des constantes vitales
//
// Flux par étape réelle (Température + SpO₂/FC) :
//   PRET → (clic Mesurer) → COMPTE (5→1) → ATTENTE → (valeur valide) → COMPLET
//   ATTENTE → (null retourné) → message + Réessayer → COMPTE → ATTENTE
//   ATTENTE → (30s sans valeur) → valeur simulée injectée + COMPLET auto (3s)
//
// Tension : saisie manuelle (PRET → SaisieTension → COMPLET)
// 3 étapes : Température → SpO₂/FC (MAX30102) → Tension (manuelle)
// Après les 3 étapes → RECAP (BiometrieDisplay complet + "Continuer")

import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePatient } from '../context/PatientContext'
import { demarrerArduino, arreterArduino, mesurerConstante, abandonnerSession } from '../services/api'
// usePatient est aussi utilisé dans VueMesure (sous-composant) pour audioActif
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
import { useTextToSpeech } from '../hooks/useTextToSpeech'
import { useInactivite } from '../hooks/useInactivite'
import BoutonAudio from '../components/BoutonAudio'
import ClavierNumerique from '../components/ClavierNumerique'
import { useVoiceInput } from '../hooks/useVoiceInput'
import '../styles/kiosk.css'

// TTS chunké pour mode illettré (≤50 chars/morceau, chaîne via onend)
const SR_API_C = typeof window !== 'undefined'
  ? (window.SpeechRecognition || window.webkitSpeechRecognition) : null
const LANG_BCP_C = { fr: 'fr-FR', en: 'en-US', ar: 'ar-SA' }

function parlerEnMorceaux(texte, langue) {
  if (!texte || typeof window === 'undefined' || !window.speechSynthesis) return 2000
  const lang = LANG_BCP_C[langue] ?? 'fr-FR'
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
    cle:            'temperature',
    typeMesure:     'temperature',
    label:          'const_temp_label',
    instruction:    'const_temp_instruction',
    instructionTTS: 'tts_instruction_temp',
    messageNull:    'const_temp_null',
    unite:        '°C',
    icone:        '🌡️',
    illustration: IllustrationThermometre,
    formatter:    (v) => Number(v).toFixed(1),
    fallback:     { temperature: 36.5 },
  },

  {
    cle:            'spo2',
    typeMesure:     'spo2',
    simulerLocal:   true,
    simulerValeurs: () => ({
      spo2: Math.floor(Math.random() * 10) + 90,
    }),
    label:          'const_spo2_label',
    instruction:    'guide3_spo2',
    instructionTTS: 'tts_instruction_spo2',
    messageNull:    'const_spo2_null',
    icone:        '🫁',
    illustration: IllustrationSpo2,
    unite:        '%',
    formatter:    (v) => Number(v).toFixed(1),
  },

  {
    cle:            'bp_systolic',
    typeMesure:     'tension',
    manuelle:       true,
    instruction:    'const_kf65r_guide',
    instructionTTS: 'tts_instruction_kf65r',
    label:          'const_bp_label',
    unite:          'mmHg',
    icone:          '💉',
    illustration:   IllustrationTension,
    formatter:      (v, all) => `${Math.round(v)} / ${Math.round(all?.bp_diastolic ?? 0)}`,
  },
]

const CLES_VITALES      = ['temperature', 'spo2', 'heart_rate', 'bp_systolic']
const TIMEOUT_MESURE_MS = 30_000   // 30s avant injection valeur simulée

const PHASE = { MESURE: 'mesure', RECAP: 'recap' }
const ETAT  = { PRET: 'pret', COMPTE: 'compte', ATTENTE: 'attente', COMPLET: 'complet' }

// ═════════════════════════════════════════════════════════════════════════════
export default function ConstantesPage() {
  const navigate = useNavigate()
  const { patient, setConstantes, reinitialiser, modeIllettré } = usePatient()
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

  const [phase, setPhase]                = useState(PHASE.MESURE)
  const [indexEtape, setIndexEtape]      = useState(0)
  const [etat, setEtat]                  = useState(ETAT.PRET)
  const [compteRebours, setCompteRebours] = useState(null)
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
    demarrerArduino().catch(() => { console.warn('[Arduino] Non détecté — mode simulation') })
    return () => { arreterArduino() }
  }, [])

  // ── Compte à rebours : 5 → 0 puis lance ATTENTE ─────────────────────────────
  useEffect(() => {
    if (etat !== ETAT.COMPTE) return
    if (compteRebours <= 0) {
      setEtat(ETAT.ATTENTE)
      return
    }
    const timer = setTimeout(() => setCompteRebours(c => c - 1), 1000)
    return () => clearTimeout(timer)
  }, [etat, compteRebours])

  // ── Auto-lancer les étapes simulées (skip PRET/COMPTE) ──────────────────────
  useEffect(() => {
    if (etat === ETAT.PRET && etapeActuelle.simulee) {
      setEtat(ETAT.ATTENTE)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [etat, indexEtape])

  // ── Mesure : Arduino ou simulation locale selon l'étape ─────────────────────
  useEffect(() => {
    console.log(`[Constantes] useEffect mesure — etat=${etat} etape=${etapeActuelle?.cle} enFetch=${enFetchRef.current} simulee=${etapeActuelle?.simulee} simulerLocal=${etapeActuelle?.simulerLocal}`)
    if (etat !== ETAT.ATTENTE || enFetchRef.current || etapeActuelle.simulee) return

    setMessageCapture(null)
    enFetchRef.current = true

    if (etapeActuelle.simulerLocal) {
      console.log(`[Constantes] SpO2 — simulation locale démarrée (3s)`)
      const timer = setTimeout(() => {
        const valeurs = etapeActuelle.simulerValeurs ? etapeActuelle.simulerValeurs() : {}
        console.log(`[Constantes] SpO2 — valeurs simulées :`, valeurs)
        setConstantesLocal(prev => ({ ...prev, ...valeurs }))
        setErreur(null)
        enFetchRef.current = false
      }, 3000)
      return () => { clearTimeout(timer); enFetchRef.current = false }
    }

    mesurerConstante(etapeActuelle.typeMesure, patient.session_id)
      .then(res => {
        const nouvelles = {}
        Object.entries(res.constantes ?? {}).forEach(([k, v]) => {
          if (v != null) nouvelles[k] = v
        })
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

  // ── Timeout 30s : injecte valeur de secours si toujours en attente ──────────
  useEffect(() => {
    if (etat !== ETAT.ATTENTE || etapeActuelle.simulee || etapeActuelle.simulerLocal) return

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

  // ── Étapes simulées : génère les valeurs après délai ─────────────────────────
  useEffect(() => {
    if (etat !== ETAT.ATTENTE || !etapeActuelle.simulee) return
    const timer = setTimeout(() => {
      const valeurs = etapeActuelle.simulerValeurs ? etapeActuelle.simulerValeurs() : {}
      setConstantesLocal(prev => ({ ...prev, ...valeurs }))
      setEtat(ETAT.COMPLET)
    }, etapeActuelle.delaiSimulation ?? 3000)
    return () => clearTimeout(timer)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [etat, indexEtape])

  // ── Étapes simulées : passage auto en 3s une fois COMPLET ────────────────────
  useEffect(() => {
    if (etat !== ETAT.COMPLET || !etapeActuelle.simulee) return
    const timer = setTimeout(() => {
      if (indexEtape < ETAPES.length - 1) {
        setIndexEtape(i => i + 1)
        setEtat(ETAT.PRET)
      } else {
        setPhase(PHASE.RECAP)
      }
    }, 3000)
    return () => clearTimeout(timer)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [etat, indexEtape])

  // ── ATTENTE → COMPLET dès que la valeur primaire arrive ─────────────────────
  useEffect(() => {
    console.log(`[Constantes] auto-avance — etat=${etat} etape=${etapeActuelle?.cle} valeurActuelle=${valeurActuelle}`)
    if (etat === ETAT.ATTENTE && valeurActuelle != null) {
      console.log(`[Constantes] → passage COMPLET (valeur reçue)`)
      setEtat(ETAT.COMPLET)
    }
  }, [etat, valeurActuelle])

  // ── Lancer la mesure (clic bouton "Mesurer") ─────────────────────────────────
  const lancerMesure = () => {
    setCompteRebours(5)
    setEtat(ETAT.COMPTE)
  }

  // ── Réessayer après null (repart du compte à rebours) ───────────────────────
  const reessayer = () => {
    setMessageCapture(null)
    setCompteRebours(5)
    setEtat(ETAT.COMPTE)
  }

  // ── Valider KF-65R (SYS, DIA, PUL) — PUL remplace la FC simulée ────────────
  const validerTensionManuelle = ({ bp_systolic, bp_diastolic, heart_rate }) => {
    setConstantesLocal(prev => ({ ...prev, bp_systolic, bp_diastolic, heart_rate }))
    setEtat(ETAT.COMPLET)
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
      <BoutonAudio />
      <ModalInactivite avertissement={avertissement} compte={compte} onContinuer={reset} />

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
          compte={compteRebours}
          valeur={valeurActuelle}
          constantes={constantes}
          erreur={erreur}
          messageCapture={messageCapture}
          onLancerMesure={lancerMesure}
          onEtapeSuivante={etapeSuivante}
          onReessayer={reessayer}
          onValiderManuel={validerTensionManuelle}
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
function CompteSVG({ compte }) {
  const rayon    = 50
  const circonf  = 2 * Math.PI * rayon
  const dashoffset = (1 - compte / 5) * circonf
  return (
    <svg
      width="130" height="130" viewBox="0 0 130 130"
      role="status" aria-live="assertive" aria-label={compte}
      style={{ display: 'block', margin: '0 auto' }}
    >
      <circle cx="65" cy="65" r={rayon} fill="none" stroke="#1e2a3a" strokeWidth="10" />
      <circle
        cx="65" cy="65" r={rayon}
        fill="none"
        stroke="#00d4ff"
        strokeWidth="10"
        strokeDasharray={circonf}
        strokeDashoffset={dashoffset}
        strokeLinecap="round"
        transform="rotate(-90 65 65)"
        style={{ transition: 'stroke-dashoffset 0.85s linear' }}
      />
      <text x="65" y="65" textAnchor="middle" dominantBaseline="central"
        fontSize="38" fontWeight="800" fill="#00d4ff">
        {compte}
      </text>
    </svg>
  )
}

// ═════════════════════════════════════════════════════════════════════════════
function VueMesure({
  etape, indexEtape, total, etat, compte, valeur, constantes,
  erreur, messageCapture,
  onLancerMesure, onEtapeSuivante, onReessayer, onValiderManuel, onRetour,
}) {
  const { t, langue }  = useTranslation()
  const { parler, arreter, estEnTrainDeParler, supporte } = useTextToSpeech()
  const { audioActif, modeIllettré } = usePatient()
  const estSimulee      = !!etape.simulee
  const estManuelle     = !!etape.manuelle
  const estSimulerLocal = !!etape.simulerLocal

  const texteInstruction = etape.instructionTTS ? t(etape.instructionTTS) : null
  const autoMesureRef    = useRef(null)

  // Lecture auto 300ms après le passage à l'état PRET (nouvelle étape ou retour)
  useEffect(() => {
    if (etat !== ETAT.PRET || !texteInstruction) return
    clearTimeout(autoMesureRef.current)

    if (modeIllettré && !estManuelle && !estSimulee) {
      // Mode illettré : TTS chunké puis auto-lancer la mesure
      const t1 = setTimeout(() => {
        const délai = parlerEnMorceaux(texteInstruction, langue)
        console.log('[ILL] Auto-lancer mesure dans', délai, 'ms — étape:', etape.cle)
        autoMesureRef.current = setTimeout(onLancerMesure, délai)
      }, 300)
      return () => { clearTimeout(t1); clearTimeout(autoMesureRef.current); arreter() }
    }

    const timer = setTimeout(() => parler(texteInstruction, langue), 300)
    return () => { clearTimeout(timer); arreter() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [etat, indexEtape])

  // Re-lecture quand l'audio est (ré)activé sur cette page
  useEffect(() => {
    if (!audioActif || !texteInstruction) return
    parler(texteInstruction, langue)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audioActif])

  const relireInstruction = () => { if (texteInstruction) parler(texteInstruction, langue) }

  // Auto-avance mode illettré : COMPLET → étape suivante après 4s (non manuelle)
  useEffect(() => {
    if (!modeIllettré || etat !== ETAT.COMPLET || estManuelle || estSimulee || messageCapture === 'timeout') return
    // Lire le résultat à voix haute
    let texteR = ''
    if (etape.cle === 'temperature' && valeur != null) {
      texteR = langue === 'ar'
        ? `درجة حرارتك ${Number(valeur).toFixed(1)} درجة`
        : langue === 'en'
        ? `Your temperature is ${Number(valeur).toFixed(1)} degrees`
        : `Votre température est ${Number(valeur).toFixed(1)} degrés`
    } else if (etape.cle === 'spo2' && valeur != null) {
      texteR = langue === 'ar'
        ? `نسبة أكسجينك ${Math.round(valeur)} بالمئة`
        : langue === 'en'
        ? `Your oxygen level is ${Math.round(valeur)} percent`
        : `Votre taux d'oxygène est ${Math.round(valeur)} pour cent`
    }
    if (texteR) parler(texteR, langue)
    const timer = setTimeout(() => onEtapeSuivante(), 4000)
    return () => clearTimeout(timer)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [etat, indexEtape])

  // Auto-avance mode illettré : COMPLET après KF-65R manuel
  useEffect(() => {
    if (!modeIllettré || etat !== ETAT.COMPLET || !estManuelle) return
    parler(t('ill_constantes_ok'), langue)
    const timer = setTimeout(() => onEtapeSuivante(), 3500)
    return () => clearTimeout(timer)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [etat, indexEtape])

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
          <span className="eyebrow">{t('const_etape_titre')}</span>
          <span className="seq-compteur">{indexEtape + 1} / {total}</span>
        </div>

        <div className="seq-titre-wrapper">
          <span className="seq-icone" aria-hidden="true">{etape.icone}</span>
          <h2 className="kiosk-titre-sm">{t(etape.label)}</h2>
        </div>

        {/* PRET : illustration + bouton Mesurer */}
        {etat === ETAT.PRET && !estSimulee && !estManuelle && (
          <>
            {Illustration && (
              <div className="illustration-wrapper">
                <Illustration />
              </div>
            )}
            {modeIllettré ? (
              /* Mode illettré : un seul grand bouton tactile (TTS guide, pas de texte) */
              <button onClick={onLancerMesure} style={{
                width: 160, height: 160, borderRadius: 24, border: 'none',
                background: 'rgba(0,212,255,0.15)', color: '#00d4ff',
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                gap: 10, cursor: 'pointer', WebkitTapHighlightColor: 'transparent',
              }}>
                <span style={{ fontSize: '4rem', lineHeight: 1 }}>{etape.icone}</span>
                <span style={{ fontSize: '1rem', fontWeight: 700 }}>{t('const_mesurer')}</span>
              </button>
            ) : (
              /* Mode normal : instruction + bouton standard */
              <>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <p className="kiosk-soustitre" style={{ margin: 0 }}>{t(etape.instruction)}</p>
                  {supporte && texteInstruction && (
                    <button
                      className={`tts-btn${estEnTrainDeParler ? ' tts-btn--actif' : ''}`}
                      onClick={relireInstruction}
                      aria-label={t('tts_ecouter')}
                      title={t('tts_ecouter')}
                    >🔊</button>
                  )}
                </div>
                <button className="kiosk-btn kiosk-btn--primary" onClick={onLancerMesure}>
                  {t('const_mesurer')}
                </button>
              </>
            )}
          </>
        )}

        {/* PRET : saisie manuelle KF-65R */}
        {etat === ETAT.PRET && estManuelle && (
          <>
            {supporte && texteInstruction && (
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 4 }}>
                <button
                  className={`tts-btn${estEnTrainDeParler ? ' tts-btn--actif' : ''}`}
                  onClick={relireInstruction}
                  aria-label={t('tts_ecouter')}
                  title={t('tts_ecouter')}
                >🔊</button>
              </div>
            )}
            <SaisieKF65R
              instruction={t(etape.instruction ?? 'const_kf65r_guide')}
              onValider={onValiderManuel}
              t={t}
              modeIllettré={modeIllettré}
              langue={langue}
            />
          </>
        )}

        {/* COMPTE : compte à rebours circulaire SVG 5→1 */}
        {etat === ETAT.COMPTE && (
          <div className="seq-attente">
            <p className="kiosk-soustitre">{t('const_preparez')}</p>
            <CompteSVG compte={compte ?? 5} />
          </div>
        )}

        {/* ATTENTE : spinner (mesure en cours) */}
        {etat === ETAT.ATTENTE && !estSimulee && messageCapture !== 'null' && (
          <div className="seq-attente">
            <div className="kiosk-spinner" aria-label={t('const_mesure_cours')} />
            <p className="kiosk-note">{t('const_mesure_cours')}</p>
          </div>
        )}

        {/* ATTENTE : capteur non pointé → message + Réessayer */}
        {etat === ETAT.ATTENTE && messageCapture === 'null' && (
          <div className="seq-attente">
            <div className="kiosk-alerte" role="alert">
              {etape.messageNull ? t(etape.messageNull) : t('const_capteur_verif')}
            </div>
            <button
              className="kiosk-btn kiosk-btn--primary"
              onClick={() => { onReessayer(); relireInstruction() }}
            >
              {t('const_reessayer')}
            </button>
          </div>
        )}

        {/* COMPLET */}
        {etat === ETAT.COMPLET && (
          <div className="seq-complet">

            {/* Étape simulée */}
            {estSimulee && (
              <p className="kiosk-note kiosk-note--info">
                {etape.messageSimule ? t(etape.messageSimule) : t('const_sim_default')}
              </p>
            )}

            {/* Timeout : valeur simulée injectée */}
            {messageCapture === 'timeout' && (
              <p className="kiosk-alerte" role="alert">
                {t('const_sim_timeout')}
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
              {t(LIBELLES_COULEUR[couleurBadge])}
            </div>

            {/* Mesure réussie : confirmation + bouton (géant en mode illettré) */}
            {!estSimulee && messageCapture !== 'timeout' && (
              modeIllettré ? (
                <button onClick={onEtapeSuivante} style={{
                  width: 160, height: 100, borderRadius: 20, border: 'none',
                  background: 'rgba(16,185,129,0.25)', color: '#10b981',
                  fontSize: '3rem', fontWeight: 900, cursor: 'pointer',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4,
                  WebkitTapHighlightColor: 'transparent',
                }}>
                  <span>✓</span>
                  <span style={{ fontSize: '0.85rem', fontWeight: 700 }}>OK</span>
                </button>
              ) : (
                <>
                  <div className="seq-ok" role="status">{t('const_mesure_ok')}</div>
                  <button className="kiosk-btn kiosk-btn--primary" onClick={onEtapeSuivante}>
                    {estDerniere ? t('const_voir_bilan') : t('const_suivante')}
                  </button>
                </>
              )
            )}

            {/* Auto-avance (étape simulée ou timeout) */}
            {(estSimulee || messageCapture === 'timeout') && (
              <p className="kiosk-note" role="status">
                {t('const_auto_passage')}
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
            {t('retour')}
          </button>
        )}
      </div>
    </div>
  )
}

// ═════════════════════════════════════════════════════════════════════════════
function ValeursDouble({ valeurs, constantes, avecCouleur = false }) {
  const { t } = useTranslation()
  return (
    <div className="seq-double-valeurs">
      {valeurs.map(({ cle, label, unite, formatter, simule }) => {
        const v       = constantes?.[cle]
        const fmt     = v != null ? formatter(v) : '…'
        const couleur = avecCouleur ? evaluerCouleur(cle, v) : null

        return (
          <div key={cle} className="seq-double-item">
            <span className="seq-double-label">{t(label)}</span>
            <div className={`seq-valeur-grande${couleur ? ` seq-valeur-grande--${couleur}` : ''}`}>
              {fmt}
              <span className="seq-unite">{unite}</span>
            </div>
            {simule && (
              <div className="bio-badge bio-badge--gris" style={{ alignSelf: 'center', marginTop: 4 }}>
                <span className="bio-badge-dot" />
                {t('sim_badge')}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ═════════════════════════════════════════════════════════════════════════════
function VueRecap({ constantes, onContinuer, onRecommencer }) {
  const { t } = useTranslation()
  const alerteCritique = CLES_VITALES.some(
    cle => evaluerCouleur(cle, constantes?.[cle]) === 'rouge'
  )

  return (
    <div className="constantes-layout">

      <div className="constantes-header">
        <span className="eyebrow">{t('const_etape_titre')}</span>
        <h2 className="kiosk-titre-sm">{t('const_bilan_titre')}</h2>
        <p className="kiosk-soustitre">{t('const_bilan_sous_titre')}</p>
      </div>

      <div className="stabilisation-ok" role="status">
        {t('const_bilan_complet')}
      </div>

      {alerteCritique && (
        <div className="kiosk-alerte kiosk-alerte--urgence" role="alert">
          {t('const_alerte_critique')}
        </div>
      )}

      <BiometrieDisplay constantes={constantes} enCours={false} />

      <div className="kiosk-actions constantes-actions">
        <button className="kiosk-btn kiosk-btn--primary" onClick={onContinuer}>
          {t('continuer')}
        </button>
        <button className="kiosk-btn kiosk-btn--secondary" onClick={onRecommencer}>
          {t('const_refaire')}
        </button>
      </div>

    </div>
  )
}

// ═════════════════════════════════════════════════════════════════════════════
// Saisie KF-65R : SYS / DIA / PUL
// ═════════════════════════════════════════════════════════════════════════════
function evaluerCouleurKF65R(type, v) {
  if (type === 'sys') {
    if (v > 160 || v < 90) return 'rouge'
    if (v >= 130) return 'orange'
    return 'vert'
  }
  // dia
  if (v > 100 || v < 60) return 'rouge'
  if (v >= 85) return 'orange'
  return 'vert'
}

function SaisieKF65R({ instruction, onValider, t, modeIllettré = false, langue = 'fr' }) {
  const { parler } = useTextToSpeech()
  const [sys, setSys] = useState('')
  const [dia, setDia] = useState('')
  const [pul, setPul] = useState('')
  const [focusChamp, setFocusChamp] = useState(null)
  const [champVocal, setChampVocal] = useState(null) // label visuel champ actif en écoute
  const [ecouteIll, setEcouteIll]   = useState(false)
  const [champConf, setChampConf]   = useState(null) // 'sys'|'dia'|'pul' en attente de ✓/↺

  // Refs pour mode illettré — raw SR (évite cancel TTS de useVoiceInput)
  const recoRef    = useRef(null)
  const noResRef   = useRef(null)
  const timersIll  = useRef([])
  const lancerRef  = useRef(null)
  const ecouteRef  = useRef(false)
  const sysIllRef  = useRef('')   // valeur sys sans closure stale
  const diaIllRef  = useRef('')   // valeur dia sans closure stale
  const pulIllRef  = useRef('')   // valeur pul sans closure stale

  const clearAllIll = () => { timersIll.current.forEach(clearTimeout); timersIll.current = []; clearTimeout(noResRef.current) }
  const afterIll = (ms, fn) => { const id = setTimeout(fn, ms); timersIll.current.push(id); return id }
  const stopRecoIll = () => {
    clearTimeout(noResRef.current)
    ecouteRef.current = false
    setEcouteIll(false)
    if (!recoRef.current) return
    recoRef.current.onresult = null
    recoRef.current.onend    = null
    recoRef.current.onerror  = null
    try { recoRef.current.stop() } catch { /* ignoré */ }
    recoRef.current = null
  }

  // Hooks useVoiceInput — conservés pour les boutons manuels en mode normal
  const voixSys = useVoiceInput({ langue, onResult: (tr) => { const v = tr.replace(/\D/g,'').slice(0,3); if (v) setSys(v) } })
  const voixDia = useVoiceInput({ langue, onResult: (tr) => { const v = tr.replace(/\D/g,'').slice(0,3); if (v) setDia(v) } })
  const voixPul = useVoiceInput({ langue, onResult: (tr) => { const v = tr.replace(/\D/g,'').slice(0,3); if (v) setPul(v) } })

  // Mode illettré — lance la reco brute sur un champ (SYS/DIA/PUL)
  const lancerRecoChamp = (champ) => {
    if (!SR_API_C) return
    stopRecoIll()
    window.speechSynthesis?.cancel()
    const reco = new SR_API_C()
    reco.lang            = LANG_BCP_C[langue] ?? 'fr-FR'
    reco.continuous      = false
    reco.interimResults  = false
    reco.maxAlternatives = 1
    recoRef.current      = reco
    ecouteRef.current    = true
    setEcouteIll(true)
    setChampVocal(champ)
    console.log('[ILL-KF] Reco lancée —', champ)

    // 8s sans résultat → "pas entendu" + relance
    noResRef.current = setTimeout(() => {
      stopRecoIll()
      console.log('[ILL-KF] Timeout 8s —', champ)
      const d = parlerEnMorceaux(t('ill_pas_entendu'), langue)
      afterIll(d, () => lancerRef.current?.(champ))
    }, 8000)

    reco.onresult = (e) => {
      clearTimeout(noResRef.current)
      const transcript = Array.from(e.results).filter(r => r.isFinal).map(r => r[0].transcript).join(' ').trim()
      console.log('[ILL-KF] Résultat', champ, ':', transcript)
      stopRecoIll()
      const val = transcript.replace(/\D/g, '').slice(0, 3)
      if (!val) {
        const d = parlerEnMorceaux(t('ill_pas_entendu'), langue)
        afterIll(d, () => lancerRef.current?.(champ))
        return
      }
      // Valeur capturée → afficher + attendre confirmation ✓/↺
      if (champ === 'sys') { sysIllRef.current = val; setSys(val) }
      else if (champ === 'dia') { diaIllRef.current = val; setDia(val) }
      else if (champ === 'pul') { pulIllRef.current = val; setPul(val) }
      setChampVocal(null)
      setChampConf(champ)
    }

    reco.onerror = (e) => {
      clearTimeout(noResRef.current)
      console.log('[ILL-KF] Erreur', champ, ':', e.error)
      stopRecoIll()
      afterIll(600, () => lancerRef.current?.(champ))
    }

    reco.onend = () => {
      clearTimeout(noResRef.current)
      if (!ecouteRef.current) return // annulé par stopRecoIll
      console.log('[ILL-KF] onend sans résultat —', champ)
      recoRef.current = null; ecouteRef.current = false; setEcouteIll(false)
      const d = parlerEnMorceaux(t('ill_pas_entendu'), langue)
      afterIll(d, () => lancerRef.current?.(champ))
    }

    reco.start()
  }
  lancerRef.current = lancerRecoChamp

  // Mode illettré : TTS "premier chiffre" → lancer SYS au montage
  useEffect(() => {
    if (!modeIllettré) return
    const d = parlerEnMorceaux(t('ill_tension_sys'), langue)
    afterIll(d, () => lancerRef.current?.('sys'))
    return () => { clearAllIll(); stopRecoIll() }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => () => { if (modeIllettré) { clearAllIll(); stopRecoIll() } }, [])

  const sysN = Number(sys)
  const diaN = Number(dia)
  const pulN = Number(pul)

  const sysValide = sys !== '' && sysN >= 70 && sysN <= 200
  const diaValide = dia !== '' && diaN >= 40 && diaN <= 130
  const pulValide = pul !== '' && pulN >= 40 && pulN <= 180
  const peutValider = sysValide && diaValide && pulValide

  const couleurSys = sysValide ? evaluerCouleurKF65R('sys', sysN) : null
  const couleurDia = diaValide ? evaluerCouleurKF65R('dia', diaN) : null

  return (
    <div className="tension-manuelle">
      {/* Keyframe pulse rouge */}
      <style>{`@keyframes pulse-kf{0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,.7)}70%{box-shadow:0 0 0 20px rgba(239,68,68,0)}}`}</style>

      <p className="kiosk-soustitre">{instruction}</p>

      {/* Mode illettré : en cours d'écoute */}
      {modeIllettré && ecouteIll && champVocal && (
        <div style={{ display:'flex', flexDirection:'column', alignItems:'center', gap:12, marginBottom:12 }}>
          <div style={{ width:60, height:60, borderRadius:'50%', background:'#ef4444', animation:'pulse-kf 1.3s ease-out infinite' }} />
          <div style={{ fontSize:'1.2rem', color:'#f8fafc', fontWeight:700 }}>
            {t('ill_ecoute')} — {champVocal === 'sys' ? t('tension_sys') : champVocal === 'dia' ? t('tension_dia') : t('tension_pul')}
          </div>
        </div>
      )}

      {/* Mode illettré : confirmation ✓/↺ après capture d'une valeur */}
      {modeIllettré && champConf && (
        <div style={{ display:'flex', flexDirection:'column', alignItems:'center', gap:16, marginBottom:16 }}>
          <div style={{ fontSize:'3.5rem', fontWeight:900, color:'#f8fafc', lineHeight:1 }}>
            {champConf === 'sys' ? sys : champConf === 'dia' ? dia : pul}
          </div>
          <div style={{ display:'flex', gap:20 }}>
            <button onClick={() => {
              const c = champConf; setChampConf(null)
              if (c === 'sys') {
                const d = parlerEnMorceaux(t('ill_tension_dia'), langue); afterIll(d, () => lancerRef.current?.('dia'))
              } else if (c === 'dia') {
                const d = parlerEnMorceaux(t('ill_tension_pul'), langue); afterIll(d, () => lancerRef.current?.('pul'))
              } else {
                afterIll(200, () => onValider({ bp_systolic: Number(sysIllRef.current), bp_diastolic: Number(diaIllRef.current), heart_rate: Number(pulIllRef.current) }))
              }
            }} style={{ width:150, height:90, borderRadius:18, border:'none', background:'rgba(16,185,129,0.25)', color:'#10b981', fontSize:'2.5rem', fontWeight:900, cursor:'pointer', WebkitTapHighlightColor:'transparent' }}>
              ✓
            </button>
            <button onClick={() => {
              const c = champConf; setChampConf(null)
              if (c === 'sys') { sysIllRef.current = ''; setSys('') }
              else if (c === 'dia') { diaIllRef.current = ''; setDia('') }
              else { pulIllRef.current = ''; setPul('') }
              lancerRef.current?.(c)
            }} style={{ width:150, height:90, borderRadius:18, border:'none', background:'rgba(249,115,22,0.25)', color:'#f97316', fontSize:'2rem', fontWeight:900, cursor:'pointer', WebkitTapHighlightColor:'transparent' }}>
              ↺
            </button>
          </div>
        </div>
      )}

      <div className="tension-inputs">
        <div className="tension-input-groupe">
          <label className="tension-input-label" htmlFor="kf65r-sys">{t('tension_sys')}</label>
          <input
            id="kf65r-sys" type="number"
            className={`tension-input${couleurSys ? ` tension-input--${couleurSys}` : ''}`}
            placeholder="120" value={sys} onChange={e => setSys(e.target.value)}
            min={70} max={200} inputMode="none"
            onFocus={() => setFocusChamp('sys')} onClick={() => setFocusChamp('sys')}
          />
          {couleurSys && (
            <div className={`bio-badge bio-badge--${couleurSys}`} style={{ alignSelf:'center', marginTop:4 }}>
              <span className="bio-badge-dot" />
              {t(couleurSys === 'vert' ? 'bio_normal' : couleurSys === 'orange' ? 'bio_attention' : 'bio_critique')}
            </div>
          )}
          {modeIllettré && SR_API_C && (
            <button onClick={() => lancerRef.current?.('sys')} style={{
              marginTop:4, padding:'8px 16px', borderRadius:8,
              border:'1px solid rgba(0,212,255,0.3)',
              background: champVocal === 'sys' && ecouteIll ? 'rgba(0,212,255,0.25)' : 'rgba(0,212,255,0.1)',
              color:'#00d4ff', fontSize:'0.9rem', cursor:'pointer',
            }}>
              {champVocal === 'sys' && ecouteIll ? '⏹ Stop' : '🎤 SYS'}
            </button>
          )}
        </div>

        <div className="tension-input-groupe">
          <label className="tension-input-label" htmlFor="kf65r-dia">{t('tension_dia')}</label>
          <input
            id="kf65r-dia" type="number"
            className={`tension-input${couleurDia ? ` tension-input--${couleurDia}` : ''}`}
            placeholder="80" value={dia} onChange={e => setDia(e.target.value)}
            min={40} max={130} inputMode="none"
            onFocus={() => setFocusChamp('dia')} onClick={() => setFocusChamp('dia')}
          />
          {couleurDia && (
            <div className={`bio-badge bio-badge--${couleurDia}`} style={{ alignSelf:'center', marginTop:4 }}>
              <span className="bio-badge-dot" />
              {t(couleurDia === 'vert' ? 'bio_normal' : couleurDia === 'orange' ? 'bio_attention' : 'bio_critique')}
            </div>
          )}
          {modeIllettré && SR_API_C && (
            <button onClick={() => lancerRef.current?.('dia')} style={{
              marginTop:4, padding:'8px 16px', borderRadius:8,
              border:'1px solid rgba(0,212,255,0.3)',
              background: champVocal === 'dia' && ecouteIll ? 'rgba(0,212,255,0.25)' : 'rgba(0,212,255,0.1)',
              color:'#00d4ff', fontSize:'0.9rem', cursor:'pointer',
            }}>
              {champVocal === 'dia' && ecouteIll ? '⏹ Stop' : '🎤 DIA'}
            </button>
          )}
        </div>

        <div className="tension-input-groupe">
          <label className="tension-input-label" htmlFor="kf65r-pul">{t('tension_pul')}</label>
          <input
            id="kf65r-pul" type="number" className="tension-input"
            placeholder="72" value={pul} onChange={e => setPul(e.target.value)}
            min={40} max={180} inputMode="none"
            onFocus={() => setFocusChamp('pul')} onClick={() => setFocusChamp('pul')}
          />
          {modeIllettré && SR_API_C && (
            <button onClick={() => lancerRef.current?.('pul')} style={{
              marginTop:4, padding:'8px 16px', borderRadius:8,
              border:'1px solid rgba(0,212,255,0.3)',
              background: champVocal === 'pul' && ecouteIll ? 'rgba(0,212,255,0.25)' : 'rgba(0,212,255,0.1)',
              color:'#00d4ff', fontSize:'0.9rem', cursor:'pointer',
            }}>
              {champVocal === 'pul' && ecouteIll ? '⏹ Stop' : '🎤 PUL'}
            </button>
          )}
        </div>
      </div>

      {focusChamp && (
        <ClavierNumerique
          value={focusChamp === 'sys' ? sys : focusChamp === 'dia' ? dia : pul}
          onChange={focusChamp === 'sys' ? setSys : focusChamp === 'dia' ? setDia : setPul}
          onConfirm={() => setFocusChamp(null)}
          onFermer={() => setFocusChamp(null)}
          maxLength={3}
        />
      )}

      <button
        className="kiosk-btn kiosk-btn--primary"
        disabled={!peutValider}
        onClick={() => onValider({ bp_systolic: sysN, bp_diastolic: diaN, heart_rate: pulN })}
      >
        {t('const_kf65r_valider')}
      </button>
    </div>
  )
}

