import { useTranslation } from '../hooks/useTranslation'

const LANGUES = [
  { code: 'fr', label: 'FR', flag: '🇫🇷' },
  { code: 'en', label: 'EN', flag: '🇬🇧' },
  { code: 'ar', label: 'AR', flag: '🇸🇦' },
]

export default function SelecteurLangue() {
  const { langue, setLangue } = useTranslation()
  return (
    <div className="selecteur-langue" role="group" aria-label="Langue / Language">
      {LANGUES.map(({ code, label, flag }) => (
        <button
          key={code}
          className={`langue-btn${langue === code ? ' langue-btn--actif' : ''}`}
          onClick={() => setLangue(code)}
          aria-pressed={langue === code}
        >
          <span aria-hidden="true">{flag}</span> {label}
        </button>
      ))}
    </div>
  )
}
