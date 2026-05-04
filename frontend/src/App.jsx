const stats = [
	{ label: 'Patients triages', value: '50k+' },
	{ label: 'Delai moyen', value: '< 2 min' },
	{ label: 'Niveau critique', value: 'ESI 1-2' },
]

const workflow = [
	'Scan de la carte d’identite',
	'Symptomes libres et constantes',
	'Prediction ESI et file priorisee',
]

function App() {
	return (
		<main className="app-shell">
			<section className="hero-card">
				<div className="hero-copy">
					<span className="eyebrow">HealthGate</span>
					<h1>Borne de triage medical intelligent.</h1>
					<p>
						Une interface frontale claire pour capturer les donnees patient,
						prioriser les urgences et garder la file visible en temps reel.
					</p>

					<div className="stats-grid">
						{stats.map((stat) => (
							<article key={stat.label} className="stat-card">
								<strong>{stat.value}</strong>
								<span>{stat.label}</span>
							</article>
						))}
					</div>
				</div>

				<aside className="panel-card">
					<div className="panel-header">
						<span className="status-dot" />
						Systeme actif
					</div>

					<div className="queue-preview">
						<div>
							<span className="queue-label">Patient courant</span>
							<strong>ESI 2 - Urgence</strong>
						</div>
						<div>
							<span className="queue-label">Medecin assigne</span>
							<strong>Dr. M1</strong>
						</div>
						<div>
							<span className="queue-label">Attente estimee</span>
							<strong>07 min</strong>
						</div>
					</div>
				</aside>
			</section>

			<section className="workflow-card">
				<h2>Pipeline de triage</h2>
				<div className="workflow-list">
					{workflow.map((step, index) => (
						<div key={step} className="workflow-step">
							<span>{index + 1}</span>
							<p>{step}</p>
						</div>
					))}
				</div>
			</section>
		</main>
	)
}

export default App
