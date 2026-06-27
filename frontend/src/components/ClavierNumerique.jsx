import ReactDOM from 'react-dom'

// Layout : 7 8 9 / 4 5 6 / 1 2 3 / ← 0 ✓
const TOUCHES = ['7', '8', '9', '4', '5', '6', '1', '2', '3', '←', '0', '✓']

const W = {
  overlay: {
    position: 'fixed',
    inset: 0,
    zIndex: 999,
    background: 'transparent',
  },
  wrapper: {
    position: 'fixed',
    bottom: 0,
    left: 0,
    width: '100vw',
    zIndex: 1000,
    background: '#060b14',
    backdropFilter: 'blur(24px)',
    WebkitBackdropFilter: 'blur(24px)',
    borderRadius: '20px 20px 0 0',
    boxShadow: '0 -4px 20px rgba(0,212,255,0.15)',
    padding: '16px 12px 22px',
    userSelect: 'none',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, 1fr)',
    gap: '10px',
    maxWidth: '360px',
    margin: '0 auto',
  },
  base: {
    height: '72px',
    minWidth: '72px',
    fontSize: '28px',
    fontWeight: 700,
    background: 'rgba(255,255,255,0.09)',
    border: '1px solid rgba(255,255,255,0.15)',
    borderRadius: '8px',
    cursor: 'pointer',
    color: '#f8fafc',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    WebkitTapHighlightColor: 'transparent',
  },
  confirm: {
    height: '72px',
    minWidth: '72px',
    fontSize: '28px',
    fontWeight: 700,
    background: 'rgba(16,185,129,0.2)',
    border: '1px solid rgba(16,185,129,0.4)',
    borderRadius: '8px',
    cursor: 'pointer',
    color: '#10b981',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    WebkitTapHighlightColor: 'transparent',
  },
  back: {
    height: '72px',
    minWidth: '72px',
    fontSize: '28px',
    fontWeight: 700,
    background: 'rgba(239,68,68,0.2)',
    border: '1px solid rgba(239,68,68,0.4)',
    borderRadius: '8px',
    cursor: 'pointer',
    color: '#ef4444',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    WebkitTapHighlightColor: 'transparent',
  },
}

export default function ClavierNumerique({
  value = '',
  onChange,
  onConfirm,
  onFermer,
  modeDate = false,
  maxLength = 10,
}) {
  const formatDate = (chiffres) => {
    if (chiffres.length === 0) return ''
    if (chiffres.length <= 2) return chiffres
    if (chiffres.length <= 4) return chiffres.slice(0, 2) + '/' + chiffres.slice(2)
    return chiffres.slice(0, 2) + '/' + chiffres.slice(2, 4) + '/' + chiffres.slice(4, 8)
  }

  const insererChiffre = (chiffre) => {
    if (modeDate) {
      const chiffres = value.replace(/\//g, '')
      if (chiffres.length >= 8) return
      onChange(formatDate(chiffres + chiffre))
    } else {
      if (value.length >= maxLength) return
      onChange(value + chiffre)
    }
  }

  const supprimerDernier = () => {
    if (modeDate) {
      const chiffres = value.replace(/\//g, '')
      onChange(formatDate(chiffres.slice(0, -1)))
    } else {
      onChange(value.slice(0, -1))
    }
  }

  const portail = (
    <>
      <div style={W.overlay} onPointerDown={() => onFermer?.()} />
      <div
        style={W.wrapper}
        onMouseDown={(e) => { e.preventDefault(); e.stopPropagation() }}
        onPointerDown={(e) => { e.preventDefault(); e.stopPropagation() }}
      >
        <div style={W.grid}>
          {TOUCHES.map((touche, i) => {
            const style = touche === '✓' ? W.confirm : touche === '←' ? W.back : W.base
            return (
              <button
                key={i}
                style={style}
                onPointerDown={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  if (touche === '✓') { onConfirm?.(); onFermer?.() }
                  else if (touche === '←') supprimerDernier()
                  else insererChiffre(touche)
                }}
              >
                {touche}
              </button>
            )
          })}
        </div>
      </div>
    </>
  )

  return ReactDOM.createPortal(portail, document.body)
}
