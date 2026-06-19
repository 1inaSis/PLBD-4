// Interface d'orchestration de démonstration — /demo
// Usage jury / soutenance : lance les 3 scénarios prédéfinis en un clic.

import { useState } from 'react'
import '../styles/demo.css'

const SCENARIOS = [
  {
    id: 1,
    titre: 'Urgence cardiaque',
    icone: '❤️',
    esi_attendu: '1-2',
    couleur: '#ef4444',
    fond: 'rgba(239,68,68,0.08)',
    bordure: 'rgba(239,68,68,0.35)',
    details: [
      '👤 Michel Durand, 45 ans, homme',
      '🩺 Douleur thoracique + irradiation bras gauche',
      '📊 FC 128 bpm · TA 88/58 · SpO₂ 91 %',
      '🌡️ Température 37.2 °C',
    ],
  },
  {
    id: 2,
    titre: 'Fièvre modérée',
    icone: '🌡️',
    esi_attendu: '3',
    couleur: '#fbbf24',
    fond: 'rgba(251,191,36,0.08)',
    bordure: 'rgba(251,191,36,0.35)',
    details: [
      '👤 Sara Benali, 30 ans, femme',
      '🩺 Fièvre 38.8 °C, maux de tête, courbatures',
      '📊 FC 98 bpm · TA 118/76 · SpO₂ 97 %',
      '🌡️ Température 38.8 °C',
    ],
  },
  {
    id: 3,
    titre: 'Consultation simple',
    icone: '💊',
    esi_attendu: '4-5',
    couleur: '#34d399',
    fond: 'rgba(52,211,153,0.08)',
    bordure: 'rgba(52,211,153,0.30)',
    details: [
      '👤 Léa Martin, 25 ans, femme',
      '🩺 Céphalée légère ce matin, légère fatigue',
      '📊 FC 72 bpm · TA 118/74 · SpO₂ 99 %',
      '🌡️ Température 36.8 °C',
    ],
  },
]

const ESI_COULEURS = {
  1: '#ef4444', 2: '#f97316', 3: '#fbbf24', 4: '#34d399', 5: '#38bdf8',
}
const ESI_LIBELLES = {
  1: 'CRITIQUE', 2: 'TRÈS URGENT', 3: 'URGENT', 4: 'PEU URGENT', 5: 'NON URGENT',
}

const ETAPES = [
  'Création du patient',
  'Analyse des symptômes',
  'Mesure des constantes',
  'Questions IA',
  'Calcul de l\'ESI',
]

async function lancerScenarioAPI(scenarioId) {
  const resp = await fetch('/api/demo/scenario', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scenario_id: scenarioId }),
  })
  if (!resp.ok) throw new Error(`Erreur ${resp.status}`)
  return resp.json()
}

function delai(ms) {
  return new Promise(r => setTimeout(r, ms))
}

function BadgeESI({ esi }) {
  const couleur = ESI_COULEURS[esi] ?? '#94a3b8'
  const libelle = ESI_LIBELLES[esi] ?? '—'
  return (
    <span
      className="demo-esi-badge"
      style={{ background: `${couleur}22`, border: `2px solid ${couleur}66`, color: couleur }}
    >
      ESI {esi} — {libelle}
    </span>
  )
}

export default function DemoPage() {
  const [etats, setEtats] = useState({ 1: null, 2: null, 3: null })

  const reinitialiser = (id) => {
    setEtats(prev => ({ ...prev, [id]: null }))
  }

  const lancer = async (id) => {
    const init = { phase: 'run', etapeActuelle: 0, resultat: null, erreur: null }
    setEtats(prev => ({ ...prev, [id]: init }))

    const avancer = (etape) => {
      setEtats(prev => ({ ...prev, [id]: { ...prev[id], etapeActuelle: etape } }))
    }

    try {
      // Animation des étapes avant l'appel API
      for (let i = 0; i < ETAPES.length - 1; i++) {
        avancer(i)
        await delai(500)
      }

      // Appel API réel
      const res = await lancerScenarioAPI(id)

      avancer(ETAPES.length - 1)
      await delai(300)

      setEtats(prev => ({
        ...prev,
        [id]: { phase: 'done', etapeActuelle: ETAPES.length, resultat: res, erreur: null },
      }))
    } catch (err) {
      setEtats(prev => ({
        ...prev,
        [id]: { phase: 'erreur', etapeActuelle: 0, resultat: null, erreur: err.message },
      }))
    }
  }

  return (
    <div className="demo-shell">
      <header className="demo-header">
        <div className="demo-header-content">
          <div className="demo-logo">🏥</div>
          <div>
            <h1 className="demo-titre">HealthGate — Interface de démonstration</h1>
            <p className="demo-sous-titre">
              Soutenance PLBD-4 · Orchestration des scénarios de triage
            </p>
          </div>
        </div>
        <a className="demo-lien-borne" href="/" target="_blank" rel="noopener noreferrer">
          Ouvrir la borne →
        </a>
      </header>

      <main className="demo-main">
        <div className="demo-grid">
          {SCENARIOS.map(sc => {
            const etat = etats[sc.id]
            return (
              <ScenarioCard
                key={sc.id}
                scenario={sc}
                etat={etat}
                onLancer={() => lancer(sc.id)}
                onReinit={() => reinitialiser(sc.id)}
              />
            )
          })}
        </div>

        <div className="demo-liens-rapides">
          <span className="demo-liens-label">Interfaces</span>
          <a href="/salle" target="_blank" rel="noopener noreferrer" className="demo-lien">
            📺 Salle d'attente
          </a>
          <a href="/medecin/M1" target="_blank" rel="noopener noreferrer" className="demo-lien">
            👨‍⚕️ Dr. El Amrani
          </a>
          <a href="/medecin/M2" target="_blank" rel="noopener noreferrer" className="demo-lien">
            👩‍⚕️ Dr. Bensouda
          </a>
        </div>
      </main>
    </div>
  )
}

function ScenarioCard({ scenario, etat, onLancer, onReinit }) {
  const idle = !etat
  const enCours = etat?.phase === 'run'
  const done = etat?.phase === 'done'
  const erreur = etat?.phase === 'erreur'

  return (
    <div
      className="demo-card"
      style={{ borderColor: scenario.bordure, background: scenario.fond }}
    >
      {/* En-tête scénario */}
      <div className="demo-card-header">
        <span className="demo-card-icone">{scenario.icone}</span>
        <div>
          <h2 className="demo-card-titre" style={{ color: scenario.couleur }}>
            {scenario.titre}
          </h2>
          <span className="demo-card-esi-attendu">
            ESI attendu : {scenario.esi_attendu}
          </span>
        </div>
      </div>

      {/* Détails patients */}
      <ul className="demo-card-details">
        {scenario.details.map((d, i) => <li key={i}>{d}</li>)}
      </ul>

      {/* Barre d'étapes */}
      {(enCours || done) && (
        <div className="demo-etapes">
          {ETAPES.map((etape, i) => {
            const ok = (etat.etapeActuelle ?? 0) > i
            const actif = (etat.etapeActuelle ?? 0) === i
            return (
              <div key={i} className={`demo-etape${ok ? ' demo-etape--ok' : ''}${actif ? ' demo-etape--actif' : ''}`}>
                <span className="demo-etape-ico">{ok ? '✓' : actif ? '⟳' : '○'}</span>
                <span className="demo-etape-label">{etape}</span>
              </div>
            )
          })}
        </div>
      )}

      {/* Résultat */}
      {done && etat.resultat && (
        <div className="demo-resultat">
          <BadgeESI esi={etat.resultat.esi_predit} />
          <div className="demo-res-meta">
            <span>Position : <b>{etat.resultat.position_file}</b></span>
            <span>Attente : <b>{etat.resultat.attente_estimee}</b></span>
            <span>Médecin : <b>{etat.resultat.medecin_assigne}</b></span>
            <span>Fiabilité IA : <b>{Math.round(etat.resultat.confiance)} %</b></span>
            {etat.resultat.regle_clinique && (
              <span className="demo-res-regle">⚠️ Règle clinique appliquée</span>
            )}
          </div>
          {(etat.resultat.explications ?? []).length > 0 && (
            <div className="demo-explications">
              <p className="demo-expl-titre">Facteurs IA :</p>
              {etat.resultat.explications.map((e, i) => (
                <div key={i} className="demo-expl-item">✓ {e}</div>
              ))}
            </div>
          )}
          <p className="demo-res-id">ID : {etat.resultat.patient_id}</p>
        </div>
      )}

      {/* Erreur */}
      {erreur && (
        <div className="demo-erreur">⚠️ {etat.erreur}</div>
      )}

      {/* Actions */}
      <div className="demo-card-actions">
        {idle && (
          <button className="demo-btn demo-btn--lancer" onClick={onLancer}>
            ▶ Lancer ce scénario
          </button>
        )}
        {enCours && (
          <button className="demo-btn demo-btn--disabled" disabled>
            ⟳ En cours…
          </button>
        )}
        {(done || erreur) && (
          <button className="demo-btn demo-btn--reset" onClick={onReinit}>
            ↺ Réinitialiser
          </button>
        )}
      </div>
    </div>
  )
}
