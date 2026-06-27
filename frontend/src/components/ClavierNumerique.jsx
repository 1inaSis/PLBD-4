import ReactDOM from 'react-dom'

const STYLE_WRAPPER = {
  position: 'fixed',
  bottom: 0,
  left: '50%',
  transform: 'translateX(-50%)',
  zIndex: 9999,
  background: '#fff',
  borderRadius: '20px 20px 0 0',
  boxShadow: '0 -8px 40px rgba(0,0,0,0.35)',
  padding: '16px',
  width: '280px',
}

const STYLE_GRID = {
  display: 'grid',
  gridTemplateColumns: 'repeat(3, 1fr)',
  gap: '10px',
}

const STYLE_BTN_BASE = {
  height: '64px',
  fontSize: '1.5rem',
  fontWeight: 700,
  background: '#f1f5f9',
  border: '1px solid #cbd5e1',
  borderRadius: '12px',
  cursor: 'pointer',
  color: '#0f172a',
}

const STYLE_BTN_CONFIRM = {
  height: '64px',
  fontSize: '1.5rem',
  fontWeight: 700,
  background: '#10b981',
  border: 'none',
  borderRadius: '12px',
  cursor: 'pointer',
  color: '#fff',
}

const STYLE_BTN_BACK = {
  height: '64px',
  fontSize: '1.5rem',
  fontWeight: 700,
  background: '#f87171',
  border: 'none',
  borderRadius: '12px',
  cursor: 'pointer',
  color: '#fff',
}

// Layout : 7 8 9 / 4 5 6 / 1 2 3 / ← 0 ✓
const TOUCHES = ['7', '8', '9', '4', '5', '6', '1', '2', '3', '←', '0', '✓']

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
    <div style={STYLE_WRAPPER}>
      <div style={STYLE_GRID}>
        {TOUCHES.map((touche, i) => {
          let style = STYLE_BTN_BASE
          if (touche === '✓') style = STYLE_BTN_CONFIRM
          if (touche === '←') style = STYLE_BTN_BACK

          return (
            <button
              key={i}
              style={style}
              onPointerDown={(e) => {
                e.preventDefault()
                if (touche === '✓') onConfirm()
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
