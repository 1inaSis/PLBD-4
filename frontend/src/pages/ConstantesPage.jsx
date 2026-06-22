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
      spo2:       Math.floor(Math.random() * 4)  + 96,
      heart_rate: Math.floor(Math.random() * 21) + 65,
    }),
    double:         true,
    label:          'const_spo2_label',
    instruction:    'guide3_spo2',
    instructionTTS: 'tts_instruction_spo2',
    messageNull:    'const_spo2_null',
    icone:        '🫁',
    illustration: IllustrationSpo2,
    valeurs: [
      { cle: 'spo2',       label: 'bio_spo2',      unite: '%',   formatter: (v) => Number(v).toFixed(1) },
      { cle: 'heart_rate', label: 'const_fc_label', unite: 'bpm', formatter: (v) => Math.round(Number(v)) },
    ],
  },

  {
    cle:            'bp_systolic',
    typeMesure:     'tension',
    manuelle:       true,
    instruction:    'const_bp_guide',
    instructionTTS: 'tts_instruction_tension',
    label:       'const_bp_label',
    unite:       'mmHg',
    icone:       '💉',
    illustration: IllustrationTension,
    formatter:   (v, all) => `${Math.round(v)} / ${Math.round(all?.bp_diastolic ?? 0)}`,
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
    if (etat !== ETAT.ATTENTE || enFetchRef.current || etapeActuelle.simulee) return

    setMessageCapture(null)
    enFetchRef.current = true

    if (etapeActuelle.simulerLocal) {
      // Simulation locale : délai 3s puis injection des valeurs aléatoires
      const timer = setTimeout(() => {
        const valeurs = etapeActuelle.simulerValeurs ? etapeActuelle.simulerValeurs() : {}
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
    if (etat === ETAT.ATTENTE && valeurActuelle != null) {
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

  // ── Valider tension saisie manuelle ─────────────────────────────────────────
  const validerTensionManuelle = ({ bp_systolic, bp_diastolic }) => {
    setConstantesLocal(prev => ({ ...prev, bp_systolic, bp_diastolic }))
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
function VueMesure({
  etape, indexEtape, total, etat, compte, valeur, constantes,
  erreur, messageCapture,
  onLancerMesure, onEtapeSuivante, onReessayer, onValiderManuel, onRetour,
}) {
  const { t, langue }  = useTranslation()
  const { parler, arreter, estEnTrainDeParler, supporte } = useTextToSpeech()
  const estSimulee    = !!etape.simulee
  const estManuelle   = !!etape.manuelle

  const texteInstruction = etape.instructionTTS ? t(etape.instructionTTS) : null

  // Lecture auto une fois à chaque nouvelle étape
  useEffect(() => {
    if (texteInstruction) parler(texteInstruction, langue)
    return arreter
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [indexEtape])

  const relireInstruction = () => { if (texteInstruction) parler(texteInstruction, langue) }
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

        {/* PRET : illustration + instruction + bouton Mesurer (température / SpO₂) */}
        {etat === ETAT.PRET && !estSimulee && !estManuelle && (
          <>
            {Illustration && (
              <div className="illustration-wrapper">
                <Illustration />
              </div>
            )}
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

        {/* PRET : saisie manuelle tension artérielle */}
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
            <SaisieTension
              instruction={t(etape.instruction ?? 'const_bp_guide')}
              onValider={onValiderManuel}
              t={t}
            />
          </>
        )}

        {/* COMPTE : compte à rebours SVG circulaire 5→1 */}
        {etat === ETAT.COMPTE && (
          <div className="seq-attente">
            <p className="kiosk-soustitre">{t('const_preparez')}</p>
            <CompteReboursCirculaire compte={compte ?? 5} role="status" aria-live="assertive" />
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

            {/* Mesure réelle réussie : confirmation + bouton */}
            {!estSimulee && messageCapture !== 'timeout' && (
              <>
                <div className="seq-ok" role="status">{t('const_mesure_ok')}</div>
                <button className="kiosk-btn kiosk-btn--primary" onClick={onEtapeSuivante}>
                  {estDerniere ? t('const_voir_bilan') : t('const_suivante')}
                </button>
              </>
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
// Saisie manuelle de la tension artérielle
// ═════════════════════════════════════════════════════════════════════════════
function evaluerCouleurTension(sys, dia) {
  if (sys > 160 || sys < 90 || dia > 100 || dia < 60) return 'rouge'
  if (sys >= 130 || dia >= 85) return 'orange'
  return 'vert'
}

function SaisieTension({ instruction, onValider, t }) {
  const [sys, setSys] = useState('')
  const [dia, setDia] = useState('')

  const sysN = Number(sys)
  const diaN = Number(dia)
  const peutValider = sys !== '' && dia !== '' && sysN > 0 && diaN > 0
  const couleur = peutValider ? evaluerCouleurTension(sysN, diaN) : null

  const LIBELLES_TENSION = { vert: t('bio_normal'), orange: t('bio_attention'), rouge: t('bio_critique') }

  return (
    <div className="tension-manuelle">
      <p className="kiosk-soustitre">{instruction}</p>

      <div className="tension-inputs">
        <div className="tension-input-groupe">
          <label className="tension-input-label" htmlFor="tension-sys">
            {t('tension_systolique')}
          </label>
          <input
            id="tension-sys"
            type="number"
            className="tension-input"
            placeholder="120"
            value={sys}
            onChange={e => setSys(e.target.value)}
            min={40} max={300}
            inputMode="numeric"
          />
        </div>

        <span className="tension-separateur">/</span>

        <div className="tension-input-groupe">
          <label className="tension-input-label" htmlFor="tension-dia">
            {t('tension_diastolique')}
          </label>
          <input
            id="tension-dia"
            type="number"
            className="tension-input"
            placeholder="80"
            value={dia}
            onChange={e => setDia(e.target.value)}
            min={20} max={200}
            inputMode="numeric"
          />
        </div>
      </div>

      {couleur && (
        <div className={`bio-badge bio-badge--${couleur}`} style={{ alignSelf: 'center' }}>
          <span className="bio-badge-dot" />
          {LIBELLES_TENSION[couleur]}
        </div>
      )}

      <button
        className="kiosk-btn kiosk-btn--primary"
        disabled={!peutValider}
        onClick={() => onValider({ bp_systolic: sysN, bp_diastolic: diaN })}
      >
        {t('const_bp_valider')}
      </button>
    </div>
  )
}

// ── Compte à rebours SVG circulaire ──────────────────────────────────────────
const CDR_R = 42
const CDR_CIRC = 2 * Math.PI * CDR_R  // ≈ 263.9

function CompteReboursCirculaire({ compte, ...props }) {
  const pct = Math.max(0, Math.min(compte, 5)) / 5
  const dashoffset = CDR_CIRC * (1 - pct)
  return (
    <div className="countdown-svg-wrap" {...props}>
      <svg width="140" height="140" viewBox="0 0 100 100" className="countdown-ring">
        <defs>
          <linearGradient id="cdr-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#00d4ff" />
            <stop offset="100%" stopColor="#7c3aed" />
          </linearGradient>
        </defs>
        <circle className="countdown-ring__track" cx="50" cy="50" r={CDR_R} />
        <circle
          className="countdown-ring__circle"
          cx="50" cy="50" r={CDR_R}
          strokeDasharray={CDR_CIRC}
          strokeDashoffset={dashoffset}
        />
      </svg>
      <span className="countdown-svg-num">{compte}</span>
    </div>
  )
}
