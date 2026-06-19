import { useTranslation } from '../hooks/useTranslation'

export default function ModalInactivite({ avertissement, compte, onContinuer }) {
  const { t } = useTranslation()
  if (!avertissement) return null
  return (
    <div className="inactivite-overlay" role="alertdialog" aria-modal="true">
      <div className="inactivite-modal">
        <span className="inactivite-icone" aria-hidden="true">⏱</span>
        <h2 className="inactivite-titre">{t('inact_titre')}</h2>
        <p className="inactivite-msg">
          {t('inact_msg')}{' '}
          <strong className="inactivite-compte">{compte}</strong>{' '}
          {t('inact_secondes')}
        </p>
        <button className="kiosk-btn kiosk-btn--primary inactivite-btn" onClick={onContinuer}>
          {t('inact_continuer')}
        </button>
      </div>
    </div>
  )
}
