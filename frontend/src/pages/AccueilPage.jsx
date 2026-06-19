import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePatient } from '../context/PatientContext'
import { scannerCIN, saisirManuel, demarrerDemo } from '../services/api'
import IndicateurEtape from '../components/IndicateurEtape'
import ConfirmationPatient from '../components/ConfirmationPatient'
import { IllustrationScanCIN } from '../components/IllustrationsGestes'
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
  const { setIdentite, connecterBorne, reinitialiser } = usePatient()

  const [vue, setVue]                   = useState(VUE.ACCUEIL)
  const [donneesScan, setDonneesScan]   = useState(null)
  const [erreur, setErreur]             = useState(null)
  const [wsConnecte, setWsConnecte]     = useState(false)
  const [prenomBienvenue, setPrenomBienvenue] = useState('')

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
      setErreurForm('Le nom et le prénom sont obligatoires.')
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
      setErreur('Impossible de démarrer le mode démo')
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
    <div className="kiosk-shell">
      <IndicateurEtape etapeCourante={1} />

      <div className={`ws-badge ${wsConnecte ? 'ws-badge--ok' : 'ws-badge--off'}`}>
        {wsConnecte ? '● Connecté' : '○ Hors ligne'}
      </div>

      {/* ── Accueil ─────────────────────────────────────────────── */}
      {vue === VUE.ACCUEIL && (
        <div className="kiosk-center">
          <div className="kiosk-card">
            <span className="eyebrow">HealthGate · Urgences</span>
            <h1 className="kiosk-titre">Bienvenue</h1>
            <p className="kiosk-soustitre">
              Pour commencer votre prise en charge, veuillez scanner votre carte
              d'identité nationale.
            </p>

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
              Scanner ma carte d'identité
            </button>

            <button
              className="kiosk-btn kiosk-btn--secondary"
              onClick={() => { setFormulaire({ nom: '', prenom: '', date_naissance: '' }); setSessionManuelId(null); setVue(VUE.FORMULAIRE) }}
            >
              Saisie manuelle
            </button>

            <button
              className="kiosk-btn kiosk-btn--secondary"
              onClick={lancerDemo}
              style={{ marginTop: 8, opacity: 0.6, fontSize: '0.85em' }}
            >
              Mode Démo
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
              Caméra active
            </div>
            <div className="kiosk-spinner" aria-label="Chargement" />
            <h2 className="kiosk-titre-sm">Scan en cours…</h2>
            <p className="kiosk-soustitre">
              Veuillez maintenir votre carte face au lecteur.
            </p>
          </div>
        </div>
      )}

      {/* ── Formulaire manuel ───────────────────────────────────── */}
      {vue === VUE.FORMULAIRE && (
        <div className="kiosk-center">
          <div className="kiosk-card">
            <span className="eyebrow">Saisie manuelle</span>
            <h2 className="kiosk-titre-sm">Entrez vos informations</h2>
            <p className="kiosk-soustitre">
              Le scanner n'a pas pu lire votre carte. Veuillez renseigner vos informations manuellement.
            </p>

            {erreurForm && (
              <div className="kiosk-alerte" role="alert">{erreurForm}</div>
            )}

            <div className="cin-form">
              <div className="cin-field">
                <label className="cin-label" htmlFor="cin-nom">Nom</label>
                <input
                  id="cin-nom"
                  className="cin-input"
                  name="nom"
                  type="text"
                  placeholder="Votre nom de famille"
                  value={formulaire.nom}
                  onChange={changerChamp}
                  autoComplete="family-name"
                />
              </div>

              <div className="cin-field">
                <label className="cin-label" htmlFor="cin-prenom">Prénom</label>
                <input
                  id="cin-prenom"
                  className="cin-input"
                  name="prenom"
                  type="text"
                  placeholder="Votre prénom"
                  value={formulaire.prenom}
                  onChange={changerChamp}
                  autoComplete="given-name"
                />
              </div>

              <div className="cin-field">
                <label className="cin-label" htmlFor="cin-ddn">Date de naissance</label>
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
                <span className="cin-hint">Format : 15/03/1985</span>
              </div>
            </div>

            <div className="kiosk-actions">
              <button
                className="kiosk-btn kiosk-btn--primary"
                onClick={validerManuel}
                disabled={enSoumission}
              >
                {enSoumission ? 'Validation…' : 'Valider et continuer →'}
              </button>
              <button className="kiosk-btn kiosk-btn--secondary" onClick={() => setVue(VUE.ACCUEIL)}>
                ↩ Retour — Réessayer le scan
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
              Bonjour {prenomBienvenue} !
            </h2>
            <p className="kiosk-soustitre">
              Nous allons maintenant évaluer votre état de santé.
            </p>
            <div className="kiosk-spinner" style={{ marginTop: 16 }} aria-label="Chargement" />
          </div>
        </div>
      )}
    </div>
  )
}
