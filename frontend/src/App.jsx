import { BrowserRouter, Routes, Route } from 'react-router-dom';
import AccueilPage from './pages/AccueilPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AccueilPage />} />
        {/* On ajoutera la route du questionnaire ici juste après */}
      </Routes>
    </BrowserRouter>
  );
}

export default App;