import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePatient } from '../context/PatientContext'
import { scannerCIN, saisirManuel, demarrerDemo, abandonnerSession } from '../services/api'
import IndicateurEtape from '../components/IndicateurEtape'
import ConfirmationPatient from '../components/ConfirmationPatient'
import { IllustrationScanCIN } from '../components/IllustrationsGestes'
import SelecteurLangue from '../components/SelecteurLangue'
import GuideEtape from '../components/GuideEtape'
import ModalInactivite from '../components/ModalInactivite'
import BoutonPleinEcran from '../components/BoutonPleinEcran'
import { useTranslation } from '../hooks/useTranslation'
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
  const { setIdentite, connecterBorne, reinitialiser, patient } = usePatient()
  const { t, langue } = useTranslation()

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

  // Session créée côté backend même si OCR incomplet
  const [sessionManuelId, setSessionManuelId] = useState(null)

  // Champs du formulaire manuel (pré-remplis si OCR partiel)
  const [formulaire, setFormulaire] = useState({ nom: '', prenom: '', date_naissance: '' })
  const [erreurForm, setErreurForm] = useState(null)
  const [enSoumission, setEnSoumission] = useState(false)

  // Auto-navigation après message de bienvenue (2 s)
  useEffect(() => {
    if (vue !== VUE.BIENVENUE) return
    const t = setTimeout(() => navigate('/questionnaire'), 2000)
    return () => clearTimeout(t)
  }, [vue, navigate])

  useEffect(() => {
    reinitialiser()

    const ws = connecterBorne((msg) => {
      if (msg.event === 'constantes_update') {
        console.log('[WS borne] Constantes reçues :', msg.data)
      }
    })

    ws.onopen = () => setWsConnecte(true)
    // Chaîner avec le handler de reconnexion de PatientContext
    const _prevOnClose = ws.onclose
    ws.onclose = (e) => {
      setWsConnecte(false)
      _prevOnClose?.(e)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Scan CIN ─────────────────────────────────────────────────────────────
  const lancerScan = async () => {
    enterFullscreen()
    setVue(VUE.SCAN)
    setErreur(null)
    setErreurForm(null)
    try {
      const data = await scannerCIN()
      if (data.formulaire_manuel) {
        // OCR incomplet → formulaire avec pré-remplissage partiel
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
      // Échec réseau ou autre → formulaire vide
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

  const validerManuel = async () => {
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

  // ── Mode démo ─────────────────────────────────────────────────────────────
  const lancerDemo = async () => {
    enterFullscreen()
    setErreur(null)
    try {
      const data = await demarrerDemo()
      setIdentite({
        session_id: data.session_id,
        nom:        data.nom,
        prenom:     data.prenom,
        age:        data.age,
        sexe:       data.sexe ?? 0,
        numero_cin: '',
      })
      setPrenomBienvenue(data.prenom)
      setVue(VUE.BIENVENUE)
    } catch {
      setErreur(t('erreur_mode_demo'))
    }
  }

  // ── Scan réussi confirmé ──────────────────────────────────────────────────
  const confirmer = () => {
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
        <div className="kiosk-center">
          <div className="kiosk-card">
            <span className="eyebrow">{t('titre_app')}</span>
            <h1 className="kiosk-titre">{t('bienvenue')}</h1>
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

            <button
              className="kiosk-btn kiosk-btn--secondary"
              onClick={lancerDemo}
              style={{ marginTop: 8, opacity: 0.6, fontSize: '0.85em' }}
            >
              {t('mode_demo')}
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
                  onChange={changerChamp}
                  inputMode="numeric"
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
