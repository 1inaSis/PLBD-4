// Barre de progression du parcours patient (5 étapes).
// Utilisée en haut de chaque page de la borne.

import { useTranslation } from '../hooks/useTranslation'

const ETAPES = [
  { num: 1, labelKey: 'etape_identite' },
  { num: 2, labelKey: 'etape_symptomes' },
  { num: 3, labelKey: 'etape_constantes' },
  { num: 4, labelKey: 'etape_questions' },
  { num: 5, labelKey: 'etape_resultat' },
]

export default function IndicateurEtape({ etapeCourante }) {
  const { t } = useTranslation()
  return (
    <nav className="indicateur-etape" aria-label="Progression du triage">
      {ETAPES.map((etape, index) => {
        const etat =
          etape.num < etapeCourante  ? 'terminee' :
          etape.num === etapeCourante ? 'active' :
                                        'a-venir'
        return (
          <div key={etape.num} className={`etape etape--${etat}`}>
            <div className="etape-bulle" aria-hidden="true">
              {etat === 'terminee' ? '✓' : etape.num}
            </div>
            <span className="etape-label">{t(etape.labelKey)}</span>
            {index < ETAPES.length - 1 && (
              <div className={`etape-trait etape-trait--${etat === 'terminee' ? 'actif' : 'inactif'}`} />
            )}
          </div>
        )
      })}
    </nav>
  )
}
