// Affiche les informations extraites de la CIN pour validation par le patient.

const LIBELLE_SEXE = { 1: 'Homme', 0: 'Femme', '-1': '—' }

export default function ConfirmationPatient({ donnees, onConfirmer, onRecommencer }) {
  const champs = [
    { label: 'Nom',         valeur: donnees?.nom      || '—' },
    { label: 'Prénom',      valeur: donnees?.prenom   || '—' },
    { label: 'Âge',         valeur: donnees?.age != null ? `${donnees.age} ans` : '—' },
    { label: 'Sexe',        valeur: LIBELLE_SEXE[String(donnees?.sexe)] ?? '—' },
    { label: 'N° CIN',      valeur: donnees?.numero_cin || '—' },
  ]

  return (
    <div className="kiosk-center">
      <div className="kiosk-card">
        <span className="eyebrow">Étape 1 / 5</span>
        <h2 className="kiosk-titre-sm">Vérifiez vos informations</h2>
        <p className="kiosk-soustitre">
          Ces données ont été extraites de votre carte d'identité. Est-ce bien vous ?
        </p>

        <div className="patient-infos">
          {champs.map(({ label, valeur }) => (
            <div key={label} className="patient-info-ligne">
              <span className="patient-info-label">{label}</span>
              <span className="patient-info-valeur">{valeur}</span>
            </div>
          ))}
        </div>

        <div className="kiosk-actions">
          <button className="kiosk-btn kiosk-btn--primary" onClick={onConfirmer}>
            Confirmer et continuer →
          </button>
          <button className="kiosk-btn kiosk-btn--secondary" onClick={onRecommencer}>
            ↩ Ce n'est pas moi — Recommencer
          </button>
        </div>
      </div>
    </div>
  )
}
