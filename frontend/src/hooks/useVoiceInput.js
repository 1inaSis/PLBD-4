// Hook partagé — Web Speech API (reconnaissance vocale)
//
// Paramètres :
//   langue  : 'fr' | 'en' | 'ar'  → mappé vers 'fr-FR', 'en-US', 'ar-SA'
//   onResult(transcript) : callback appelé avec le texte reconnu
//   onEnd()              : callback optionnel appelé quand la reconnaissance s'arrête
//   timeout              : délai ms avant arrêt auto si silence (défaut 15 000)
//
// Retourne :
//   { supporte, ecoute, erreurPermission, demarrer, arreter }
//   supporte        : bool (false si API absente)
//   ecoute          : bool (true pendant l'écoute active)
//   erreurPermission: string | null (message si micro refusé)

import { useState, useEffect, useRef, useCallback } from 'react'

const LANG_MAP = { fr: 'fr-FR', en: 'en-US', ar: 'ar-SA' }
const TIMEOUT_DEFAUT = 15_000

const SR_API = typeof window !== 'undefined'
  ? (window.SpeechRecognition || window.webkitSpeechRecognition)
  : null

export function useVoiceInput({
  langue   = 'fr',
  onResult,
  onEnd,
  timeout  = TIMEOUT_DEFAUT,
} = {}) {
  const supporte = !!SR_API

  const [ecoute, setEcoute]                 = useState(false)
  const [erreurPermission, setErreurPermission] = useState(null)

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
      recoRef.current.onend = null
      try { recoRef.current.stop() } catch { /* ignoré */ }
      recoRef.current = null
    }
    setEcoute(false)
    onEndRef.current?.()
  }, [])

  // ── demarrer — demande permission micro AU MOMENT du clic ─────────────────
  const demarrer = useCallback(async () => {
    if (!supporte || recoRef.current) return

    // 1. Demande permission micro (déclenche la popup Chromium)
    if (navigator.mediaDevices?.getUserMedia) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        stream.getTracks().forEach(t => t.stop())
        console.log('[VOICE] Permission micro: granted')
        setErreurPermission(null)
      } catch (err) {
        console.log('[VOICE] Permission micro: denied', err.name)
        setErreurPermission('Autorisez le micro dans Chromium')
        return
      }
    }

    // 2. Lance la reconnaissance vocale
    const reco = new SR_API()
    reco.lang            = LANG_MAP[langue] ?? 'fr-FR'
    reco.interimResults  = true
    reco.continuous      = false

    reco.onresult = (e) => {
      clearTimeout(timerRef.current)
      // Prend le meilleur transcript disponible (final ou interim)
      const transcript = Array.from(e.results)
        .map(r => r[0]?.transcript ?? '')
        .join('')
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
    }

    reco.start()
    recoRef.current = reco
    setEcoute(true)

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

  return { supporte, ecoute, erreurPermission, demarrer, arreter }
}
