import { useState, useCallback, useEffect, useRef } from 'react'
import { useVoiceInput } from '../hooks/useVoiceInput'
import { useTranslation } from '../hooks/useTranslation'
import ClavierAlpha from './ClavierAlpha'

export default function ZoneSaisieMixte({
  value       = '',
  onChange,
  langue      = 'fr',
  placeholder,
  rows        = 5,
}) {
  const { t } = useTranslation()
  const [clavierOuvert, setClavierOuvert]     = useState(false)
  const [texteModifiable, setTexteModifiable] = useState(false)
  const timerRef = useRef(null)

  // Déclenche le hint "modifiable" pendant 2s après une transcription finale
  const signalerModifiable = useCallback(() => {
    setTexteModifiable(true)
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => setTexteModifiable(false), 2000)
  }, [])

  useEffect(() => () => clearTimeout(timerRef.current), [])

  const { supporte, ecoute, erreurPermission, transcriptInterim, demarrer, arreter } =
    useVoiceInput({
      langue,
      onResult: (transcript) => {
        onChange((value ? value.trimEnd() + ' ' : '') + transcript)
        signalerModifiable()
      },
    })

  const gererMicro = useCallback(() => {
    if (ecoute) arreter()
    else         demarrer()
  }, [ecoute, demarrer, arreter])

  const ouvrir = useCallback(() => {
    if (ecoute) arreter()
    setClavierOuvert(true)
  }, [ecoute, arreter])

  // Classe de la zone : pulse vert 1s après transcription
  const classeZone = [
    'zsm-zone',
    texteModifiable && !ecoute ? 'zsm-zone--pret' : '',
  ].filter(Boolean).join(' ')

  return (
    <div className="zsm-wrapper">
      {/* Badge écoute en cours */}
      {ecoute && (
        <div className="zsm-ecoute-badge">
          🎙 {t('saisie_ecoute')}
        </div>
      )}

      {/* Hint discret "vous pouvez modifier" — 2s après transcription */}
      {texteModifiable && !ecoute && (
        <div className="zsm-modifiable-hint">
          ✓ {t('saisie_modifiable')}
        </div>
      )}

      {/* Zone d'affichage cliquable */}
      <div
        className={classeZone}
        role="textbox"
        aria-multiline="true"
        dir={langue === 'ar' ? 'rtl' : 'ltr'}
        onClick={ouvrir}
      >
        <span className="zsm-texte-final">{value}</span>
        {transcriptInterim && (
          <span className="zsm-texte-interim"> {transcriptInterim}</span>
        )}
        {!value && !transcriptInterim && (
          <span className="zsm-placeholder">
            {placeholder ?? t('saisie_placeholder')}
          </span>
        )}
      </div>

      {/* Barre d'actions */}
      <div className="zsm-actions">
        {supporte && !erreurPermission && window.isSecureContext && (
          <button
            className={`zsm-btn-parler${ecoute ? ' zsm-btn-parler--actif' : ''}`}
            onClick={gererMicro}
          >
            {ecoute ? '⏹' : '🎤'}
            <span>{ecoute ? t('saisie_stop') : t('saisie_parler')}</span>
          </button>
        )}

        <button className="zsm-btn-ecrire" onClick={ouvrir}>
          ✏️ <span>{t('saisie_ecrire')}</span>
        </button>

        {value && (
          <button className="zsm-btn-effacer" onClick={() => onChange('')}>
            ✕ <span>{t('saisie_effacer')}</span>
          </button>
        )}

        {erreurPermission && (
          <span className="zsm-micro-indispo">{erreurPermission}</span>
        )}
      </div>

      {clavierOuvert && (
        <ClavierAlpha
          value={value}
          onChange={onChange}
          onConfirm={() => setClavierOuvert(false)}
          onFermer={() => setClavierOuvert(false)}
          langue={langue}
        />
      )}
    </div>
  )
}
