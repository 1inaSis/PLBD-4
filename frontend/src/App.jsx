import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { PatientProvider } from './context/PatientContext'
import AccueilPage       from './pages/AccueilPage'
import QuestionnairePage from './pages/QuestionnairePage'
import ConstantesPage    from './pages/ConstantesPage'
import QuestionsPage     from './pages/QuestionsPage'
import ResultatPage      from './pages/ResultatPage'
import FileAttentePage   from './pages/FileAttentePage'
import SalleAttentePage  from './pages/SalleAttentePage'
import MedecinPage       from './pages/MedecinPage'

export default function App() {
  return (
    <PatientProvider>
      <BrowserRouter>
        <Routes>
          {/* Étape 1 — Identité */}
          <Route path="/"              element={<AccueilPage />} />

          {/* Étape 2 — Symptômes + pictogramme corps */}
          <Route path="/questionnaire" element={<QuestionnairePage />} />

          {/* Étape 3 — Constantes vitales (capteurs) */}
          <Route path="/constantes"    element={<ConstantesPage />} />

          {/* Étape 4 — Questions adaptatives IA */}
          <Route path="/questions"     element={<QuestionsPage />} />

          {/* Étape 5 — Résultat ESI + ticket */}
          <Route path="/resultat"      element={<ResultatPage />} />

          {/* Écran salle d'attente — grand affichage public */}
          <Route path="/salle"         element={<SalleAttentePage />} />

          {/* Ancienne route file d'attente (conservée) */}
          <Route path="/file-attente"  element={<FileAttentePage />} />

          {/* Interface médecin — dossiers patients assignés */}
          <Route path="/medecin/:id"   element={<MedecinPage />} />

          {/* Redirection fallback */}
          <Route path="*"              element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </PatientProvider>
  )
}
