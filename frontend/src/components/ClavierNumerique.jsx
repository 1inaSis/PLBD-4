import ReactDOM from 'react-dom'

// Layout : 7 8 9 / 4 5 6 / 1 2 3 / ← 0 ✓
const TOUCHES = ['7', '8', '9', '4', '5', '6', '1', '2', '3', '←', '0', '✓']

const W = {
  wrapper: {
    position: 'fixed',
    bottom: 0,
    left: 0,
    width: '100vw',
    zIndex: 9999,
    background: '#fff',
    borderRadius: '20px 20px 0 0',
    boxShadow: '0 -4px 20px rgba(0,0,0,0.15)',
    padding: '16px 12px 20px',
    userSelect: 'none',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, 1fr)',
    gap: '8px',
    maxWidth: '340px',
    margin: '0 auto',
  },
  base: {
    height: '64px',
    minWidth: '64px',
    fontSize: '24px',
    fontWeight: 700,
    background: '#f5f5f5',
    border: '1px solid #ddd',
    borderRadius: '8px',
    cursor: 'pointer',
    color: '#0f172a',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    WebkitTapHighlightColor: 'transparent',
  },
  confirm: {
    height: '64px',
    minWidth: '64px',
    fontSize: '24px',
    fontWeight: 700,
    background: '#10b981',
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer',
    color: '#fff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    WebkitTapHighlightColor: 'transparent',
  },
  back: {
    height: '64px',
    minWidth: '64px',
    fontSize: '24px',
    fontWeight: 700,
    background: '#ef4444',
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer',
    color: '#fff',
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

  const clavier = (
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
                if (touche === '✓') onConfirm?.()
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
  )

  return ReactDOM.createPortal(clavier, document.body)
}
