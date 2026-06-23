// Étape 5 / 5 — Résultat du triage ESI
// Affiche : niveau ESI coloré, ticket patient, position en file, temps d'attente.

import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePatient } from '../context/PatientContext'
import IndicateurEtape from '../components/IndicateurEtape'
import SelecteurLangue from '../components/SelecteurLangue'
import GuideEtape from '../components/GuideEtape'
import ModalInactivite from '../components/ModalInactivite'
import BoutonAudio from '../components/BoutonAudio'
import { useTranslation } from '../hooks/useTranslation'
import { useTextToSpeech } from '../hooks/useTextToSpeech'
import { useInactivite } from '../hooks/useInactivite'
import '../styles/kiosk.css'

// ── Couleurs ESI (statique) ───────────────────────────────────────────────────
const ESI_CONFIG = {
  1: { couleur: 'rouge'  },
  2: { couleur: 'orange' },
  3: { couleur: 'jaune'  },
  4: { couleur: 'vert'   },
  5: { couleur: 'bleu'   },
}

const COULEURS_ESI = {
  rouge:  { fond: 'rgba(239,68,68,0.14)',   bordure: 'rgba(239,68,68,0.45)',   texte: '#f87171' },
  orange: { fond: 'rgba(249,115,22,0.14)',  bordure: 'rgba(249,115,22,0.42)',  texte: '#fb923c' },
  jaune:  { fond: 'rgba(251,191,36,0.14)',  bordure: 'rgba(251,191,36,0.40)',  texte: '#fbbf24' },
  vert:   { fond: 'rgba(52,211,153,0.12)',  bordure: 'rgba(52,211,153,0.38)',  texte: '#34d399' },
  bleu:   { fond: 'rgba(56,189,248,0.12)',  bordure: 'rgba(56,189,248,0.35)',  texte: '#38bdf8' },
}

export default function ResultatPage() {
  const navigate  = useNavigate()
  const { patient, reinitialiser, audioActif } = usePatient()
  const { t, langue } = useTranslation()
  const { parler, estEnTrainDeParler, supporte } = useTextToSpeech()
  const [sortie, setSortie] = useState(false)

  const { avertissement, compte, reset } = useInactivite({
    onExpiration: () => { reinitialiser(); navigate('/') },
  })

  const navigerVers = useCallback((path, opts) => {
    setSortie(true)
    setTimeout(() => navigate(path, opts), 350)
  }, [navigate])

  const res        = patient.resultat_triage
  const esi        = res?.esi_predit ?? null
  const config     = ESI_CONFIG[esi] ?? null
  const style      = config ? COULEURS_ESI[config.couleur] : null
  const esiLibelle  = esi ? t(`esi${esi}_libelle`) : null
  const esiDelai    = esi ? t(`esi${esi}_delai`)   : null
  const texteResultat = esiLibelle && esiDelai
    ? t('tts_resultat', { libelle: esiLibelle, delai: esiDelai })
    : null

  useEffect(() => {
    if (!res) navigate('/', { replace: true })
  }, [res, navigate])

  // Lecture automatique du résultat à l'arrivée sur la page (si audio activé)
  useEffect(() => {
    if (!texteResultat) return
    const timer = setTimeout(() => parler(texteResultat, langue), 300)
    return () => clearTimeout(timer)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Re-lecture quand l'audio est (ré)activé
  useEffect(() => {
    if (!audioActif || !texteResultat) return
    parler(texteResultat, langue)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audioActif])

  if (!res) return null

  // ── Raccourcis pour l'affichage ───────────────────────────────────────────
  const numeroTicket  = res.patient_id ?? '—'
  const positionFile  = res.position_file ?? '—'
  const attente       = res.attente_estimee ?? esiDelai ?? '—'
  const medecin       = res.medecin_assigne ?? null
  const confiance     = res.confiance != null ? Math.round(res.confiance) : null
  const explications  = res.explications ?? []

  const nouvelleConsultation = () => {
    reinitialiser()
    navigerVers('/', { replace: true })
  }

  return (
    <div className={`kiosk-shell${sortie ? ' page-exit' : ''}`} dir={langue === 'ar' ? 'rtl' : 'ltr'}>
      <IndicateurEtape etapeCourante={5} />
      <SelecteurLangue />
      <BoutonAudio />
      <ModalInactivite avertissement={avertissement} compte={compte} onContinuer={reset} />
      <GuideEtape etape={5} />

      <div className="kiosk-center">
        <div className="resultat-carte kiosk-card">

          {/* Ticket numéroté */}
          <div className="resultat-ticket-wrapper">
            <span className="eyebrow">{t('votre_ticket')}</span>
            <span className="resultat-ticket">{numeroTicket}</span>
          </div>

          {/* Badge ESI principal */}
          {esi && style && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div
                className="resultat-esi-badge"
                style={{
                  background: style.fond,
                  border: `2px solid ${style.bordure}`,
                  color: style.texte,
                  flex: 1,
                }}
                aria-label={`${t('niveau_priorite')} ESI ${esi} : ${esiLibelle}`}
              >
                <span className="resultat-esi-numero">{esi}</span>
                <div className="resultat-esi-infos">
                  <span className="resultat-esi-libelle">{esiLibelle}</span>
                  <span className="resultat-esi-sous">{t('niveau_priorite')}</span>
                </div>
              </div>
              {supporte && texteResultat && (
                <button
                  className={`tts-btn${estEnTrainDeParler ? ' tts-btn--actif' : ''}`}
                  onClick={() => parler(texteResultat, langue)}
                  aria-label={t('tts_ecouter')}
                  title={t('tts_ecouter')}
                  style={{ fontSize: '1.4rem', padding: '6px 10px' }}
                >🔊</button>
              )}
            </div>
          )}

          {/* Ligne de statut (niveau_urgence du backend) */}
          {res.niveau_urgence && (
            <p className="resultat-statut">{res.niveau_urgence}</p>
          )}

          {/* Explications ESI */}
          {explications.length > 0 && (
            <div className="resultat-explications">
              <p className="resultat-expl-titre">{t('facteurs_influence')}</p>
              <ul className="resultat-expl-liste">
                {explications.map((e, i) => (
                  <li key={i} className="resultat-expl-item">
                    <span className="resultat-expl-check">✓</span> {e}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Méta-informations : file / attente / médecin */}
          <div className="resultat-meta">
            <div className="resultat-meta-item">
              <span className="resultat-meta-label">{t('position_file')}</span>
              <span className="resultat-meta-valeur">{positionFile}</span>
            </div>
            <div className="resultat-meta-item">
              <span className="resultat-meta-label">{t('temps_attente')}</span>
              <span className="resultat-meta-valeur">{attente}</span>
            </div>
            {medecin && (
              <div className="resultat-meta-item">
                <span className="resultat-meta-label">{t('medecin_assigne')}</span>
                <span className="resultat-meta-valeur">{medecin}</span>
              </div>
            )}
            {confiance != null && (
              <div className="resultat-meta-item">
                <span className="resultat-meta-label">{t('fiabilite_ia')}</span>
                <span className="resultat-meta-valeur">{confiance} %</span>
              </div>
            )}
          </div>

          {/* Message de guidage */}
          <div className="resultat-instruction">{t('instruction_att')}</div>

          {/* Bouton nouvelle consultation */}
          <div className="kiosk-actions">
            <button
              className="kiosk-btn kiosk-btn--secondary"
              onClick={nouvelleConsultation}
            >
              {t('nvlle_consult')}
            </button>
          </div>

        </div>
      </div>
    </div>
  )
}
