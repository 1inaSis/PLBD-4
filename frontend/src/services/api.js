// Toutes les requêtes REST vers le backend FastAPI.
// Le proxy Vite redirige /api/* → http://localhost:8000/api/*

const API = '/api'

async function requete(chemin, options = {}) {
  const reponse = await fetch(`${API}${chemin}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  const data = await reponse.json()
  if (!reponse.ok) {
    throw new Error(data.detail ?? `Erreur ${reponse.status}`)
  }
  return data
}

// ── Étape 1 : Scanner la CIN ─────────────────────────────────────────────────
// imageBase64 : string base64 de l'image, ou null → caméra / simulation
export function scannerCIN(imageBase64 = null) {
  return requete('/scanner', {
    method: 'POST',
    body: JSON.stringify({ image_base64: imageBase64 }),
  })
}

// ── Étape 1b : Saisie manuelle identité (filet si OCR incomplet) ─────────────
export function saisirManuel(session_id, nom, prenom, date_naissance) {
  return requete('/scanner/manuel', {
    method: 'POST',
    body: JSON.stringify({ session_id, nom, prenom, date_naissance }),
  })
}

// ── Étape 2 : Enregistrer les symptômes ──────────────────────────────────────
export function soumettreSymptomes(session_id, symptom_text, zones_corps = []) {
  return requete('/symptomes', {
    method: 'POST',
    body: JSON.stringify({ session_id, symptom_text, zones_corps }),
  })
}

// ── Étape 3 : Lire les constantes vitales (capteurs ou simulation) ───────────
// session_id : si fourni, les constantes sont stockées en session côté serveur
export function lireConstantes(session_id = null) {
  const params = session_id ? `?session_id=${session_id}` : ''
  return requete(`/constantes${params}`)
}

// ── Étape 3 : Lifecycle Arduino (démarrage/arrêt avec ConstantesPage) ────────
// demarrerArduino : appelé au mount de ConstantesPage
export function demarrerArduino() {
  return requete('/constantes/start')
}

// arreterArduino : appelé au unmount de ConstantesPage (keepalive = survit à la navigation)
export function arreterArduino() {
  return fetch('/api/constantes/stop', { keepalive: true }).catch(() => {})
}

// ── Étape 3 : Mesure unitaire d'une constante (mode commande Arduino) ────────
// type      : "temperature" | "spo2" | "tension"
// session_id: si fourni, la valeur est stockée en session côté serveur
export function mesurerConstante(type, session_id = null) {
  return requete('/constantes/mesurer', {
    method: 'POST',
    body: JSON.stringify({ type, session_id }),
  })
}

// ── Étape 4 : Demander UNE question adaptative (mode question par question) ──
// reponses_precedentes : [{question, feature_name, reponse}]
export function demanderQuestionSuivante(session_id, reponses_precedentes = [], constantes = null, symptomes = null) {
  return requete('/questions/suivante', {
    method: 'POST',
    body: JSON.stringify({ session_id, reponses_precedentes, constantes, symptomes }),
  })
}

// ── Étape 5 : Lancer le triage ESI ───────────────────────────────────────────
export function lancerTriage(session_id, constantes = null, question_reponses = {}) {
  return requete('/triage', {
    method: 'POST',
    body: JSON.stringify({ session_id, constantes, question_reponses }),
  })
}

// ── File d'attente ────────────────────────────────────────────────────────────
export function getFile() {
  return requete('/file')
}

// ── Rapport détaillé d'un patient ────────────────────────────────────────────
export function getRapportPatient(patient_id) {
  return requete(`/rapport/${encodeURIComponent(patient_id)}`)
}

// ── Médecin ───────────────────────────────────────────────────────────────────
export function getPatientsMedecin(medecin_id) {
  return requete(`/medecin/${medecin_id}`)
}

export function prendreEnCharge(patient_id, medecin_id) {
  return requete('/prise_en_charge', {
    method: 'POST',
    body: JSON.stringify({ patient_id, medecin_id }),
  })
}

// ── Statistiques ──────────────────────────────────────────────────────────────
export function getStats() {
  return requete('/stats')
}

// ── Démo / Admin ──────────────────────────────────────────────────────────────
export function demarrerDemo() {
  return requete('/demo/patient', { method: 'POST' })
}

export function reinitialiserFile() {
  return requete('/admin/reset', { method: 'POST' })
}

export function abandonnerSession(session_id) {
  return fetch('/api/session/abandon', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id }),
    keepalive: true,
  }).catch(() => {})
}
