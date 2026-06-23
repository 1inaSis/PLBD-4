import { useState, useCallback, useRef, useEffect } from 'react'
import { usePatient } from '../context/PatientContext'

const LANG_MAP = { fr: 'fr-FR', en: 'en-US', ar: 'ar-SA' }
const SUPPORTE = typeof window !== 'undefined' && 'speechSynthesis' in window

export function activerAudio() {
  if (!SUPPORTE) return
  const silence = new SpeechSynthesisUtterance('')
  silence.volume = 0
  window.speechSynthesis.speak(silence)
}

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
    // Réduit à 500ms : si voiceschanged ne se déclenche pas, on n'attend pas 3s
    setTimeout(() => {
      window.speechSynthesis.removeEventListener('voiceschanged', handler)
      resolve(window.speechSynthesis.getVoices())
    }, 500)
  })
}

function choisirVoix(voix, langue) {
  const langCible = LANG_MAP[langue] ?? 'fr-FR'
  if (langue !== 'fr') {
    const prefixe   = langCible.split('-')[0]
    const voixCible = voix.filter(v => v.lang.startsWith(prefixe))
    if (voixCible.length > 0) return { voice: voixCible[0], lang: langCible }
    console.warn(`[TTS] Voix ${langue} non disponible, fallback FR`)
    const voixFr = voix.filter(v => v.lang.startsWith('fr'))
    return { voice: voixFr[0] ?? null, lang: 'fr-FR' }
  }
  const voixFr = voix.filter(v => v.lang.startsWith('fr'))
  return { voice: voixFr[0] ?? null, lang: 'fr-FR' }
}

export function useTextToSpeech() {
  const [estEnTrainDeParler, setEstEnTrainDeParler] = useState(false)
  const timerRef    = useRef(null)
  const { audioActif } = usePatient()
  const audioActifRef = useRef(audioActif)
  useEffect(() => { audioActifRef.current = audioActif }, [audioActif])

  const activer = useCallback(() => { activerAudio() }, [])

  const parler = useCallback((texte, langue) => {
    console.log('[TTS] parler:', texte, langue)
    console.log('[TTS] speechSynthesis disponible:', !!window?.speechSynthesis)
    console.log('[TTS] audioActif:', audioActifRef.current)
    if (!audioActifRef.current) return
    if (!SUPPORTE || !texte) return

    window.speechSynthesis.cancel()
    clearTimeout(timerRef.current)

    timerRef.current = setTimeout(async () => {
      const voix = await attendreVoix()
      console.log('[TTS] voix disponibles:', voix.length)

      const { voice, lang } = choisirVoix(voix, langue)
      const utterance = new SpeechSynthesisUtterance(texte)
      utterance.lang   = lang
      utterance.rate   = 0.95
      utterance.volume = 1.0
      if (voice) utterance.voice = voice
      utterance.onstart = () => setEstEnTrainDeParler(true)
      utterance.onend   = () => setEstEnTrainDeParler(false)
      utterance.onerror = (e) => {
        console.log('[TTS] erreur:', e.error, '— lang:', lang)
        setEstEnTrainDeParler(false)
      }

      window.speechSynthesis.speak(utterance)
    }, 300)
  }, [])

  const arreter = useCallback(() => {
    if (!SUPPORTE) return
    clearTimeout(timerRef.current)
    window.speechSynthesis.cancel()
    setEstEnTrainDeParler(false)
  }, [])

  return { parler, arreter, activer, estEnTrainDeParler, supporte: SUPPORTE }
}
