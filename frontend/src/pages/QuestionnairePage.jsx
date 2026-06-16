// Étape 2 / 5 — Questionnaire symptômes
// Patient sélectionne les zones douloureuses sur le pictogramme
// et décrit librement ses symptômes. POST /api/symptomes envoie
// le texte + les zones ; le NLP extrait les features côté serveur.

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePatient } from '../context/PatientContext'
import { soumettreSymptomes } from '../services/api'
import IndicateurEtape from '../components/IndicateurEtape'
import CorpsHumain, { ZONES_MAP } from '../components/CorpsHumain'
import '../styles/kiosk.css'

export default function QuestionnairePage() {
  const navigate = useNavigate()
  const { patient, setSymptomes } = usePatient()

  const [zonesSelectionnees, setZonesSelectionnees] = useState([])
  const [texteSymptome, setTexteSymptome] = useState('')
  const [enChargement, setEnChargement]   = useState(false)
  const [erreur, setErreur]               = useState(null)
  const [urgenceDetectee, setUrgenceDetectee] = useState(false)

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
        // Afficher l'alerte 2,5 s puis naviguer automatiquement
        setUrgenceDetectee(true)
        setTimeout(() => navigate('/constantes'), 2500)
      } else {
        navigate('/constantes')
      }
    } catch (err) {
      setErreur(`Erreur : ${err.message}`)
    } finally {
      setEnChargement(false)
    }
  }

  return (
    <div className="kiosk-shell">
      <IndicateurEtape etapeCourante={2} />

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
            <span className="eyebrow">Étape 2 / 5 · Symptômes</span>
            <h2 className="kiosk-titre-sm">
              {patient.prenom ? `Où avez-vous mal, ${patient.prenom} ?` : 'Où avez-vous mal ?'}
            </h2>

            {/* Chips des zones sélectionnées */}
            {zonesSelectionnees.length > 0 ? (
              <div className="zones-choisies">
                <p className="zones-choisies-titre">Zones sélectionnées :</p>
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
                Appuyez sur le schéma pour sélectionner vos zones douloureuses.
              </p>
            )}

            {/* Champ de description libre */}
            <div className="symptome-groupe">
              <label className="symptome-label" htmlFor="symptome-texte">
                Décrivez vos symptômes <span className="symptome-optionnel">(optionnel si zones sélectionnées)</span>
              </label>
              <textarea
                id="symptome-texte"
                className="symptome-input"
                placeholder="Ex : j'ai très mal à la poitrine depuis ce matin, j'ai du mal à respirer…"
                value={texteSymptome}
                onChange={e => setTexteSymptome(e.target.value)}
                rows={4}
                maxLength={500}
              />
              <span className="symptome-compteur">{texteSymptome.length} / 500</span>
            </div>

            {/* Alerte urgence détectée par le NLP */}
            {urgenceDetectee && (
              <div className="kiosk-alerte kiosk-alerte--urgence" role="alert" aria-live="assertive">
                ⚠️ Urgence détectée — Le personnel soignant est alerté. Vous serez pris en charge très rapidement.
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
                {enChargement ? 'Envoi en cours…' : 'Continuer →'}
              </button>
              <button
                className="kiosk-btn kiosk-btn--secondary"
                onClick={() => navigate('/')}
                disabled={enChargement}
              >
                ← Retour
              </button>
            </div>
          </div>
        </section>

      </div>
    </div>
  )
}
