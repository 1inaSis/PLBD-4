import { useTranslation } from '../hooks/useTranslation'

const GUIDES = {
  '1':         (t) => ({ icone: '📋', texte: t('guide1') }),
  '2':         (t) => ({ icone: '👆', texte: t('guide2') }),
  '3_temp':    (t) => ({ icone: '🌡️', texte: t('guide3_temp') }),
  '3_spo2':    (t) => ({ icone: '👆', texte: t('guide3_spo2') }),
  '3_tension': (t) => ({ icone: '💪', texte: t('guide3_tension') }),
  '4':         (t) => ({ icone: '💬', texte: t('guide4') }),
  '5':         (t) => ({ icone: '✅', texte: t('guide5') }),
}

export default function GuideEtape({ etape, sousEtape }) {
  const { t } = useTranslation()
  const cle = sousEtape ? `${etape}_${sousEtape}` : `${etape}`
  const guide = (GUIDES[cle] ?? GUIDES[`${etape}`])?.(t)
  if (!guide) return null
  return (
    <div className="guide-etape" role="status" aria-live="polite">
      <span className="guide-icone" aria-hidden="true">{guide.icone}</span>
      <span className="guide-texte">{guide.texte}</span>
    </div>
  )
}
