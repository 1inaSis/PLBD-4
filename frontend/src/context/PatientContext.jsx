import { createContext, useContext, useReducer, useRef, useCallback } from 'react'

// ── État initial ─────────────────────────────────────────────────────────────
const etatInitial = {
  // Étape 1 — Identité
  session_id:  null,
  nom:         '',
  prenom:      '',
  age:         null,
  sexe:        null,
  numero_cin:  '',

  // Étape 2 — Symptômes
  symptom_text: '',
  zones_corps:  [],

  // Étape 3 — Constantes vitales
  constantes: null,

  // Étape 4 — Questions adaptatives
  questions:         [],
  question_reponses: {},

  // Étape 5 — Résultat triage
  resultat_triage: null,
}

// ── Reducer ──────────────────────────────────────────────────────────────────
function patientReducer(etat, action) {
  switch (action.type) {
    case 'SET_IDENTITE':
      return { ...etat, ...action.payload }

    case 'SET_SYMPTOMES':
      return {
        ...etat,
        symptom_text: action.payload.symptom_text,
        zones_corps:  action.payload.zones_corps ?? [],
      }

    case 'SET_CONSTANTES':
      return { ...etat, constantes: action.payload }

    case 'SET_QUESTIONS':
      return { ...etat, questions: action.payload }

    case 'SET_REPONSE':
      return {
        ...etat,
        question_reponses: {
          ...etat.question_reponses,
          [action.payload.feature_name]: action.payload.valeur,
        },
      }

    case 'SET_RESULTAT_TRIAGE':
      return { ...etat, resultat_triage: action.payload }

    case 'REINITIALISER':
      return { ...etatInitial }

    default:
      return etat
  }
}

// ── Contexte ─────────────────────────────────────────────────────────────────
export const PatientContext = createContext(null)

export function PatientProvider({ children }) {
  const [patient, dispatch] = useReducer(patientReducer, etatInitial)

  // Référence WebSocket — useRef évite les re-renders inutiles
  const wsRef = useRef(null)

  // Connexion WebSocket role=borne (créée une seule fois par session)
  const connecterBorne = useCallback((onEvenement) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return wsRef.current

    const ws = new WebSocket('/ws?role=borne')

    ws.onopen  = () => console.log('[WS borne] Connectée')
    ws.onerror = (e) => console.error('[WS borne] Erreur', e)
    ws.onclose = () => console.log('[WS borne] Déconnectée')

    if (onEvenement) {
      ws.onmessage = (e) => {
        try { onEvenement(JSON.parse(e.data)) }
        catch { /* message non-JSON ignoré */ }
      }
    }

    wsRef.current = ws
    return ws
  }, [])

  // Ferme la connexion WebSocket (fin de parcours ou nouvelle session)
  const deconnecterBorne = useCallback(() => {
    wsRef.current?.close()
    wsRef.current = null
  }, [])

  // ── Actions ──────────────────────────────────────────────────────────────
  const setIdentite      = (data)  => dispatch({ type: 'SET_IDENTITE',      payload: data })
  const setSymptomes     = (text, zones) =>
    dispatch({ type: 'SET_SYMPTOMES', payload: { symptom_text: text, zones_corps: zones } })
  const setConstantes    = (data)  => dispatch({ type: 'SET_CONSTANTES',    payload: data })
  const setQuestions     = (liste) => dispatch({ type: 'SET_QUESTIONS',      payload: liste })
  const setReponse       = (name, val) =>
    dispatch({ type: 'SET_REPONSE', payload: { feature_name: name, valeur: val } })
  const setResultatTriage = (res)  => dispatch({ type: 'SET_RESULTAT_TRIAGE', payload: res })
  const reinitialiser    = ()      => {
    deconnecterBorne()
    dispatch({ type: 'REINITIALISER' })
  }

  return (
    <PatientContext.Provider value={{
      patient,
      wsRef,
      connecterBorne,
      deconnecterBorne,
      setIdentite,
      setSymptomes,
      setConstantes,
      setQuestions,
      setReponse,
      setResultatTriage,
      reinitialiser,
    }}>
      {children}
    </PatientContext.Provider>
  )
}

// Hook raccourci
export function usePatient() {
  const ctx = useContext(PatientContext)
  if (!ctx) throw new Error('usePatient doit être utilisé dans un PatientProvider')
  return ctx
}
