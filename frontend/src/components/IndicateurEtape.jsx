// Barre de progression du parcours patient (5 étapes).
// Utilisée en haut de chaque page de la borne.

const ETAPES = [
  { num: 1, label: 'Identité' },
  { num: 2, label: 'Symptômes' },
  { num: 3, label: 'Constantes' },
  { num: 4, label: 'Questions' },
  { num: 5, label: 'Résultat' },
]

export default function IndicateurEtape({ etapeCourante }) {
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
            <span className="etape-label">{etape.label}</span>
            {index < ETAPES.length - 1 && (
              <div className={`etape-trait etape-trait--${etat === 'terminee' ? 'actif' : 'inactif'}`} />
            )}
          </div>
        )
      })}
    </nav>
  )
}
