// Étape 2 / 5 — Questionnaire symptômes
// Patient sélectionne les zones douloureuses sur le pictogramme
// et décrit librement ses symptômes. POST /api/symptomes envoie
// le texte + les zones ; le NLP extrait les features côté serveur.

import { useState, useCallback, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePatient } from '../context/PatientContext'
import { soumettreSymptomes, abandonnerSession } from '../services/api'
import IndicateurEtape from '../components/IndicateurEtape'
import CorpsHumain, { ZONES_MAP } from '../components/CorpsHumain'
import SelecteurLangue from '../components/SelecteurLangue'
import GuideEtape from '../components/GuideEtape'
import ModalInactivite from '../components/ModalInactivite'
import { useTranslation } from '../hooks/useTranslation'
import { useTextToSpeech } from '../hooks/useTextToSpeech'
import { useInactivite } from '../hooks/useInactivite'
import BoutonAudio from '../components/BoutonAudio'
import ZoneSaisieMixte from '../components/ZoneSaisieMixte'
import { useVoiceInput } from '../hooks/useVoiceInput'
import '../styles/kiosk.css'

const SR_API_QR = typeof window !== 'undefined'
  ? (window.SpeechRecognition || window.webkitSpeechRecognition)
  : null

function parlerQR(texte, langue) {
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
  function next() {
    if (i >= morceaux.length) return
    const utt = new SpeechSynthesisUtterance(morceaux[i++])
    utt.lang = lang; utt.rate = 0.9; utt.volume = 1.0
    utt.onend = next; utt.onerror = () => setTimeout(next, 100)
    window.speechSynthesis.speak(utt)
  }
  setTimeout(next, 50)
  return durée
}

export default function QuestionnairePage() {
  const navigate = useNavigate()
  const { patient, setSymptomes, reinitialiser, audioActif, modeIllettré } = usePatient()
  const { t, langue } = useTranslation()
  const { parler, arreter } = useTextToSpeech()
  const handleExpiration = useCallback(async () => {
    if (patient.session_id) await abandonnerSession(patient.session_id)
    reinitialiser(); navigate('/')
  }, [patient.session_id, reinitialiser, navigate])
  const { avertissement, compte, reset } = useInactivite({ onExpiration: handleExpiration })

  useEffect(() => {
    if (!patient.session_id) navigate('/', { replace: true })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Lecture automatique de l'instruction principale — 300ms après montage
  useEffect(() => {
    const cle = modeIllettré ? 'ill_symptomes_zones' : 'tts_questionnaire'
    const timer = setTimeout(() => parler(t(cle), langue), 300)
    return () => { clearTimeout(timer); arreter() }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Re-lecture de l'instruction quand l'audio est (ré)activé sur cette page
  useEffect(() => {
    if (!audioActif) return
    parler(t('tts_questionnaire'), langue)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audioActif])

  const [zonesSelectionnees, setZonesSelectionnees] = useState([])

  // Mode illettré : répète "Touchez là où vous avez mal" toutes les 10s si aucune zone
  useEffect(() => {
    if (!modeIllettré) return
    const id = setInterval(() => {
      if (zonesSelectionnees.length === 0) parlerQR(t('ill_symptomes_zones'), langue)
    }, 10000)
    return () => clearInterval(id)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modeIllettré, zonesSelectionnees.length])
  const [texteSymptome, setTexteSymptome] = useState('')
  const [enChargement, setEnChargement]   = useState(false)
  const [erreur, setErreur]               = useState(null)
  const [urgenceDetectee, setUrgenceDetectee] = useState(false)
  const [sortie, setSortie]               = useState(false)

  const navigerVers = useCallback((path, opts) => {
    setSortie(true)
    setTimeout(() => navigate(path, opts), 350)
  }, [navigate])

  // Le bouton Continuer est actif si au moins une zone OU 3+ caractères de texte
  const peutContinuer = zonesSelectionnees.length > 0 || texteSymptome.trim().length >= 3

  // Ajouter / retirer une zone de la sélection
  const toggleZone = (id) => {
    setZonesSelectionnees(prev =>
      prev.includes(id) ? prev.filter(z => z !== id) : [...prev, id]
    )
  }

  const retirer = (id) => setZonesSelectionnees(prev => prev.filter(z => z !== id))

  const continuer = async () => {
    if (enChargement) return
    // En mode illettré, on continue même sans texte minimum
    if (!modeIllettré && !peutContinuer) return
    setEnChargement(true)
    setErreur(null)

    // Si texte vide, on génère automatiquement depuis les zones sélectionnées
    const texteEnvoye = texteSymptome.trim() ||
      zonesSelectionnees.map(id => ZONES_MAP[id]).join(', ') ||
      (modeIllettré ? 'Symptômes non décrits verbalement' : '')

    try {
      const res = await soumettreSymptomes(
        patient.session_id,
        texteEnvoye,
        zonesSelectionnees,
      )

      // Sauvegarder dans le contexte global
      setSymptomes(texteEnvoye, zonesSelectionnees)

      if (res.urgence_detectee) {
        setUrgenceDetectee(true)
        setTimeout(() => navigerVers('/constantes'), 2500)
      } else {
        navigerVers('/constantes')
      }
    } catch (err) {
      setErreur(`Erreur : ${err.message}`)
    } finally {
      setEnChargement(false)
    }
  }

  return (
    <div className={`kiosk-shell${sortie ? ' page-exit' : ''}`} dir={langue === 'ar' ? 'rtl' : 'ltr'}>
      <IndicateurEtape etapeCourante={2} />
      <SelecteurLangue />
      <BoutonAudio />
      <ModalInactivite avertissement={avertissement} compte={compte} onContinuer={reset} />
      <GuideEtape etape={2} />

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

      {/* ── Mode illettré : corps seul + voix après zone touchée ── */}
      {modeIllettré ? (
        <div className="kiosk-center" style={{ flexDirection: 'column', gap: 16, padding: 12 }}>
          <CorpsHumain zonesSelectionnees={zonesSelectionnees} onToggleZone={toggleZone} />

          {zonesSelectionnees.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
              {zonesSelectionnees.map(id => (
                <span key={id} style={{
                  background: 'rgba(0,212,255,0.12)', border: '1px solid rgba(0,212,255,0.3)',
                  color: '#00d4ff', borderRadius: 20, padding: '4px 12px', fontSize: '0.88rem',
                }}>
                  {ZONES_MAP[id]}
                </span>
              ))}
            </div>
          )}

          {zonesSelectionnees.length > 0 && (
            <ModeIlletréSymptomes
              langue={langue}
              onTexte={(texte) => setTexteSymptome(texte)}
              onFin={() => continuer()}
            />
          )}

          {urgenceDetectee && (
            <div className="kiosk-alerte kiosk-alerte--urgence" role="alert">{t('alerte_urgence_detectee')}</div>
          )}
          {erreur && <div className="kiosk-alerte" role="alert">{erreur}</div>}

          {/* Bouton continuer géant — mode illettré */}
          <button
            onClick={continuer}
            disabled={zonesSelectionnees.length === 0 || enChargement}
            style={{
              width: 160, height: 100, borderRadius: 20, border: 'none',
              background: zonesSelectionnees.length === 0 ? 'rgba(255,255,255,0.07)' : 'rgba(16,185,129,0.25)',
              color: zonesSelectionnees.length === 0 ? 'rgba(255,255,255,0.25)' : '#10b981',
              fontSize: '3rem', fontWeight: 900, cursor: zonesSelectionnees.length === 0 ? 'default' : 'pointer',
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4,
              marginTop: 8, WebkitTapHighlightColor: 'transparent',
            }}
          >
            {enChargement ? <div className="kiosk-spinner" style={{ width: 32, height: 32 }} /> : <>✓<span style={{ fontSize: '0.85rem', fontWeight: 700 }}>OK</span></>}
          </button>
        </div>
      ) : (
        <div className="questionnaire-layout">

          {/* ── Colonne gauche : Pictogramme ──────────────────────────── */}
          <section className="questionnaire-col questionnaire-col--corps" aria-label="Sélection des zones douloureuses">
            <CorpsHumain zonesSelectionnees={zonesSelectionnees} onToggleZone={toggleZone} />
          </section>

          {/* ── Colonne droite : Saisie symptômes ─────────────────────── */}
          <section className="questionnaire-col questionnaire-col--saisie" aria-label="Description des symptômes">
            <div className="kiosk-card">
              <span className="eyebrow">{t('etape2_titre')}</span>
              <h2 className="kiosk-titre-sm">
                {patient.prenom ? `${t('ou_mal').replace('?', ',').replace('؟', '،')} ${patient.prenom} ?` : t('ou_mal')}
              </h2>

              {zonesSelectionnees.length > 0 ? (
                <div className="zones-choisies">
                  <p className="zones-choisies-titre">{t('zones_select')}</p>
                  <div className="zones-tags">
                    {zonesSelectionnees.map(id => (
                      <button key={id} className="zone-tag" onClick={() => retirer(id)} aria-label={`Retirer ${ZONES_MAP[id]}`}>
                        {ZONES_MAP[id]}<span className="zone-tag-suppr" aria-hidden="true"> ×</span>
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="kiosk-note" style={{ marginTop: 0 }}>{t('instruction_corps')}</p>
              )}

              <div className="symptome-groupe">
                <label className="symptome-label">
                  {t('symptomes_label')} <span className="symptome-optionnel">{t('symptomes_opt')}</span>
                </label>
                <ZoneSaisieMixte
                  value={texteSymptome}
                  onChange={setTexteSymptome}
                  langue={langue}
                  placeholder={t('saisie_placeholder')}
                />
                <span className="symptome-compteur">{texteSymptome.length} / 500</span>
              </div>

              {urgenceDetectee && (
                <div className="kiosk-alerte kiosk-alerte--urgence" role="alert" aria-live="assertive">
                  {t('alerte_urgence_detectee')}
                </div>
              )}
              {erreur && <div className="kiosk-alerte" role="alert">{erreur}</div>}

              <div className="kiosk-actions">
                <button className="kiosk-btn kiosk-btn--primary" onClick={continuer} disabled={!peutContinuer || enChargement}>
                  {enChargement ? '…' : t('continuer')}
                </button>
                <button className="kiosk-btn kiosk-btn--secondary" onClick={() => navigate('/')} disabled={enChargement}>
                  {t('retour')}
                </button>
              </div>
            </div>
          </section>

        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Saisie vocale symptômes — raw SR (évite cancel TTS) — mode illettré
// ─────────────────────────────────────────────────────────────────────────────
function ModeIlletréSymptomes({ langue, onTexte, onFin }) {
  const { t } = useTranslation()
  const [texte, setTexte] = useState('')
  const [ecoute, setEcoute] = useState(false)
  const recoRef     = useRef(null)
  const ecouteRef   = useRef(false)
  const silenceRef  = useRef(null)
  const timers      = useRef([])
  const accRef      = useRef('')
  const lancerRef   = useRef(null)

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
    if (!SR_API_QR) return
    stopReco(); window.speechSynthesis?.cancel()
    const reco = new SR_API_QR()
    reco.lang = { fr: 'fr-FR', en: 'en-US', ar: 'ar-SA' }[langue] ?? 'fr-FR'
    reco.continuous = false; reco.interimResults = false; reco.maxAlternatives = 1
    recoRef.current = reco; ecouteRef.current = true; setEcoute(true)

    reco.onresult = (e) => {
      const tr = Array.from(e.results).filter(r => r.isFinal).map(r => r[0].transcript).join(' ').trim()
      if (tr) {
        const nouveau = accRef.current ? accRef.current + ' ' + tr : tr
        accRef.current = nouveau; setTexte(nouveau); onTexte(nouveau)
      }
      stopReco()
      // 5s silence → terminer
      silenceRef.current = setTimeout(() => onFin(accRef.current), 5000)
      // relance pour capturer plus
      after(300, () => lancerRef.current?.())
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
    const d = parlerQR(t('ill_symptomes_voix'), langue)
    after(d, () => lancerRef.current?.())
    return () => { clearAll(); stopReco() }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, alignItems: 'center', width: '100%' }}>
      <style>{`@keyframes pulse-qr{0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,.7)}70%{box-shadow:0 0 0 16px rgba(239,68,68,0)}}`}</style>
      {ecoute && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 36, height: 36, borderRadius: '50%', background: '#ef4444', animation: 'pulse-qr 1.3s ease-out infinite' }} />
          <span style={{ color: '#f8fafc', fontSize: '1rem' }}>{t('ill_ecoute')}</span>
        </div>
      )}
      <div style={{
        minHeight: 70, width: '100%', padding: '14px 16px',
        background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.15)',
        borderRadius: 12, fontSize: '1.3rem', color: '#f8fafc', lineHeight: 1.6,
        direction: langue === 'ar' ? 'rtl' : 'ltr',
      }}>
        {texte || <span style={{ color: 'rgba(255,255,255,0.3)', fontStyle: 'italic' }}>{t('saisie_ecoute')}</span>}
      </div>
    </div>
  )
}
