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

const W = {
  wrapper: {
    position: 'fixed',
    bottom: 0,
    left: 0,
    right: 0,
    zIndex: 9999,
    background: '#fff',
    borderRadius: '20px 20px 0 0',
    boxShadow: '0 -4px 20px rgba(0,0,0,0.15)',
    padding: '12px 6px 18px',
    userSelect: 'none',
  },
  ligne: {
    display: 'flex',
    justifyContent: 'center',
    gap: '5px',
    marginBottom: '5px',
  },
  base: {
    minHeight: '52px',
    minWidth: '32px',
    fontSize: '18px',
    fontWeight: 600,
    background: '#f5f5f5',
    border: '1px solid #ddd',
    borderRadius: '8px',
    cursor: 'pointer',
    color: '#0f172a',
    padding: '4px 6px',
    WebkitTapHighlightColor: 'transparent',
  },
  fonction: {
    minHeight: '52px',
    minWidth: '44px',
    fontSize: '16px',
    fontWeight: 600,
    background: '#e2e8f0',
    border: '1px solid #cbd5e1',
    borderRadius: '8px',
    cursor: 'pointer',
    color: '#0f172a',
    padding: '4px 8px',
    WebkitTapHighlightColor: 'transparent',
  },
  confirm: {
    minHeight: '52px',
    minWidth: '64px',
    fontSize: '18px',
    fontWeight: 700,
    background: '#10b981',
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer',
    color: '#fff',
    padding: '4px 12px',
    WebkitTapHighlightColor: 'transparent',
  },
  back: {
    minHeight: '52px',
    minWidth: '44px',
    fontSize: '18px',
    fontWeight: 700,
    background: '#ef4444',
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer',
    color: '#fff',
    padding: '4px 8px',
    WebkitTapHighlightColor: 'transparent',
  },
  espace: {
    minHeight: '52px',
    minWidth: '140px',
    fontSize: '16px',
    fontWeight: 600,
    background: '#e2e8f0',
    border: '1px solid #cbd5e1',
    borderRadius: '8px',
    cursor: 'pointer',
    color: '#0f172a',
    padding: '4px 12px',
    WebkitTapHighlightColor: 'transparent',
  },
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
    if (touche === '✓')     { onConfirm?.(); return }
    if (touche === '←')     { onChange(value.slice(0, -1)); return }
    if (touche === 'ESPACE') { onChange(value + ' '); return }
    if (touche === 'SHIFT') { setMajuscule((m) => !m); return }
    if (touche === ',.')    { onChange(value + ','); return }
    onChange(value + (majuscule ? touche.toUpperCase() : touche))
  }

  const getStyle = (touche) => {
    if (touche === '✓')     return W.confirm
    if (touche === '←')     return W.back
    if (touche === 'ESPACE') return W.espace
    if (touche === 'SHIFT') return majuscule
      ? { ...W.fonction, background: '#bfdbfe', color: '#1d4ed8' }
      : W.fonction
    if (touche === ',.') return W.fonction
    return W.base
  }

  const getLabel = (touche) => {
    if (touche === 'SHIFT')  return '⇧'
    if (touche === 'ESPACE') return '⎵'
    if (touche === ',.')     return ',.'
    if (majuscule && touche.length === 1) return touche.toUpperCase()
    return touche
  }

  const clavier = (
    <div
      style={W.wrapper}
      dir={langue === 'ar' ? 'rtl' : 'ltr'}
      onMouseDown={(e) => { e.preventDefault(); e.stopPropagation() }}
      onPointerDown={(e) => { e.preventDefault(); e.stopPropagation() }}
    >
      {layout.map((ligne, iLigne) => (
        <div key={iLigne} style={W.ligne}>
          {ligne.map((touche, iTouche) => (
            <button
              key={iTouche}
              style={getStyle(touche)}
              onPointerDown={(e) => {
                e.preventDefault()
                e.stopPropagation()
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
