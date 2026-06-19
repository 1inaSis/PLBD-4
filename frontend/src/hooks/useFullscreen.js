import { useState, useEffect, useCallback } from 'react'

export function useFullscreen() {
  const [isFullscreen, setIsFullscreen] = useState(
    () => !!document.fullscreenElement
  )

  useEffect(() => {
    const onChange = () => setIsFullscreen(!!document.fullscreenElement)
    document.addEventListener('fullscreenchange', onChange)
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [])

  const enterFullscreen = useCallback(async () => {
    try {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen()
      }
    } catch { /* refusé sans geste utilisateur — silencieux */ }
  }, [])

  const toggleFullscreen = useCallback(async () => {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen()
      } else {
        await document.documentElement.requestFullscreen()
      }
    } catch { /* silencieux */ }
  }, [])

  // Touche F11 pour toggle
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'F11') { e.preventDefault(); toggleFullscreen() }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [toggleFullscreen])

  // Tentative auto au premier montage (échoue sans geste — silencieuse)
  useEffect(() => {
    enterFullscreen()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { isFullscreen, enterFullscreen, toggleFullscreen }
}
