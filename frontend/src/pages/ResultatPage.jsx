// Étape 5 / 5 — Résultat du triage ESI
// Affiche : niveau ESI coloré, ticket patient, position en file, temps d'attente.

import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePatient } from '../context/PatientContext'
import IndicateurEtape from '../components/IndicateurEtape'
import SelecteurLangue from '../components/SelecteurLangue'
import GuideEtape from '../components/GuideEtape'
import ModalInactivite from '../components/ModalInactivite'
import { useTranslation } from '../hooks/useTranslation'
import { useInactivite } from '../hooks/useInactivite'
import '../styles/kiosk.css'

// ── Configuration des niveaux ESI ────────────────────────────────────────────
const ESI_CONFIG = {
  1: { couleur: 'rouge',  libelle: 'Immédiat',    delai: 'Prise en charge immédiate' },
  2: { couleur: 'orange', libelle: 'Très urgent',  delai: 'Sous 10 minutes' },
  3: { couleur: 'jaune',  libelle: 'Urgent',       delai: 'Sous 30 minutes' },
  4: { couleur: 'vert',   libelle: 'Peu urgent',   delai: 'Sous 1 heure' },
  5: { couleur: 'bleu',   libelle: 'Non urgent',   delai: 'Selon disponibilités' },
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
  const { patient, reinitialiser } = usePatient()
  const { t, langue } = useTranslation()
  const [sortie, setSortie] = useState(false)

  const { avertissement, compte, reset } = useInactivite({
    onExpiration: () => { reinitialiser(); navigate('/') },
  })

  const navigerVers = useCallback((path, opts) => {
    setSortie(true)
    setTimeout(() => navigate(path, opts), 350)
  }, [navigate])

  const res    = patient.resultat_triage
  const esi    = res?.esi_predit ?? null
  const config = ESI_CONFIG[esi] ?? null
  const style  = config ? COULEURS_ESI[config.couleur] : null

  // Garder le résultat affiché 60 s max, puis permettre nouvelle consultation
  useEffect(() => {
    if (!res) navigate('/', { replace: true })
  }, [res, navigate])

  if (!res) return null

  // ── Raccourcis pour l'affichage ───────────────────────────────────────────
  const numeroTicket  = res.patient_id ?? '—'
  const positionFile  = res.position_file ?? '—'
  const attente       = res.attente_estimee ?? config?.delai ?? '—'
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
            <div
              className="resultat-esi-badge"
              style={{
                background: style.fond,
                border: `2px solid ${style.bordure}`,
                color: style.texte,
              }}
              aria-label={`Niveau de priorité ESI ${esi} : ${config.libelle}`}
            >
              <span className="resultat-esi-numero">{esi}</span>
              <div className="resultat-esi-infos">
                <span className="resultat-esi-libelle">{config.libelle}</span>
                <span className="resultat-esi-sous">Niveau de priorité</span>
              </div>
            </div>
          )}

          {/* Ligne de statut (niveau_urgence du backend) */}
          {res.niveau_urgence && (
            <p className="resultat-statut">{res.niveau_urgence}</p>
          )}

          {/* Explications ESI */}
          {explications.length > 0 && (
            <div className="resultat-explications">
              <p className="resultat-expl-titre">Facteurs ayant influencé votre niveau de priorité :</p>
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
