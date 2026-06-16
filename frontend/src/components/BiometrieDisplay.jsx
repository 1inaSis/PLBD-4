// Affiche les 4 constantes vitales mesurées avec leur badge couleur.
// Seuils issus de hardware/alertes.py (SpO2/FC) et backend/triage_engine.py (temp/tension).

// ── Seuils médicaux ───────────────────────────────────────────────────────────
function evaluerCouleur(cle, valeur) {
  if (valeur == null || isNaN(Number(valeur))) return 'gris'

  switch (cle) {
    case 'temperature':
      if (valeur < 35.0 || valeur >= 40.0) return 'rouge'
      if (valeur >= 38.5 || valeur < 36.0) return 'orange'
      if (valeur >= 37.5) return 'jaune'
      return 'vert'

    case 'spo2':
      if (valeur < 90) return 'rouge'
      if (valeur < 94) return 'orange'
      if (valeur < 95) return 'jaune'
      return 'vert'

    case 'heart_rate':
      if (valeur < 40 || valeur >= 150) return 'rouge'
      if (valeur < 50) return 'orange'   // bradycardie légère
      if (valeur >= 100) return 'jaune'  // tachycardie légère
      return 'vert'

    case 'bp_systolic':
      if (valeur < 80 || valeur >= 180) return 'rouge'
      if (valeur < 90 || valeur >= 160) return 'orange'
      if (valeur >= 140) return 'jaune'
      return 'vert'

    default:
      return 'gris'
  }
}

const LIBELLES_COULEUR = {
  vert:   'Normal',
  jaune:  'Vigilance',
  orange: 'Alerte',
  rouge:  'Critique',
  gris:   'En attente',
}

// ── Configuration des 4 constantes affichées ──────────────────────────────────
const CONSTANTES_CONFIG = [
  {
    cle:      'temperature',
    label:    'Température',
    unite:    '°C',
    icone:    '🌡️',
    formatter: (v) => v != null ? Number(v).toFixed(1) : '—',
  },
  {
    cle:      'spo2',
    label:    'SpO₂',
    unite:    '%',
    icone:    '🫁',
    formatter: (v) => v != null ? Number(v).toFixed(1) : '—',
  },
  {
    cle:      'heart_rate',
    label:    'Fréq. cardiaque',
    unite:    'bpm',
    icone:    '❤️',
    formatter: (v) => v != null ? Math.round(Number(v)) : '—',
  },
  {
    cle:      'bp_systolic',
    label:    'Tension art.',
    unite:    'mmHg',
    icone:    '💉',
    // La tension s'affiche sys/dias, la couleur est évaluée sur la systolique
    formatter: (v, constantes) =>
      v != null ? `${Math.round(v)}/${Math.round(constantes?.bp_diastolic ?? 0)}` : '—',
  },
]

/**
 * @param {object|null} constantes   - Objet retourné par /api/constantes
 * @param {boolean}     enCours      - true = mesure en cours (spinner sur chaque carte)
 */
export default function BiometrieDisplay({ constantes, enCours }) {
  return (
    <div className="bio-grille">
      {CONSTANTES_CONFIG.map(({ cle, label, unite, icone, formatter }) => {
        const valeur  = constantes?.[cle]
        const couleur = enCours ? 'gris' : evaluerCouleur(cle, valeur)
        const affichee = formatter(valeur, constantes)

        return (
          <div
            key={cle}
            className={`bio-carte bio-carte--${couleur}`}
            aria-label={`${label} : ${affichee} ${unite}`}
          >
            <div className="bio-icone" aria-hidden="true">{icone}</div>
            <div className="bio-label">{label}</div>

            <div className="bio-valeur">
              {enCours && valeur == null
                ? <span className="bio-spinner" aria-label="Mesure en cours" />
                : <>{affichee} <span className="bio-unite">{unite}</span></>
              }
            </div>

            <div className={`bio-badge bio-badge--${couleur}`}>
              <span className="bio-badge-dot" />
              {LIBELLES_COULEUR[couleur]}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// Exports pour usage dans ConstantesPage
export { evaluerCouleur, LIBELLES_COULEUR }
