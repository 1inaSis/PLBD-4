import { useState, useCallback } from 'react'

const LANG_MAP = { fr: 'fr-FR', en: 'en-US', ar: 'ar-SA' }
const SUPPORTE = typeof window !== 'undefined' && 'speechSynthesis' in window

// Déverrouille speechSynthesis lors du premier geste utilisateur (politique autoplay Chrome)
export function activerAudio() {
  if (!SUPPORTE) return
  const silence = new SpeechSynthesisUtterance('')
  silence.volume = 0
  window.speechSynthesis.speak(silence)
}

export function useTextToSpeech() {
  const [estEnTrainDeParler, setEstEnTrainDeParler] = useState(false)

  const activer = useCallback(() => { activerAudio() }, [])

  const parler = useCallback((texte, langue) => {
    if (!SUPPORTE || !texte) return
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(texte)
    utterance.lang   = LANG_MAP[langue] ?? 'fr-FR'
    utterance.rate   = 0.95
    utterance.volume = 1.0
    utterance.onstart = () => setEstEnTrainDeParler(true)
    utterance.onend   = () => setEstEnTrainDeParler(false)
    utterance.onerror = () => setEstEnTrainDeParler(false)
    window.speechSynthesis.speak(utterance)
  }, [])

  const arreter = useCallback(() => {
    if (!SUPPORTE) return
    window.speechSynthesis.cancel()
    setEstEnTrainDeParler(false)
  }, [])

  return { parler, arreter, activer, estEnTrainDeParler, supporte: SUPPORTE }
}
