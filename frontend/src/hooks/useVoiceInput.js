// Hook partagé — Web Speech API (reconnaissance vocale)
//
// Paramètres :
//   langue  : 'fr' | 'en' | 'ar'  → mappé vers 'fr-FR', 'en-US', 'ar-SA'
//   onResult(transcript) : callback appelé avec le texte reconnu (final)
//   onEnd()              : callback optionnel appelé quand la reconnaissance s'arrête
//   timeout              : délai ms avant arrêt auto si silence (défaut 10 000)
//
// Retourne :
//   { supporte, ecoute, demarrer, arreter }
//   supporte : bool (false si Web Speech API absente)
//   ecoute   : bool (true pendant l'écoute active)

import { useState, useEffect, useRef, useCallback } from 'react'

const LANG_MAP = { fr: 'fr-FR', en: 'en-US', ar: 'ar-SA' }
const TIMEOUT_DEFAUT = 10_000

export function useVoiceInput({
  langue   = 'fr',
  onResult,
  onEnd,
  timeout  = TIMEOUT_DEFAUT,
} = {}) {
  // Détection de l'API (côté client uniquement)
  const supporte =
    typeof window !== 'undefined' &&
    !!(window.SpeechRecognition || window.webkitSpeechRecognition)

  const [ecoute, setEcoute] = useState(false)

  // Refs stables pour éviter les closures périmées
  const recoRef     = useRef(null)
  const timerRef    = useRef(null)
  const onResultRef = useRef(onResult)
  const onEndRef    = useRef(onEnd)

  useEffect(() => { onResultRef.current = onResult }, [onResult])
  useEffect(() => { onEndRef.current    = onEnd    }, [onEnd])

  // ── arreter ───────────────────────────────────────────────────────────────
  const arreter = useCallback(() => {
    clearTimeout(timerRef.current)
    if (recoRef.current) {
      recoRef.current.onend = null   // évite un double-appel de onEnd
      try { recoRef.current.stop() } catch { /* ignoré */ }
      recoRef.current = null
    }
    setEcoute(false)
    onEndRef.current?.()
  }, [])

  // ── demarrer ──────────────────────────────────────────────────────────────
  const demarrer = useCallback(() => {
    if (!supporte || recoRef.current) return   // déjà en écoute ou non supporté

    const SR   = window.SpeechRecognition || window.webkitSpeechRecognition
    const reco = new SR()
    reco.lang            = LANG_MAP[langue] ?? 'fr-FR'
    reco.interimResults  = false
    reco.continuous      = false

    reco.onresult = (e) => {
      clearTimeout(timerRef.current)
      const transcript = e.results[0]?.[0]?.transcript ?? ''
      if (transcript.trim()) onResultRef.current?.(transcript.trim())
    }

    reco.onend = () => {
      clearTimeout(timerRef.current)
      recoRef.current = null
      setEcoute(false)
      onEndRef.current?.()
    }

    reco.onerror = () => {
      clearTimeout(timerRef.current)
      recoRef.current = null
      setEcoute(false)
      // Erreurs gérées silencieusement (pas de throw)
    }

    reco.start()
    recoRef.current = reco
    setEcoute(true)

    // Timeout : arrêt automatique si silence
    timerRef.current = setTimeout(arreter, timeout)
  }, [supporte, langue, timeout, arreter])

  // ── Nettoyage au démontage ─────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      clearTimeout(timerRef.current)
      if (recoRef.current) {
        recoRef.current.onend = null
        try { recoRef.current.stop() } catch { /* ignoré */ }
        recoRef.current = null
      }
    }
  }, [])

  return { supporte, ecoute, demarrer, arreter }
}
