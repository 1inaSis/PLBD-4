import { useState, useEffect, useRef, useCallback } from 'react'

const DELAI_AVERTISSEMENT_MS = 2 * 60 * 1000  // 2 minutes
const DUREE_COMPTE_S         = 30

export function useInactivite({ onExpiration, actif = true }) {
  const [avertissement, setAvertissement] = useState(false)
  const [compte, setCompte]               = useState(DUREE_COMPTE_S)

  const enAvertissRef  = useRef(false)
  const timerAvertRef  = useRef(null)
  const timerCompteRef = useRef(null)

  const demarrerCompte = useCallback(() => {
    enAvertissRef.current = true
    setAvertissement(true)
    setCompte(DUREE_COMPTE_S)
    let restant = DUREE_COMPTE_S
    timerCompteRef.current = setInterval(() => {
      restant -= 1
      setCompte(restant)
      if (restant <= 0) {
        clearInterval(timerCompteRef.current)
        onExpiration?.()
      }
    }, 1000)
  }, [onExpiration])

  const reset = useCallback(() => {
    clearTimeout(timerAvertRef.current)
    clearInterval(timerCompteRef.current)
    enAvertissRef.current = false
    setAvertissement(false)
    setCompte(DUREE_COMPTE_S)
    if (!actif) return
    timerAvertRef.current = setTimeout(demarrerCompte, DELAI_AVERTISSEMENT_MS)
  }, [actif, demarrerCompte])

  useEffect(() => {
    if (!actif) return
    reset()
    const EVENTS = ['touchstart', 'mousedown', 'keydown']
    const handler = () => { if (!enAvertissRef.current) reset() }
    EVENTS.forEach(e => document.addEventListener(e, handler, { passive: true }))
    return () => {
      EVENTS.forEach(e => document.removeEventListener(e, handler))
      clearTimeout(timerAvertRef.current)
      clearInterval(timerCompteRef.current)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [actif])

  return { avertissement, compte, reset }
}
