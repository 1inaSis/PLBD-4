import { usePatient } from '../context/PatientContext'
import { TRANSLATIONS } from '../i18n/translations'

export function useTranslation() {
  const { langue, setLangue } = usePatient()
  const t = (key) => TRANSLATIONS[langue]?.[key] ?? TRANSLATIONS.fr[key] ?? key
  return { t, langue, setLangue }
}
