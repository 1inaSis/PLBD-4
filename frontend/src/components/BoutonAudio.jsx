import { usePatient } from '../context/PatientContext'
import { useTranslation } from '../hooks/useTranslation'
import { useTextToSpeech } from '../hooks/useTextToSpeech'

export default function BoutonAudio() {
  const { audioActif, setAudioActif } = usePatient()
  const { t } = useTranslation()
  const { activer } = useTextToSpeech()

  const basculer = () => {
    if (audioActif) {
      if (window.speechSynthesis) window.speechSynthesis.cancel()
      setAudioActif(false)
    } else {
      activer()
      setAudioActif(true)
    }
  }

  return (
    <button
      className={`btn-audio-fixe${audioActif ? ' btn-audio-fixe--actif' : ''}`}
      onClick={basculer}
      title={audioActif ? t('tts_audio_desactiver') : t('tts_audio_activer')}
      aria-label={audioActif ? t('tts_audio_desactiver') : t('tts_audio_activer')}
      aria-pressed={audioActif}
    >
      {audioActif ? '🔊' : '🔇'}
    </button>
  )
}
