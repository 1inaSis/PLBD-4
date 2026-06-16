// Pictogramme SVG interactif du corps humain — silhouette anatomique réaliste.
// IDs et labels des zones conservés intégralement pour compatibilité POST /api/symptomes.
// Nouvelle silhouette : paths bezier (torse, bras, jambes) + proportions anatomiques correctes.
// ViewBox élargi à 400×555.

// ── Couleurs dark-theme ────────────────────────────────────────────────────────
const B  = '#152238'          // remplissage corps
const BS = '#263f5e'          // contour corps
const D  = 'rgba(56,100,190,0.18)'  // décoration (sternum, clavicules, nombril)

// ── Zones interactives — IDs et labels INCHANGÉS ──────────────────────────────
export const ZONES = [
  { id: 'tete',          label: 'Tête / Visage',           cx: 200, cy: 56,  r: 34 },
  { id: 'cou',           label: 'Cou / Gorge',              cx: 200, cy: 117, r: 14 },
  { id: 'poitrine',      label: 'Poitrine / Cœur',          cx: 200, cy: 185, r: 44 },
  { id: 'ventre',        label: 'Ventre / Abdomen',         cx: 200, cy: 250, r: 36 },
  { id: 'bas_ventre',    label: 'Bas-ventre',                cx: 200, cy: 306, r: 24 },
  { id: 'epaule_gauche', label: 'Épaule gauche',            cx: 103, cy: 162, r: 22 },
  { id: 'epaule_droite', label: 'Épaule droite',            cx: 297, cy: 162, r: 22 },
  { id: 'bras_gauche',   label: 'Bras gauche',               cx: 76,  cy: 250, r: 20 },
  { id: 'bras_droit',    label: 'Bras droit',                cx: 324, cy: 250, r: 20 },
  { id: 'hanche_gauche', label: 'Hanche / Dos gauche',      cx: 145, cy: 310, r: 22 },
  { id: 'hanche_droite', label: 'Hanche / Dos droit',       cx: 255, cy: 310, r: 22 },
  { id: 'jambe_gauche',  label: 'Jambe gauche',              cx: 136, cy: 410, r: 22 },
  { id: 'jambe_droite',  label: 'Jambe droite',              cx: 264, cy: 410, r: 22 },
  { id: 'pied_gauche',   label: 'Pied / Cheville gauche',   cx: 134, cy: 494, r: 18 },
  { id: 'pied_droit',    label: 'Pied / Cheville droit',    cx: 266, cy: 494, r: 18 },
]

// Lookup rapide id → label (inchangé)
export const ZONES_MAP = Object.fromEntries(ZONES.map(z => [z.id, z.label]))

// ── Props ─────────────────────────────────────────────────────────────────────
// zonesSelectionnees : string[]  — IDs des zones actives
// onToggleZone       : (id) => void
export default function CorpsHumain({ zonesSelectionnees, onToggleZone }) {
  return (
    <div className="corps-humain-wrapper">
      <p className="corps-humain-consigne">
        Appuyez sur les zones douloureuses
        <br />
        <small>Sélection multiple autorisée</small>
      </p>

      <svg
        className="corps-humain-svg"
        viewBox="0 0 400 555"
        xmlns="http://www.w3.org/2000/svg"
        aria-label="Schéma du corps humain — sélectionner les zones douloureuses"
        role="group"
      >
        {/* ════════════════════════════════════════════════════════
            SILHOUETTE ANATOMIQUE (non-interactive, fond)
            Ordre de rendu : jambes → bras → torse → cou → tête
            (pour que les jointures se chevauchent proprement)
            ════════════════════════════════════════════════════════ */}

        {/* ── Jambe gauche (thigh + calf + pied) ─────────────── */}
        <path
          d="M 120 336
             C 106 355 100 392 100 430
             C 100 456 104 482 108 508
             Q 112 526 122 531
             Q 155 537 170 526
             Q 172 515 165 509
             C 150 499 148 473 150 450
             C 152 422 158 390 167 360
             Q 172 346 176 336 Z"
          fill={B} stroke={BS} strokeWidth="1.8"
        />

        {/* ── Jambe droite (miroir) ────────────────────────────── */}
        <path
          d="M 280 336
             C 294 355 300 392 300 430
             C 300 456 296 482 292 508
             Q 288 526 278 531
             Q 245 537 230 526
             Q 228 515 235 509
             C 250 499 252 473 250 450
             C 248 422 242 390 233 360
             Q 228 346 224 336 Z"
          fill={B} stroke={BS} strokeWidth="1.8"
        />

        {/* ── Bras gauche (épaule → main) ─────────────────────── */}
        <path
          d="M 94 150
             C 74 178 58 228 54 272
             C 52 296 54 318 58 336
             Q 62 350 70 355
             Q 82 358 86 351
             Q 88 340 90 325
             C 94 305 98 282 100 270
             C 108 228 118 178 112 150 Z"
          fill={B} stroke={BS} strokeWidth="1.8"
        />

        {/* ── Bras droit (miroir) ──────────────────────────────── */}
        <path
          d="M 306 150
             C 326 178 342 228 346 272
             C 348 296 346 318 342 336
             Q 338 350 330 355
             Q 318 358 314 351
             Q 312 340 310 325
             C 306 305 302 282 300 270
             C 292 228 282 178 288 150 Z"
          fill={B} stroke={BS} strokeWidth="1.8"
        />

        {/* ── Torse + hips (chest → abdomen → pelvis → crotch) ── */}
        <path
          d="M 184 130
             L 216 130
             C 258 126 302 130 316 158
             C 324 178 320 212 314 244
             C 308 265 280 276 264 295
             C 268 312 280 325 278 336
             L 226 336
             C 214 330 206 326 200 326
             C 194 326 186 330 174 336
             L 122 336
             C 120 325 132 312 136 295
             C 120 276 92 265 86 244
             C 80 212 76 178 84 158
             C 98 130 142 126 184 130 Z"
          fill={B} stroke={BS} strokeWidth="1.8"
        />

        {/* ── Cou ─────────────────────────────────────────────── */}
        <rect
          x="182" y="102" width="36" height="30" rx="10"
          fill={B} stroke={BS} strokeWidth="1.8"
        />

        {/* ── Tête ─────────────────────────────────────────────── */}
        <ellipse
          cx="200" cy="56" rx="40" ry="48"
          fill={B} stroke={BS} strokeWidth="2"
        />

        {/* ════════════════════════════════════════════════════════
            DÉCORATION ANATOMIQUE (non-interactive)
            ════════════════════════════════════════════════════════ */}

        {/* Ligne sternale (axe vertical du torse) */}
        <line
          x1="200" y1="138" x2="200" y2="274"
          stroke={D} strokeWidth="1.2" strokeDasharray="4 7"
          pointerEvents="none"
        />

        {/* Clavicule gauche */}
        <path
          d="M 198 140 C 168 140 135 146 112 160"
          fill="none" stroke={D} strokeWidth="1.4"
          pointerEvents="none"
        />

        {/* Clavicule droite */}
        <path
          d="M 202 140 C 232 140 265 146 288 160"
          fill="none" stroke={D} strokeWidth="1.4"
          pointerEvents="none"
        />

        {/* Nombril */}
        <circle
          cx="200" cy="272" r="4"
          fill={D} pointerEvents="none"
        />

        {/* ════════════════════════════════════════════════════════
            ZONES CLIQUABLES (superposées à la silhouette)
            ════════════════════════════════════════════════════════ */}
        {ZONES.map((zone) => {
          const actif = zonesSelectionnees.includes(zone.id)
          return (
            <g
              key={zone.id}
              onClick={() => onToggleZone(zone.id)}
              style={{ cursor: 'pointer' }}
              role="button"
              aria-label={zone.label}
              aria-pressed={actif}
            >
              <circle
                cx={zone.cx}
                cy={zone.cy}
                r={zone.r}
                fill={actif ? 'rgba(239,68,68,0.45)' : 'rgba(45,212,191,0.10)'}
                stroke={actif ? '#ef4444' : 'rgba(45,212,191,0.45)'}
                strokeWidth="2"
                style={{ transition: 'fill 0.18s, stroke 0.18s' }}
              />
              {actif && (
                <text
                  x={zone.cx}
                  y={zone.cy + 5}
                  textAnchor="middle"
                  fontSize="14"
                  fill="#fff"
                  fontWeight="700"
                  pointerEvents="none"
                >
                  ✓
                </text>
              )}
            </g>
          )
        })}
      </svg>

      {/* Légende */}
      <div className="corps-legende">
        <span className="corps-legende-item corps-legende-item--inactif">Zone disponible</span>
        <span className="corps-legende-item corps-legende-item--actif">Zone sélectionnée</span>
      </div>
    </div>
  )
}
