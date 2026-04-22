import { Link } from 'react-router-dom';

function AccueilPage() {
  return (
    <div style={{ 
      display: 'flex', alignItems: 'center', justifyContent: 'center', 
      minHeight: '100vh', backgroundColor: '#f0f4f8', fontFamily: 'sans-serif' 
    }}>
      <div style={{ 
        backgroundColor: 'white', padding: '50px', borderRadius: '20px', 
        textAlign: 'center', boxShadow: '0 4px 20px rgba(0,0,0,0.1)', maxWidth: '500px'
      }}>
        <h1 style={{ color: '#2c3e50' }}>🏥 Urgences Hospitalières</h1>
        <p style={{ color: '#64748b', marginBottom: '30px' }}>
          Bienvenue. Veuillez commencer votre évaluation pour réduire votre temps d'attente.
        </p>
        
        <Link to="/questionnaire">
          <button style={{ 
            padding: '20px 40px', fontSize: '1.2rem', cursor: 'pointer', 
            backgroundColor: '#007BFF', color: 'white', border: 'none', borderRadius: '12px' 
          }}>
            Commencer l'évaluation
          </button>
        </Link>
      </div>
    </div>
  );
}

export default AccueilPage;