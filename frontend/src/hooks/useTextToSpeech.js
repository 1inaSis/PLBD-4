import { useState, useCallback, useRef, useEffect } from 'react'
import { usePatient } from '../context/PatientContext'

const LANG_MAP = { fr: 'fr-FR', en: 'en-US', ar: 'ar-SA' }
const SUPPORTE = typeof window !== 'undefined' && 'speechSynthesis' in window

// Déverrouille speechSynthesis lors du premier geste utilisateur (politique autoplay Chrome)
export function activerAudio() {
  if (!SUPPORTE) return
  const silence = new SpeechSynthesisUtterance('')
  silence.volume = 0
  window.speechSynthesis.speak(silence)
}

// Attend que les voix soient chargées (Chromium charge les voix de façon asynchrone)
function attendreVoix() {
  return new Promise((resolve) => {
    const voix = window.speechSynthesis.getVoices()
    if (voix.length > 0) {
      resolve(voix)
      return
    }
    const handler = () => {
      window.speechSynthesis.removeEventListener('voiceschanged', handler)
      resolve(window.speechSynthesis.getVoices())
    }
    window.speechSynthesis.addEventListener('voiceschanged', handler)
    setTimeout(() => {
      window.speechSynthesis.removeEventListener('voiceschanged', handler)
      resolve(window.speechSynthesis.getVoices())
    }, 3000)
  })
}

export function useTextToSpeech() {
  const [estEnTrainDeParler, setEstEnTrainDeParler] = useState(false)
  const timerRef    = useRef(null)
  const { audioActif } = usePatient()
  // Ref pour éviter les stale closures dans parler()
  const audioActifRef = useRef(audioActif)
  useEffect(() => { audioActifRef.current = audioActif }, [audioActif])

  const activer = useCallback(() => { activerAudio() }, [])

  const parler = useCallback((texte, langue) => {
    console.log('[TTS] parler:', texte, langue)
    console.log('[TTS] speechSynthesis disponible:', !!window?.speechSynthesis)
    console.log('[TTS] audioActif:', audioActifRef.current)
    if (!audioActifRef.current) return   // TTS conditionnel : inactif si guidage désactivé
    if (!SUPPORTE || !texte) return

    window.speechSynthesis.cancel()
    clearTimeout(timerRef.current)

    timerRef.current = setTimeout(async () => {
      const voix = await attendreVoix()
      console.log('[TTS] voix disponibles:', voix.length)

      const langCible = LANG_MAP[langue] ?? 'fr-FR'
      const utterance = new SpeechSynthesisUtterance(texte)
      utterance.lang   = langCible
      utterance.rate   = 0.95
      utterance.volume = 1.0
      utterance.onstart = () => setEstEnTrainDeParler(true)
      utterance.onend   = () => setEstEnTrainDeParler(false)
      utterance.onerror = (e) => {
        console.log('[TTS] erreur:', e.error, '— lang:', langCible)
        setEstEnTrainDeParler(false)
      }

      window.speechSynthesis.speak(utterance)
    }, 500)
  }, [])

  const arreter = useCallback(() => {
    if (!SUPPORTE) return
    clearTimeout(timerRef.current)
    window.speechSynthesis.cancel()
    setEstEnTrainDeParler(false)
  }, [])

  return { parler, arreter, activer, estEnTrainDeParler, supporte: SUPPORTE }
}
