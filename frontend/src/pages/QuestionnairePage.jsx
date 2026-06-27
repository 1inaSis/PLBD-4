// Étape 2 / 5 — Questionnaire symptômes
// Patient sélectionne les zones douloureuses sur le pictogramme
// et décrit librement ses symptômes. POST /api/symptomes envoie
// le texte + les zones ; le NLP extrait les features côté serveur.

import { useState, useCallback, useEffect } from 'react'
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
import '../styles/kiosk.css'

export default function QuestionnairePage() {
  const navigate = useNavigate()
  const { patient, setSymptomes, reinitialiser, audioActif } = usePatient()
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
    const timer = setTimeout(() => parler(t('tts_questionnaire'), langue), 300)
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
    if (!peutContinuer || enChargement) return
    setEnChargement(true)
    setErreur(null)

    // Si texte vide, on génère automatiquement depuis les zones sélectionnées
    const texteEnvoye = texteSymptome.trim() ||
      zonesSelectionnees.map(id => ZONES_MAP[id]).join(', ')

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

      <div className="questionnaire-layout">

        {/* ── Colonne gauche : Pictogramme ───────────────────────────── */}
        <section className="questionnaire-col questionnaire-col--corps" aria-label="Sélection des zones douloureuses">
          <CorpsHumain
            zonesSelectionnees={zonesSelectionnees}
            onToggleZone={toggleZone}
          />
        </section>

        {/* ── Colonne droite : Saisie symptômes ──────────────────────── */}
        <section className="questionnaire-col questionnaire-col--saisie" aria-label="Description des symptômes">
          <div className="kiosk-card">
            <span className="eyebrow">{t('etape2_titre')}</span>
            <h2 className="kiosk-titre-sm">
              {patient.prenom ? `${t('ou_mal').replace('?', ',').replace('؟', '،')} ${patient.prenom} ?` : t('ou_mal')}
            </h2>

            {/* Chips des zones sélectionnées */}
            {zonesSelectionnees.length > 0 ? (
              <div className="zones-choisies">
                <p className="zones-choisies-titre">{t('zones_select')}</p>
                <div className="zones-tags">
                  {zonesSelectionnees.map(id => (
                    <button
                      key={id}
                      className="zone-tag"
                      onClick={() => retirer(id)}
                      aria-label={`Retirer ${ZONES_MAP[id]}`}
                    >
                      {ZONES_MAP[id]}
                      <span className="zone-tag-suppr" aria-hidden="true"> ×</span>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <p className="kiosk-note" style={{ marginTop: 0 }}>
                {t('instruction_corps')}
              </p>
            )}

            {/* Champ de description libre */}
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

            {/* Alerte urgence détectée par le NLP */}
            {urgenceDetectee && (
              <div className="kiosk-alerte kiosk-alerte--urgence" role="alert" aria-live="assertive">
                {t('alerte_urgence_detectee')}
              </div>
            )}

            {erreur && (
              <div className="kiosk-alerte" role="alert">{erreur}</div>
            )}

            <div className="kiosk-actions">
              <button
                className="kiosk-btn kiosk-btn--primary"
                onClick={continuer}
                disabled={!peutContinuer || enChargement}
              >
                {enChargement ? '…' : t('continuer')}
              </button>
              <button
                className="kiosk-btn kiosk-btn--secondary"
                onClick={() => navigate('/')}
                disabled={enChargement}
              >
                {t('retour')}
              </button>
            </div>
          </div>
        </section>

      </div>
    </div>
  )
}
