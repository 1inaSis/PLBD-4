// Hook — notifications push natives (Notification API) pour médecin
// Enregistre le service worker et gère la permission utilisateur.
// La notification réelle est déclenchée par l'appelant via notifier().

import { useState, useEffect, useCallback } from 'react'

export function useNotificationPush() {
  const supported = typeof window !== 'undefined' && 'Notification' in window

  const [permission, setPermission] = useState(
    supported ? Notification.permission : 'denied'
  )

  useEffect(() => {
    if (!supported) return
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch(() => {})
    }
    setPermission(Notification.permission)
  }, [supported])

  const demander = useCallback(async () => {
    if (!supported) return false
    const perm = await Notification.requestPermission()
    setPermission(perm)
    return perm === 'granted'
  }, [supported])

  // Envoie une notification uniquement si la page est en arrière-plan
  const notifier = useCallback((titre, corps, tag = 'healthgate') => {
    if (!supported || Notification.permission !== 'granted') return
    if (!document.hidden) return
    try {
      new Notification(titre, {
        body: corps,
        icon: '/favicon.ico',
        tag,
        requireInteraction: true,
      })
    } catch { /* AudioContext ou Notification non disponible */ }
  }, [supported])

  return { permission, demander, notifier }
}
