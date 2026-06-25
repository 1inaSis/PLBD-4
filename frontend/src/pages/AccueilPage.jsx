import { useState, useEffect, useCallback } from 'react'
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
  const { setIdentite, connecterBorne, reinitialiser, patient, audioActif, setAudioActif } = usePatient()
  const { t, langue } = useTranslation()
  const { parler, arreter, activer } = useTextToSpeech()

  const [vue, setVue]                   = useState(VUE.ACCUEIL)
  const [donneesScan, setDonneesScan]   = useState(null)
  const [erreur, setErreur]             = useState(null)
  const [wsConnecte, setWsConnecte]     = useState(false)
  const [prenomBienvenue, setPrenomBienvenue] = useState('')

  // Inactivité
  const handleExpiration = useCallback(async () => {
    if (patient.session_id) await abandonnerSession(patient.session_id)
    reinitialiser()
    navigate('/')
  }, [patient.session_id, reinitialiser, navigate])
  const { avertissement, compte, reset } = useInactivite({ onExpiration: handleExpiration })
  const { enterFullscreen } = useFullscreen()

  const [sessionManuelId, setSessionManuelId] = useState(null)
  const [formulaire, setFormulaire] = useState({ nom: '', prenom: '', date_naissance: '' })
  const [erreurForm, setErreurForm] = useState(null)
  const [enSoumission, setEnSoumission] = useState(false)

  // Auto-navigation après message de bienvenue (2 s)
  useEffect(() => {
    if (vue !== VUE.BIENVENUE) return
    const timer = setTimeout(() => navigate('/questionnaire'), 2000)
    return () => clearTimeout(timer)
  }, [vue, navigate])

  // Lecture TTS — bienvenue personnalisée (300ms après affichage)
  useEffect(() => {
    if (vue !== VUE.BIENVENUE || !prenomBienvenue) return
    const timer = setTimeout(() => parler(t('tts_bienvenue', { prenom: prenomBienvenue }), langue), 300)
    return () => { clearTimeout(timer); arreter() }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vue])

  // Lecture TTS — instruction scan (300ms après passage à VUE.SCAN)
  useEffect(() => {
    if (vue !== VUE.SCAN) return
    const timer = setTimeout(() => parler(t('tts_scan'), langue), 300)
    return () => { clearTimeout(timer); arreter() }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vue])

  // Lecture TTS — accueil quand l'audio est activé sur cette vue
  useEffect(() => {
    if (!audioActif || vue !== VUE.ACCUEIL) return
    parler(t('tts_accueil'), langue)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audioActif])

  useEffect(() => {
    reinitialiser()

    const ws = connecterBorne((msg) => {
      if (msg.event === 'constantes_update') {
        console.log('[WS borne] Constantes reçues :', msg.data)
      }
    })

    ws.onopen = () => setWsConnecte(true)
    const _prevOnClose = ws.onclose
    ws.onclose = (e) => {
      setWsConnecte(false)
      _prevOnClose?.(e)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Activer / désactiver le guidage vocal ────────────────────────────────
  const toggleAudio = () => {
    if (audioActif) {
      arreter()
      setAudioActif(false)
    } else {
      activer()  // déverrouille speechSynthesis (geste utilisateur)
      setAudioActif(true)
    }
  }

  // ── Scan CIN ─────────────────────────────────────────────────────────────
  const lancerScan = async () => {
    activer()
    enterFullscreen()
    setVue(VUE.SCAN)
    setErreur(null)
    setErreurForm(null)
    try {
      const data = await scannerCIN()
      if (data.formulaire_manuel) {
        setSessionManuelId(data.session_id || null)
        setFormulaire({
          nom:            data.nom            || '',
          prenom:         data.prenom         || '',
          date_naissance: data.date_naissance || '',
        })
        setVue(VUE.FORMULAIRE)
      } else {
        setDonneesScan(data)
        setVue(VUE.CONFIRMATION)
      }
    } catch {
      setSessionManuelId(null)
      setFormulaire({ nom: '', prenom: '', date_naissance: '' })
      setVue(VUE.FORMULAIRE)
    }
  }

  // ── Formulaire manuel ─────────────────────────────────────────────────────
  const changerChamp = (e) => {
    setFormulaire((prev) => ({ ...prev, [e.target.name]: e.target.value }))
    setErreurForm(null)
  }

  const changerDate = (e) => {
    const prev = formulaire.date_naissance
    const raw  = e.target.value

    // Suppression : laisser passer sans reformatter
    if (raw.length < prev.length) {
      setFormulaire((p) => ({ ...p, date_naissance: raw }))
      setErreurForm(null)
      return
    }

    // Ne garder que les chiffres
    const chiffres = raw.replace(/\D/g, '')

    // Construire la valeur formatée JJ/MM/AAAA
    let formate = ''
    if (chiffres.length <= 2) {
      formate = chiffres
    } else if (chiffres.length <= 4) {
      formate = chiffres.slice(0, 2) + '/' + chiffres.slice(2)
    } else {
      formate = chiffres.slice(0, 2) + '/' + chiffres.slice(2, 4) + '/' + chiffres.slice(4, 8)
    }

    setFormulaire((p) => ({ ...p, date_naissance: formate }))
    setErreurForm(null)
  }

  const validerManuel = async () => {
    activer()
    const { nom, prenom, date_naissance } = formulaire
    if (!nom.trim() || !prenom.trim()) {
      setErreurForm(t('erreur_nom_prenom_requis'))
      return
    }
    setEnSoumission(true)
    setErreurForm(null)
    try {
      const data = await saisirManuel(sessionManuelId, nom.trim(), prenom.trim(), date_naissance.trim())
      setIdentite({
        session_id: data.session_id,
        nom:        data.nom,
        prenom:     data.prenom,
        age:        data.age,
        sexe:       data.sexe ?? -1,
        numero_cin: '',
      })
      setPrenomBienvenue(data.prenom)
      setVue(VUE.BIENVENUE)
    } catch (err) {
      setErreurForm(`Erreur : ${err.message}`)
    } finally {
      setEnSoumission(false)
    }
  }

  // ── Scan réussi confirmé ──────────────────────────────────────────────────
  const confirmer = () => {
    activer()
    setIdentite({
      session_id:  donneesScan.session_id,
      nom:         donneesScan.nom,
      prenom:      donneesScan.prenom,
      age:         donneesScan.age,
      sexe:        donneesScan.sexe,
      numero_cin:  donneesScan.numero_cin,
    })
    setPrenomBienvenue(donneesScan.prenom)
    setVue(VUE.BIENVENUE)
  }

  const recommencer = () => {
    setDonneesScan(null)
    setVue(VUE.ACCUEIL)
  }

  return (
    <div className="kiosk-shell" dir={langue === 'ar' ? 'rtl' : 'ltr'}>
      <IndicateurEtape etapeCourante={1} />
      <SelecteurLangue />
      <BoutonPleinEcran />
      <ModalInactivite avertissement={avertissement} compte={compte} onContinuer={reset} />

      <div className={`ws-badge ${wsConnecte ? 'ws-badge--ok' : 'ws-badge--off'}`}>
        {wsConnecte ? '● Connecté' : '○ Hors ligne'}
      </div>

      {/* ── Accueil ─────────────────────────────────────────────── */}
      {vue === VUE.ACCUEIL && (
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
      {vue === VUE.ACCUEIL && (
        <div className="kiosk-center">
          <div className="kiosk-card">
            <span className="eyebrow">{t('titre_app')}</span>
            <h1 className="kiosk-titre">{t('bienvenue_principale')}</h1>
            <p className="kiosk-soustitre">{t('sous_titre')}</p>
            <GuideEtape etape={1} />

            <div className="illustration-wrapper">
              <IllustrationScanCIN />
            </div>

            {erreur && (
              <div className="kiosk-alerte" role="alert">{erreur}</div>
            )}

            <button className="kiosk-btn kiosk-btn--primary" onClick={lancerScan}>
              <svg className="kiosk-btn-icone" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="2" y="5" width="20" height="14" rx="2" />
                <path d="M2 10h20" />
              </svg>
              {t('scanner_btn')}
            </button>

            <button
              className="kiosk-btn kiosk-btn--secondary"
              onClick={() => { setFormulaire({ nom: '', prenom: '', date_naissance: '' }); setSessionManuelId(null); setVue(VUE.FORMULAIRE) }}
            >
              {t('saisie_manuelle')}
            </button>

            {/* Bouton guidage vocal — bien visible sur l'accueil */}
            <button
              className="kiosk-btn kiosk-btn--secondary"
              onClick={toggleAudio}
              style={{
                marginTop: 8,
                fontSize: '0.95em',
                background: audioActif ? 'rgba(20,184,166,0.18)' : 'rgba(15,23,42,0.5)',
                border: audioActif ? '1px solid rgba(20,184,166,0.5)' : '1px solid rgba(148,163,184,0.2)',
                color: audioActif ? '#2dd4bf' : 'rgba(148,163,184,0.7)',
              }}
              aria-pressed={audioActif}
            >
              {audioActif
                ? <><span className="audio-active-dot" aria-hidden="true" /> 🔊 {t('tts_audio_desactiver')}</>
                : `🔇 ${t('tts_audio_activer')}`
              }
            </button>
          </div>
        </div>
      )}

      {/* ── Scan en cours ───────────────────────────────────────── */}
      {vue === VUE.SCAN && (
        <div className="kiosk-center">
          <div className="kiosk-card kiosk-card--centree">
            <div className="camera-active-badge" role="status" aria-live="polite">
              <span className="camera-active-dot" aria-hidden="true" />
              {t('camera_active')}
            </div>
            <div className="kiosk-spinner" aria-label="Chargement" />
            <h2 className="kiosk-titre-sm">{t('scan_en_cours')}</h2>
            <p className="kiosk-soustitre">{t('scan_instruction')}</p>
          </div>
        </div>
      )}

      {/* ── Formulaire manuel ───────────────────────────────────── */}
      {vue === VUE.FORMULAIRE && (
        <div className="kiosk-center">
          <div className="kiosk-card">
            <span className="eyebrow">{t('saisie_manuelle')}</span>
            <h2 className="kiosk-titre-sm">{t('bienvenue')}</h2>

            {erreurForm && (
              <div className="kiosk-alerte" role="alert">{erreurForm}</div>
            )}

            <div className="cin-form">
              <div className="cin-field">
                <label className="cin-label" htmlFor="cin-nom">{t('nom')}</label>
                <input
                  id="cin-nom"
                  className="cin-input"
                  name="nom"
                  type="text"
                  placeholder={t('nom')}
                  value={formulaire.nom}
                  onChange={changerChamp}
                  autoComplete="family-name"
                />
              </div>

              <div className="cin-field">
                <label className="cin-label" htmlFor="cin-prenom">{t('prenom')}</label>
                <input
                  id="cin-prenom"
                  className="cin-input"
                  name="prenom"
                  type="text"
                  placeholder={t('prenom')}
                  value={formulaire.prenom}
                  onChange={changerChamp}
                  autoComplete="given-name"
                />
              </div>

              <div className="cin-field">
                <label className="cin-label" htmlFor="cin-ddn">{t('date_naissance')}</label>
                <input
                  id="cin-ddn"
                  className="cin-input"
                  name="date_naissance"
                  type="text"
                  placeholder="JJ/MM/AAAA"
                  value={formulaire.date_naissance}
                  onChange={changerDate}
                  inputMode="numeric"
                  maxLength={10}
                />
                <span className="cin-hint">{t('format_date_hint')}</span>
              </div>
            </div>

            <div className="kiosk-actions">
              <button
                className="kiosk-btn kiosk-btn--primary"
                onClick={validerManuel}
                disabled={enSoumission}
              >
                {enSoumission ? '…' : t('valider')}
              </button>
              <button className="kiosk-btn kiosk-btn--secondary" onClick={() => setVue(VUE.ACCUEIL)}>
                {t('retour_scan')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Confirmation après scan réussi ──────────────────────── */}
      {vue === VUE.CONFIRMATION && (
        <ConfirmationPatient
          donnees={donneesScan}
          onConfirmer={confirmer}
          onRecommencer={recommencer}
        />
      )}

      {/* ── Message de bienvenue (2 s avant navigation) ─────────── */}
      {vue === VUE.BIENVENUE && (
        <div className="kiosk-center">
          <div className="kiosk-card kiosk-card--centree" style={{ textAlign: 'center' }}>
            <span style={{ fontSize: '3rem' }}>👋</span>
            <h2 className="kiosk-titre-sm" style={{ marginTop: 12 }}>
              {t('bonjour')} {prenomBienvenue} !
            </h2>
            <p className="kiosk-soustitre">{t('evaluation')}</p>
            <div className="kiosk-spinner" style={{ marginTop: 16 }} aria-label="Chargement" />
          </div>
        </div>
      )}

    </div>
  )
}
