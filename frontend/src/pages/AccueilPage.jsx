import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePatient } from '../context/PatientContext'
import { scannerCIN, saisirManuel, abandonnerSession } from '../services/api'
import IndicateurEtape from '../components/IndicateurEtape'
import ConfirmationPatient from '../components/ConfirmationPatient'
import { IllustrationScanCIN } from '../components/IllustrationsGestes'
import SelecteurLangue from '../components/SelecteurLangue'
import GuideEtape from '../components/GuideEtape'
import ModalInactivite from '../components/ModalInactivite'
import BoutonPleinEcran from '../components/BoutonPleinEcran'
import { useTranslation } from '../hooks/useTranslation'
import { useTextToSpeech } from '../hooks/useTextToSpeech'

import { useInactivite } from '../hooks/useInactivite'
import { useFullscreen } from '../hooks/useFullscreen'
import ClavierNumerique from '../components/ClavierNumerique'
import ClavierAlpha from '../components/ClavierAlpha'
import '../styles/kiosk.css'

const VUE = {
  ACCUEIL:      'accueil',
  SCAN:         'scan',
  FORMULAIRE:   'formulaire',
  CONFIRMATION: 'confirmation',
  BIENVENUE:    'bienvenue',
}

export default function AccueilPage() {
  const navigate = useNavigate()
  const { setIdentite, connecterBorne, reinitialiser, patient, audioActif, setAudioActif, modeIllettré, setModeIllettré } = usePatient()
  const { t, langue } = useTranslation()
  const { parler, arreter, activer } = useTextToSpeech()

  const [vue, setVue]                         = useState(VUE.ACCUEIL)
  const [donneesScan, setDonneesScan]         = useState(null)
  const [erreur, setErreur]                   = useState(null)
  const [wsConnecte, setWsConnecte]           = useState(false)
  const [prenomBienvenue, setPrenomBienvenue] = useState('')

  // Inactivité
  const handleExpiration = useCallback(async () => {
    if (patient.session_id) await abandonnerSession(patient.session_id)
    reinitialiser()
    navigate('/')
  }, [patient.session_id, reinitialiser, navigate])
  const { avertissement, compte, reset } = useInactivite({ onExpiration: handleExpiration })
  const { enterFullscreen } = useFullscreen()

  // ── Choix initial : 📖 sais lire / 🎤 ne sais pas lire ──────────────────
  const [modeChoixLecture, setModeChoixLecture] = useState(true)

  const choisirLecture = () => {
    activer()
    setModeIllettré(false)
    setModeChoixLecture(false)
  }

  const choisirIllettré = () => {
    activer()            // déverrouille speechSynthesis (geste utilisateur)
    setAudioActif(true)
    setModeIllettré(true)
    setModeChoixLecture(false)
  }

  // ── Formulaire manuel ─────────────────────────────────────────────────────
  const [sessionManuelId, setSessionManuelId] = useState(null)
  const [formulaire, setFormulaire]           = useState({ nom: '', prenom: '', date_naissance: '' })
  const [erreurForm, setErreurForm]           = useState(null)
  const [enSoumission, setEnSoumission]       = useState(false)
  const [focusChamp, setFocusChamp]           = useState(null)

  // ── Auto-navigation après bienvenue ──────────────────────────────────────
  useEffect(() => {
    if (vue !== VUE.BIENVENUE) return
    const timer = setTimeout(() => navigate('/questionnaire'), 2000)
    return () => clearTimeout(timer)
  }, [vue, navigate])

  // TTS bienvenue personnalisée
  useEffect(() => {
    if (vue !== VUE.BIENVENUE || !prenomBienvenue) return
    const timer = setTimeout(() => parler(t('tts_bienvenue', { prenom: prenomBienvenue }), langue), 300)
    return () => { clearTimeout(timer); arreter() }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vue])

  // TTS instruction scan
  useEffect(() => {
    if (vue !== VUE.SCAN) return
    const timer = setTimeout(() => parler(t('tts_scan'), langue), 300)
    return () => { clearTimeout(timer); arreter() }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vue])

  // TTS accueil quand audio activé (mode normal)
  useEffect(() => {
    if (!audioActif || vue !== VUE.ACCUEIL || modeIllettré) return
    parler(t('tts_accueil'), langue)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audioActif])

  // Initialisation WS
  useEffect(() => {
    reinitialiser()
    const ws = connecterBorne((msg) => {
      if (msg.event === 'constantes_update') console.log('[WS borne] Constantes :', msg.data)
    })
    ws.onopen = () => setWsConnecte(true)
    const _prev = ws.onclose
    ws.onclose = (e) => { setWsConnecte(false); _prev?.(e) }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Toggle guidage vocal ──────────────────────────────────────────────────
  const toggleAudio = () => {
    if (audioActif) { arreter(); setAudioActif(false) }
    else { activer(); setAudioActif(true) }
  }

  // ── Scan CIN ─────────────────────────────────────────────────────────────
  const lancerScan = async () => {
    activer(); enterFullscreen()
    setVue(VUE.SCAN); setErreur(null); setErreurForm(null)
    try {
      const data = await scannerCIN()
      if (data.formulaire_manuel) {
        setSessionManuelId(data.session_id || null)
        setFormulaire({ nom: data.nom || '', prenom: data.prenom || '', date_naissance: data.date_naissance || '' })
        setVue(VUE.FORMULAIRE)
      } else {
        setDonneesScan(data); setVue(VUE.CONFIRMATION)
      }
    } catch {
      setSessionManuelId(null)
      setFormulaire({ nom: '', prenom: '', date_naissance: '' })
      setVue(VUE.FORMULAIRE)
    }
  }

  // ── Formulaire manuel ─────────────────────────────────────────────────────
  const changerChamp = (e) => { setFormulaire(p => ({ ...p, [e.target.name]: e.target.value })); setErreurForm(null) }

  const changerDate = (e) => {
    const prev = formulaire.date_naissance; const raw = e.target.value
    if (raw.length < prev.length) { setFormulaire(p => ({ ...p, date_naissance: raw })); return }
    const c = raw.replace(/\D/g, '')
    let f = c.length <= 2 ? c : c.length <= 4 ? c.slice(0,2)+'/'+c.slice(2) : c.slice(0,2)+'/'+c.slice(2,4)+'/'+c.slice(4,8)
    setFormulaire(p => ({ ...p, date_naissance: f })); setErreurForm(null)
  }

  const validerManuel = async () => {
    activer()
    const { nom, prenom, date_naissance } = formulaire
    if (!nom.trim() || !prenom.trim()) { setErreurForm(t('erreur_nom_prenom_requis')); return }
    setEnSoumission(true); setErreurForm(null)
    try {
      const data = await saisirManuel(sessionManuelId, nom.trim(), prenom.trim(), date_naissance.trim())
      setIdentite({ session_id: data.session_id, nom: data.nom, prenom: data.prenom, age: data.age, sexe: data.sexe ?? -1, numero_cin: '' })
      setPrenomBienvenue(data.prenom); setVue(VUE.BIENVENUE)
    } catch (err) { setErreurForm(`Erreur : ${err.message}`) }
    finally { setEnSoumission(false) }
  }

  // ── Confirmation scan ─────────────────────────────────────────────────────
  const confirmer = () => {
    activer()
    setIdentite({ session_id: donneesScan.session_id, nom: donneesScan.nom, prenom: donneesScan.prenom, age: donneesScan.age, sexe: donneesScan.sexe, numero_cin: donneesScan.numero_cin })
    setPrenomBienvenue(donneesScan.prenom); setVue(VUE.BIENVENUE)
  }
  const recommencer = () => { setDonneesScan(null); setVue(VUE.ACCUEIL) }

  // ── Callback fin identification illettré ──────────────────────────────────
  const onIdentificationTerminée = async (prenom, nom, age, sexe) => {
    try {
      const data = await saisirManuel(null, nom || 'Patient', prenom || 'Patient', '')
      setIdentite({ session_id: data.session_id, nom: nom || data.nom, prenom: prenom || data.prenom, age: age ?? data.age, sexe: sexe ?? data.sexe ?? -1, numero_cin: '' })
      setPrenomBienvenue(prenom || data.prenom || '')
    } catch {
      setIdentite({ session_id: null, nom: nom || '', prenom: prenom || '', age: age ?? null, sexe: sexe ?? -1, numero_cin: '' })
      setPrenomBienvenue(prenom || '')
    }
    setVue(VUE.BIENVENUE)
  }

  return (
    <div className="kiosk-shell" dir={langue === 'ar' ? 'rtl' : 'ltr'}>
      <IndicateurEtape etapeCourante={1} />
      <SelecteurLangue />
      <BoutonPleinEcran />
      <ModalInactivite avertissement={avertissement} compte={compte} onContinuer={reset} />

      {/* ── ÉCRAN 1 — Modal choix lecture (📖 / 🎤) ──────────────── */}
      {modeChoixLecture && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 3000,
          background: 'rgba(6,11,20,0.97)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          gap: 24, flexWrap: 'wrap', padding: 24,
        }}>
          {/* 📖 Je sais lire */}
          <button
            onClick={choisirLecture}
            style={{
              width: 180, height: 180, borderRadius: 24,
              background: 'rgba(255,255,255,0.08)', border: '2px solid rgba(255,255,255,0.25)',
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              gap: 12, cursor: 'pointer', WebkitTapHighlightColor: 'transparent',
            }}
          >
            <span style={{ fontSize: '4.5rem', lineHeight: 1 }}>📖</span>
            <span style={{ color: '#f8fafc', fontSize: '1rem', fontWeight: 700, textAlign: 'center' }}>
              {t('illettré_oui_lecture')}
            </span>
          </button>
          {/* 🎤 Je ne sais pas lire */}
          <button
            onClick={choisirIllettré}
            style={{
              width: 180, height: 180, borderRadius: 24,
              background: 'rgba(0,212,255,0.12)', border: '2px solid rgba(0,212,255,0.4)',
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              gap: 12, cursor: 'pointer', WebkitTapHighlightColor: 'transparent',
            }}
          >
            <span style={{ fontSize: '4.5rem', lineHeight: 1 }}>🎤</span>
            <span style={{ color: '#00d4ff', fontSize: '1rem', fontWeight: 700, textAlign: 'center' }}>
              {t('illettré_non_lecture')}
            </span>
          </button>
        </div>
      )}

      {/* ── ÉCRAN 2 — Identification illettré (4 étapes) ─────────── */}
      {modeIllettré && !modeChoixLecture && vue === VUE.ACCUEIL && (
        <VueIdentificationIllettré
          langue={langue}
          onTerminé={onIdentificationTerminée}
        />
      )}

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

      <div className={`ws-badge ${wsConnecte ? 'ws-badge--ok' : 'ws-badge--off'}`}>
        {wsConnecte ? '● Connecté' : '○ Hors ligne'}
      </div>

      {/* ── Accueil (mode normal uniquement) ────────────────────── */}
      {vue === VUE.ACCUEIL && !modeIllettré && (
        <div className="accueil-fx" aria-hidden="true">
          <div className="accueil-particles">
            {Array.from({ length: 20 }, (_, i) => <span key={i} />)}
          </div>
          <svg className="accueil-ecg" viewBox="0 0 1000 60" preserveAspectRatio="none">
            <path className="ecg-path" d="M0,30 L80,30 L100,5 L105,55 L110,30 L205,30 L225,5 L230,55 L235,30 L330,30 L350,5 L355,55 L360,30 L455,30 L475,5 L480,55 L485,30 L580,30 L600,5 L605,55 L610,30 L705,30 L725,5 L730,55 L735,30 L830,30 L850,5 L855,55 L860,30 L955,30 L975,5 L980,55 L985,30 L1000,30" />
          </svg>
          <svg className="accueil-croix-medicale" viewBox="0 0 200 200" aria-hidden="true">
            <rect x="80" y="20" width="40" height="160" rx="8" />
            <rect x="20" y="80" width="160" height="40" rx="8" />
          </svg>
        </div>
      )}
      {vue === VUE.ACCUEIL && !modeIllettré && (
        <div className="kiosk-center">
          <div className="kiosk-card">
            <span className="eyebrow">{t('titre_app')}</span>
            <h1 className="kiosk-titre">{t('bienvenue_principale')}</h1>
            <p className="kiosk-soustitre">{t('sous_titre')}</p>
            <GuideEtape etape={1} />
            <div className="illustration-wrapper"><IllustrationScanCIN /></div>
            {erreur && <div className="kiosk-alerte" role="alert">{erreur}</div>}
            <button className="kiosk-btn kiosk-btn--primary" onClick={lancerScan}>
              <svg className="kiosk-btn-icone" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="2" y="5" width="20" height="14" rx="2" /><path d="M2 10h20" />
              </svg>
              {t('scanner_btn')}
            </button>
            <button
              className="kiosk-btn kiosk-btn--secondary"
              onClick={() => { setFormulaire({ nom: '', prenom: '', date_naissance: '' }); setSessionManuelId(null); setVue(VUE.FORMULAIRE) }}
            >
              {t('saisie_manuelle')}
            </button>
            <button
              className="kiosk-btn kiosk-btn--secondary"
              onClick={toggleAudio}
              style={{
                marginTop: 8, fontSize: '0.95em',
                background: audioActif ? 'rgba(20,184,166,0.18)' : 'rgba(15,23,42,0.5)',
                border: audioActif ? '1px solid rgba(20,184,166,0.5)' : '1px solid rgba(148,163,184,0.2)',
                color: audioActif ? '#2dd4bf' : 'rgba(148,163,184,0.7)',
              }}
              aria-pressed={audioActif}
            >
              {audioActif
                ? <><span className="audio-active-dot" aria-hidden="true" /> 🔊 {t('tts_audio_desactiver')}</>
                : `🔇 ${t('tts_audio_activer')}`}
            </button>
          </div>
        </div>
      )}

      {/* ── Scan en cours ─────────────────────────────────────────── */}
      {vue === VUE.SCAN && (
        <div className="kiosk-center">
          <div className="kiosk-card kiosk-card--centree">
            <div className="camera-active-badge" role="status" aria-live="polite">
              <span className="camera-active-dot" aria-hidden="true" />{t('camera_active')}
            </div>
            <div className="kiosk-spinner" aria-label="Chargement" />
            <h2 className="kiosk-titre-sm">{t('scan_en_cours')}</h2>
            <p className="kiosk-soustitre">{t('scan_instruction')}</p>
          </div>
        </div>
      )}

      {/* ── Formulaire manuel ──────────────────────────────────────── */}
      {vue === VUE.FORMULAIRE && (
        <div className="kiosk-center">
          <div className="kiosk-card">
            <span className="eyebrow">{t('saisie_manuelle')}</span>
            <h2 className="kiosk-titre-sm">{t('bienvenue')}</h2>
            {erreurForm && <div className="kiosk-alerte" role="alert">{erreurForm}</div>}
            <div className="cin-form">
              <div className="cin-field">
                <label className="cin-label" htmlFor="cin-nom">{t('nom')}</label>
                <input id="cin-nom" className="cin-input" name="nom" type="text" placeholder={t('nom')}
                  value={formulaire.nom} onChange={changerChamp} autoComplete="family-name"
                  inputMode="none" onFocus={() => setFocusChamp('nom')} onClick={() => setFocusChamp('nom')} />
              </div>
              <div className="cin-field">
                <label className="cin-label" htmlFor="cin-prenom">{t('prenom')}</label>
                <input id="cin-prenom" className="cin-input" name="prenom" type="text" placeholder={t('prenom')}
                  value={formulaire.prenom} onChange={changerChamp} autoComplete="given-name"
                  inputMode="none" onFocus={() => setFocusChamp('prenom')} onClick={() => setFocusChamp('prenom')} />
              </div>
              <div className="cin-field">
                <label className="cin-label" htmlFor="cin-ddn">{t('date_naissance')}</label>
                <input id="cin-ddn" className="cin-input" name="date_naissance" type="text"
                  placeholder="JJ/MM/AAAA" value={formulaire.date_naissance} onChange={changerDate}
                  inputMode="none" maxLength={10} onFocus={() => setFocusChamp('date')} onClick={() => setFocusChamp('date')} />
                <span className="cin-hint">{t('format_date_hint')}</span>
              </div>
            </div>
            {focusChamp === 'date' && (
              <ClavierNumerique value={formulaire.date_naissance}
                onChange={(v) => setFormulaire(p => ({ ...p, date_naissance: v }))}
                onConfirm={() => setFocusChamp(null)} onFermer={() => setFocusChamp(null)} modeDate />
            )}
            {(focusChamp === 'nom' || focusChamp === 'prenom') && (
              <ClavierAlpha
                value={focusChamp === 'nom' ? formulaire.nom : formulaire.prenom}
                onChange={focusChamp === 'nom' ? (v) => setFormulaire(p => ({ ...p, nom: v })) : (v) => setFormulaire(p => ({ ...p, prenom: v }))}
                onConfirm={() => setFocusChamp(null)} onFermer={() => setFocusChamp(null)} langue={langue} />
            )}
            <div className="kiosk-actions">
              <button className="kiosk-btn kiosk-btn--primary" onClick={validerManuel} disabled={enSoumission}>
                {enSoumission ? '…' : t('valider')}
              </button>
              <button className="kiosk-btn kiosk-btn--secondary" onClick={() => setVue(VUE.ACCUEIL)}>
                {t('retour_scan')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Confirmation scan réussi ───────────────────────────────── */}
      {vue === VUE.CONFIRMATION && (
        <ConfirmationPatient donnees={donneesScan} onConfirmer={confirmer} onRecommencer={recommencer} />
      )}

      {/* ── Bienvenue (2s → navigation) ───────────────────────────── */}
      {vue === VUE.BIENVENUE && (
        <div className="kiosk-center">
          <div className="kiosk-card kiosk-card--centree" style={{ textAlign: 'center' }}>
            <span style={{ fontSize: '3rem' }}>👋</span>
            <h2 className="kiosk-titre-sm" style={{ marginTop: 12 }}>{t('bonjour')} {prenomBienvenue} !</h2>
            <p className="kiosk-soustitre">{t('evaluation')}</p>
            <div className="kiosk-spinner" style={{ marginTop: 16 }} aria-label="Chargement" />
          </div>
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Convertit texte parlé en nombre entier (pour l'âge)
// ─────────────────────────────────────────────────────────────────────────────
function convertirAge(transcript) {
  const digits = transcript.replace(/[^\d]/g, '')
  if (digits.length > 0) {
    const n = parseInt(digits, 10)
    if (n >= 1 && n <= 120) return n
  }
  const MOTS = {
    'zéro':0,'un':1,'une':1,'deux':2,'trois':3,'quatre':4,'cinq':5,
    'six':6,'sept':7,'huit':8,'neuf':9,'dix':10,'onze':11,'douze':12,
    'treize':13,'quatorze':14,'quinze':15,'seize':16,'vingt':20,
    'trente':30,'quarante':40,'cinquante':50,'soixante':60,'cent':100,
  }
  const lower = transcript.toLowerCase().trim()
  let total = 0; let found = false
  for (const [mot, val] of Object.entries(MOTS)) {
    if (lower.includes(mot)) { total += val; found = true }
  }
  if (found && total >= 1 && total <= 120) return total
  return null
}

// ─────────────────────────────────────────────────────────────────────────────
// ÉCRAN 2 — Identification guidée mode illettré : prénom → nom → age → sexe
// Timing basé sur setTimeout fixe (pas onend — non fiable Safari iOS)
// ─────────────────────────────────────────────────────────────────────────────
const SR_API = typeof window !== 'undefined'
  ? (window.SpeechRecognition || window.webkitSpeechRecognition)
  : null
const LANG_BCP = { fr: 'fr-FR', en: 'en-US', ar: 'ar-SA' }

// Lit un texte en morceaux de ≤50 chars (TTS chunking — évite les coupures Safari/Chrome).
// Retourne la durée totale estimée en ms.
function parlerEnMorceaux(texte, langue) {
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

// ─────────────────────────────────────────────────────────────────────────────
// ÉCRAN 2 — Identification guidée mode illettré : prénom → nom → age → sexe
// TTS chunké (≤50 chars) + setTimeout fixe + maxAlternatives=1 + 8s timeout
// ─────────────────────────────────────────────────────────────────────────────
function VueIdentificationIllettré({ langue, onTerminé }) {
  const { t } = useTranslation()

  const [etape, setEtape]        = useState('prénom')
  const [phase, setPhase]        = useState('intro')
  const [valAffichee, setValAff] = useState('')
  const [tentative, setTentative] = useState(0)
  const [ecoute, setEcoute]      = useState(false)

  const etapeRef   = useRef('prénom');   etapeRef.current = etape
  const phaseRef   = useRef('intro');    phaseRef.current = phase

  const prenomRef      = useRef('')
  const nomRef         = useRef('')
  const ageRef         = useRef(null)
  const timersRef      = useRef([])
  const recoRef        = useRef(null)
  const noResultRef    = useRef(null)   // timer 8s no-result
  const lancerRecoRef  = useRef(null)   // ref stable vers lancerReco

  const clearAll = () => {
    timersRef.current.forEach(clearTimeout)
    timersRef.current = []
    clearTimeout(noResultRef.current)
  }

  const stopReco = () => {
    clearTimeout(noResultRef.current)
    if (!recoRef.current) return
    recoRef.current.onresult = null
    recoRef.current.onend    = null
    recoRef.current.onerror  = null
    try { recoRef.current.stop() } catch { /* ignoré */ }
    recoRef.current = null
    setEcoute(false)
  }

  const after = (ms, fn) => {
    const id = setTimeout(fn, ms)
    timersRef.current.push(id)
    return id
  }

  // Fonction principale — définie à chaque render mais accessible via ref stable
  const lancerReco = () => {
    if (!SR_API) return
    stopReco()
    window.speechSynthesis?.cancel()
    const reco = new SR_API()
    reco.lang            = LANG_BCP[langue] ?? 'fr-FR'
    reco.continuous      = false
    reco.interimResults  = false
    reco.maxAlternatives = 1
    recoRef.current      = reco

    console.log('[ILL] Reco lancée')
    setPhase('ecoute')
    setEcoute(true)

    // Timer 8s — si aucun résultat → TTS "pas entendu" + relance
    noResultRef.current = setTimeout(() => {
      stopReco()
      console.log('[ILL] Timeout 8s sans résultat')
      const txt = t('ill_pas_entendu')
      const d = parlerEnMorceaux(txt, langue)
      after(d, () => lancerRecoRef.current?.())
    }, 8000)

    reco.onresult = (e) => {
      clearTimeout(noResultRef.current)
      const transcript = Array.from(e.results)
        .filter(r => r.isFinal).map(r => r[0].transcript).join(' ').trim()
      console.log('[ILL] Résultat:', transcript)
      stopReco()

      const cur = etapeRef.current
      let affiche = ''
      if (cur === 'prénom') {
        const mot = transcript.split(/\s+/)[0] || transcript
        affiche = mot.charAt(0).toUpperCase() + mot.slice(1).toLowerCase()
        prenomRef.current = affiche
      } else if (cur === 'nom') {
        const mot = transcript.split(/\s+/)[0] || transcript
        affiche = mot.toUpperCase()
        nomRef.current = affiche
      } else if (cur === 'age') {
        const n = convertirAge(transcript)
        if (!n) {
          console.log('[ILL] Âge non reconnu, relance dans 600ms')
          after(600, () => lancerRecoRef.current?.())
          return
        }
        affiche = String(n)
        ageRef.current = n
      }
      if (!affiche) return
      setValAff(affiche)

      const CLES_CONF = { prénom: 'ill_confirmer_prenom', nom: 'ill_confirmer_nom', age: 'ill_confirmer_age' }
      const txtConf = (t(CLES_CONF[cur]) || '').replace('{val}', cur === 'age' ? `${affiche} ans` : affiche)
      console.log('[ILL] TTS lancé:', txtConf)
      setPhase('conf_tts')
      const délaiConf = parlerEnMorceaux(txtConf, langue)
      console.log('[ILL] Délai avant confirmation:', délaiConf, 'ms')
      after(délaiConf, () => {
        console.log('[ILL] Confirmation affichée')
        setPhase('confirmation')
      })
    }

    reco.onerror = (e) => {
      clearTimeout(noResultRef.current)
      console.log('[ILL] Reco erreur:', e.error)
      stopReco()
      after(800, () => lancerRecoRef.current?.())
    }

    reco.onend = () => {
      clearTimeout(noResultRef.current)
      if (phaseRef.current !== 'ecoute') return
      console.log('[ILL] Reco onend sans résultat')
      recoRef.current = null
      setEcoute(false)
      const txt = t('ill_pas_entendu')
      const d = parlerEnMorceaux(txt, langue)
      after(d, () => lancerRecoRef.current?.())
    }

    reco.start()
  }
  lancerRecoRef.current = lancerReco  // Toujours à jour

  // Séquence : TTS chunké → délai calculé → lancerReco
  useEffect(() => {
    clearAll()
    stopReco()
    setPhase('intro')
    setValAff('')

    if (etape === 'sexe') {
      const txtSexe = t('ill_sexe')
      console.log('[ILL] TTS lancé:', txtSexe)
      after(300, () => parlerEnMorceaux(txtSexe, langue))
      return () => { clearAll(); stopReco() }
    }

    const CLES = { prénom: 'ill_bienvenue_prenom', nom: 'ill_bienvenue_nom', age: 'ill_bienvenue_age' }
    const txtIntro = t(CLES[etape] || '')
    console.log('[ILL] TTS lancé:', txtIntro)

    after(300, () => {
      const délai = parlerEnMorceaux(txtIntro, langue)
      console.log('[ILL] Durée TTS estimée:', délai, 'ms')
      after(délai, () => lancerRecoRef.current?.())
    })

    return () => { clearAll(); stopReco() }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [etape, tentative])

  useEffect(() => () => { clearAll(); stopReco() }, []) // démontage

  const confirmer   = () => {
    if (etape === 'prénom') setEtape('nom')
    else if (etape === 'nom') setEtape('age')
    else if (etape === 'age') setEtape('sexe')
  }
  const recommencer = () => { clearAll(); stopReco(); setTentative(n => n + 1) }
  const choisirSexe = (sexe) => onTerminé(prenomRef.current, nomRef.current, ageRef.current, sexe)

  const NUM = { prénom: 1, nom: 2, age: 3, sexe: 4 }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 2500,
      background: '#060b14',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      gap: 28, padding: 24,
    }}>
      {/* Keyframe pulse rouge */}
      <style>{`@keyframes pulse-ill{0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,.7)}70%{box-shadow:0 0 0 22px rgba(239,68,68,0)}}`}</style>

      {/* Badge */}
      <div style={{
        position: 'absolute', top: 8, right: 8,
        background: 'rgba(0,212,255,0.15)', border: '1px solid rgba(0,212,255,0.3)',
        borderRadius: 20, padding: '4px 12px', fontSize: '0.78rem', color: '#00d4ff',
      }}>
        🤝 {t('illettré_mode_badge')}
      </div>

      {/* Indicateur étape */}
      <div style={{ color: 'rgba(255,255,255,0.35)', fontSize: '0.88rem' }}>
        {NUM[etape]} / 4
      </div>

      {/* Étapes 1-3 : capture vocale */}
      {etape !== 'sexe' && (
        <>
          {/* Indicateur d'écoute ou icône micro */}
          {phase !== 'confirmation' && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 }}>
              {ecoute ? (
                <>
                  <div style={{
                    width: 72, height: 72, borderRadius: '50%',
                    background: '#ef4444',
                    animation: 'pulse-ill 1.3s ease-out infinite',
                  }} />
                  <div style={{ fontSize: '1.5rem', color: '#f8fafc', fontWeight: 700 }}>
                    {t('ill_ecoute')}
                  </div>
                </>
              ) : (
                <div style={{ fontSize: '5rem', lineHeight: 1 }}>🎤</div>
              )}
            </div>
          )}

          {/* Valeur captée */}
          {valAffichee && (
            <div style={{
              fontSize: '2.8rem', fontWeight: 700, color: '#f8fafc',
              textAlign: 'center', letterSpacing: 1,
              padding: '16px 32px', background: 'rgba(255,255,255,0.06)',
              borderRadius: 16, minWidth: 180,
            }}>
              {etape === 'age' ? `${valAffichee} ans` : valAffichee}
            </div>
          )}

          {/* Confirmation ✓ / ↺ */}
          {phase === 'confirmation' && (
            <div style={{ display: 'flex', gap: 24 }}>
              <button onClick={confirmer} style={{
                width: 180, height: 110, borderRadius: 20, border: 'none',
                background: 'rgba(16,185,129,0.22)', color: '#10b981',
                fontSize: '3rem', fontWeight: 900, cursor: 'pointer',
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4,
                WebkitTapHighlightColor: 'transparent',
              }}>
                <span>✓</span>
                <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>OK</span>
              </button>
              <button onClick={recommencer} style={{
                width: 180, height: 110, borderRadius: 20, border: 'none',
                background: 'rgba(249,115,22,0.22)', color: '#f97316',
                fontSize: '2.5rem', fontWeight: 900, cursor: 'pointer',
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4,
                WebkitTapHighlightColor: 'transparent',
              }}>
                <span>↺</span>
                <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>Recommencer</span>
              </button>
            </div>
          )}
        </>
      )}

      {/* Étape 4 : sexe */}
      {etape === 'sexe' && (
        <div style={{ display: 'flex', gap: 28 }}>
          <button onClick={() => choisirSexe(0)} style={{
            width: 180, height: 180, borderRadius: 24,
            background: 'rgba(56,189,248,0.15)', border: '2px solid rgba(56,189,248,0.4)',
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            gap: 10, cursor: 'pointer', WebkitTapHighlightColor: 'transparent',
          }}>
            <span style={{ fontSize: '4.5rem', lineHeight: 1 }}>👨</span>
            <span style={{ color: '#38bdf8', fontWeight: 700, fontSize: '1rem' }}>{t('ill_homme')}</span>
          </button>
          <button onClick={() => choisirSexe(1)} style={{
            width: 180, height: 180, borderRadius: 24,
            background: 'rgba(244,114,182,0.15)', border: '2px solid rgba(244,114,182,0.4)',
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            gap: 10, cursor: 'pointer', WebkitTapHighlightColor: 'transparent',
          }}>
            <span style={{ fontSize: '4.5rem', lineHeight: 1 }}>👩</span>
            <span style={{ color: '#f472b4', fontWeight: 700, fontSize: '1rem' }}>{t('ill_femme')}</span>
          </button>
        </div>
      )}
    </div>
  )
}
