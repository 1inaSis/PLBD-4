import { useFullscreen } from '../hooks/useFullscreen'

export default function BoutonPleinEcran() {
  const { isFullscreen, toggleFullscreen } = useFullscreen()

  return (
    <button
      className={`btn-plein-ecran${isFullscreen ? ' btn-plein-ecran--actif' : ''}`}
      onClick={toggleFullscreen}
      title="Plein écran (F11)"
      aria-label={isFullscreen ? 'Quitter le plein écran' : 'Passer en plein écran'}
    >
      {isFullscreen ? '✕' : '⛶'}
    </button>
  )
}
