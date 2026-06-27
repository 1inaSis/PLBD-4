import { useState } from 'react'
import ReactDOM from 'react-dom'

const LAYOUTS = {
  fr: [
    ['a', 'z', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'],
    ['q', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm'],
    ['SHIFT', 'w', 'x', 'c', 'v', 'b', 'n', '←'],
    [',.', 'ESPACE', '✓'],
  ],
  en: [
    ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'],
    ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l'],
    ['SHIFT', 'z', 'x', 'c', 'v', 'b', 'n', 'm', '←'],
    [',.', 'ESPACE', '✓'],
  ],
  ar: [
    ['ض', 'ص', 'ث', 'ق', 'ف', 'غ', 'ع', 'ه', 'خ', 'ح', 'ج'],
    ['ش', 'س', 'ي', 'ب', 'ل', 'ا', 'ت', 'ن', 'م', 'ك'],
    ['ئ', 'ء', 'ؤ', 'ر', 'لا', 'ى', 'ة', 'و', 'ز', 'ظ'],
    ['ESPACE', '←', '✓'],
  ],
}

const STYLE_WRAPPER = {
  position: 'fixed',
  bottom: 0,
  left: 0,
  right: 0,
  zIndex: 9999,
  background: '#1e293b',
  borderRadius: '20px 20px 0 0',
  boxShadow: '0 -8px 40px rgba(0,0,0,0.5)',
  padding: '12px 8px',
}

const STYLE_LIGNE = {
  display: 'flex',
  justifyContent: 'center',
  gap: '5px',
  marginBottom: '5px',
}

const STYLE_BTN_BASE = {
  minHeight: '48px',
  minWidth: '36px',
  fontSize: '1.1rem',
  background: '#334155',
  border: 'none',
  borderRadius: '8px',
  cursor: 'pointer',
  color: '#f8fafc',
  padding: '4px',
}

const STYLE_BTN_FONCTION = {
  minHeight: '48px',
  minWidth: '36px',
  fontSize: '1.1rem',
  background: '#475569',
  border: 'none',
  borderRadius: '8px',
  cursor: 'pointer',
  color: '#f8fafc',
  padding: '4px',
}

const STYLE_BTN_CONFIRM = {
  minHeight: '48px',
  minWidth: '36px',
  fontSize: '1.1rem',
  background: '#10b981',
  border: 'none',
  borderRadius: '8px',
  cursor: 'pointer',
  color: '#f8fafc',
  padding: '4px',
}

const STYLE_BTN_BACK = {
  minHeight: '48px',
  minWidth: '36px',
  fontSize: '1.1rem',
  background: '#f87171',
  border: 'none',
  borderRadius: '8px',
  cursor: 'pointer',
  color: '#f8fafc',
  padding: '4px',
}

const STYLE_BTN_ESPACE = {
  minHeight: '48px',
  minWidth: '120px',
  fontSize: '1.1rem',
  background: '#475569',
  border: 'none',
  borderRadius: '8px',
  cursor: 'pointer',
  color: '#f8fafc',
  padding: '4px',
}

export default function ClavierAlpha({
  value = '',
  onChange,
  onConfirm,
  langue = 'fr',
}) {
  const [majuscule, setMajuscule] = useState(false)

  const layout = LAYOUTS[langue] ?? LAYOUTS.fr

  const gererTouche = (touche) => {
    if (touche === '✓') {
      onConfirm()
      return
    }
    if (touche === '←') {
      onChange(value.slice(0, -1))
      return
    }
    if (touche === 'ESPACE') {
      onChange(value + ' ')
      return
    }
    if (touche === 'SHIFT') {
      setMajuscule((m) => !m)
      return
    }
    if (touche === ',.') {
      onChange(value + ',')
      return
    }
    const char = majuscule ? touche.toUpperCase() : touche
    onChange(value + char)
  }

  const getStyle = (touche) => {
    if (touche === '✓') return STYLE_BTN_CONFIRM
    if (touche === '←') return STYLE_BTN_BACK
    if (touche === 'ESPACE') return STYLE_BTN_ESPACE
    if (touche === 'SHIFT') return majuscule
      ? { ...STYLE_BTN_FONCTION, background: '#64748b', color: '#38bdf8' }
      : STYLE_BTN_FONCTION
    if (touche === ',.') return STYLE_BTN_FONCTION
    return STYLE_BTN_BASE
  }

  const getLabel = (touche) => {
    if (touche === 'SHIFT') return '⇧'
    if (touche === 'ESPACE') return '⎵'
    if (touche === ',.') return ',.'
    if (majuscule && touche.length === 1) return touche.toUpperCase()
    return touche
  }

  const clavier = (
    <div style={STYLE_WRAPPER} dir={langue === 'ar' ? 'rtl' : 'ltr'}>
      {layout.map((ligne, iLigne) => (
        <div key={iLigne} style={STYLE_LIGNE}>
          {ligne.map((touche, iTouche) => (
            <button
              key={iTouche}
              style={getStyle(touche)}
              onPointerDown={(e) => {
                e.preventDefault()
                gererTouche(touche)
              }}
            >
              {getLabel(touche)}
            </button>
          ))}
        </div>
      ))}
    </div>
  )

  return ReactDOM.createPortal(clavier, document.body)
}
