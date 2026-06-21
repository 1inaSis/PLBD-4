import { usePatient } from '../context/PatientContext'
import { TRANSLATIONS } from '../i18n/translations'

export function useTranslation() {
  const { langue, setLangue } = usePatient()
  const t = (key, vars = {}) => {
    let str = TRANSLATIONS[langue]?.[key] ?? TRANSLATIONS.fr[key] ?? key
    const entries = Object.entries(vars)
    if (entries.length > 0) {
      entries.forEach(([k, v]) => { str = str.replace(`{${k}}`, String(v)) })
    }
    return str
  }
  return { t, langue, setLangue }
}
