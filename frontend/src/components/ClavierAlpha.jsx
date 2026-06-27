import { useState } from 'react'
import ReactDOM from 'react-dom'

const LAYOUTS = {
  fr: [
    ['a', 'z', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'],
    ['q', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm'],
    ['SHIFT', 'w', 'x', 'c', 'v', 'b', 'n', '←'],
    ["'", '-', '.', '@', 'ESPACE', '✓'],
  ],
  en: [
    ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'],
    ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l'],
    ['SHIFT', 'z', 'x', 'c', 'v', 'b', 'n', 'm', '←'],
    ["'", '-', '.', '@', 'ESPACE', '✓'],
  ],
  ar: [
    ['ض', 'ص', 'ث', 'ق', 'ف', 'غ', 'ع', 'ه', 'خ', 'ح', 'ج'],
    ['ش', 'س', 'ي', 'ب', 'ل', 'ا', 'ت', 'ن', 'م', 'ك'],
    ['ئ', 'ء', 'ؤ', 'أ', 'إ', 'ر', 'لا', 'ى', 'ة', 'و', 'ز', 'ظ'],
    ['ESPACE', '←', '✓'],
  ],
}

// Touches spéciales (1 char) qui ne passent pas par SHIFT
const SPECIAUX = new Set(["'", '-', '.', '@'])

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
    right: 0,
    zIndex: 1000,
    background: '#060b14',
    backdropFilter: 'blur(24px)',
    WebkitBackdropFilter: 'blur(24px)',
    borderRadius: '20px 20px 0 0',
    boxShadow: '0 -4px 20px rgba(0,212,255,0.15)',
    padding: '10px 4px 16px',
    userSelect: 'none',
  },
  ligne: {
    display: 'flex',
    justifyContent: 'center',
    gap: '5px',
    marginBottom: '6px',
  },
  base: {
    minHeight: '60px',
    minWidth: '30px',
    fontSize: '22px',
    fontWeight: 600,
    background: 'rgba(255,255,255,0.09)',
    border: '1px solid rgba(255,255,255,0.15)',
    borderRadius: '8px',
    cursor: 'pointer',
    color: '#f8fafc',
    padding: '4px 6px',
    WebkitTapHighlightColor: 'transparent',
  },
  fonction: {
    minHeight: '60px',
    minWidth: '40px',
    fontSize: '18px',
    fontWeight: 600,
    background: 'rgba(255,255,255,0.05)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: '8px',
    cursor: 'pointer',
    color: '#94a3b8',
    padding: '4px 8px',
    WebkitTapHighlightColor: 'transparent',
  },
  confirm: {
    minHeight: '60px',
    minWidth: '64px',
    fontSize: '22px',
    fontWeight: 700,
    background: 'rgba(16,185,129,0.2)',
    border: '1px solid rgba(16,185,129,0.4)',
    borderRadius: '8px',
    cursor: 'pointer',
    color: '#10b981',
    padding: '4px 12px',
    WebkitTapHighlightColor: 'transparent',
  },
  back: {
    minHeight: '60px',
    minWidth: '40px',
    fontSize: '22px',
    fontWeight: 700,
    background: 'rgba(239,68,68,0.2)',
    border: '1px solid rgba(239,68,68,0.4)',
    borderRadius: '8px',
    cursor: 'pointer',
    color: '#ef4444',
    padding: '4px 8px',
    WebkitTapHighlightColor: 'transparent',
  },
  espace: {
    minHeight: '60px',
    minWidth: '130px',
    fontSize: '18px',
    fontWeight: 600,
    background: 'rgba(255,255,255,0.05)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: '8px',
    cursor: 'pointer',
    color: '#94a3b8',
    padding: '4px 12px',
    WebkitTapHighlightColor: 'transparent',
  },
}

export default function ClavierAlpha({
  value = '',
  onChange,
  onConfirm,
  onFermer,
  langue = 'fr',
}) {
  const [majuscule, setMajuscule] = useState(false)
  const layout = LAYOUTS[langue] ?? LAYOUTS.fr

  const gererTouche = (touche) => {
    if (touche === '✓')      { onConfirm?.(); onFermer?.(); return }
    if (touche === '←')      { onChange(value.slice(0, -1)); return }
    if (touche === 'ESPACE') { onChange(value + ' '); return }
    if (touche === 'SHIFT')  { setMajuscule((m) => !m); return }
    // Caractères spéciaux (apostrophe, tiret, point, @) : pas de majuscule
    if (SPECIAUX.has(touche)) { onChange(value + touche); return }
    onChange(value + (majuscule ? touche.toUpperCase() : touche))
  }

  const getStyle = (touche) => {
    if (touche === '✓')      return W.confirm
    if (touche === '←')      return W.back
    if (touche === 'ESPACE') return W.espace
    if (touche === 'SHIFT')  return majuscule
      ? { ...W.fonction, background: 'rgba(0,180,216,0.3)', border: '1px solid #06b6d4', color: '#38bdf8' }
      : W.fonction
    if (SPECIAUX.has(touche)) return W.fonction
    return W.base
  }

  const getLabel = (touche) => {
    if (touche === 'SHIFT')  return '⇧'
    if (touche === 'ESPACE') return '⎵'
    if (majuscule && touche.length === 1 && !SPECIAUX.has(touche)) return touche.toUpperCase()
    return touche
  }

  const portail = (
    <>
      <div style={W.overlay} onPointerDown={() => onFermer?.()} />
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
    </>
  )

  return ReactDOM.createPortal(portail, document.body)
}
