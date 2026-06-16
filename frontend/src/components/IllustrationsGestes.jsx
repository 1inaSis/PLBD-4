// Pictogrammes SVG inline guidant le patient geste par geste.
// Palette cohérente avec le dark-theme kiosk.css :
//   #0d1929 fond profond · #152238 / #1e3a5f bleu-marine
//   #3b82f6 bleu clair   · #14b8a6 teal accent
//   #334155 / #263f5e    gris intermédiaires

// ── Étape 1 : Glisser la carte d'identité dans le scanner ─────────────────────
export function IllustrationScanCIN() {
  return (
    <svg viewBox="0 0 200 178" className="illustration-geste" aria-hidden="true">

      {/* ── Boîtier scanner ─────────────────────────────── */}
      <rect x="14" y="130" width="172" height="44" rx="11"
            fill="#0d1929" stroke="#1e3a5f" strokeWidth="1.5"/>
      <rect x="14" y="130" width="172" height="24" rx="11"
            fill="#152238" stroke="#1e3a5f" strokeWidth="1.5"/>
      {/* Fente de lecture */}
      <rect x="28" y="148" width="136" height="8" rx="4" fill="#060e1c"/>
      {/* Rayon laser — clignotement */}
      <line x1="30" y1="152" x2="166" y2="152"
            stroke="#14b8a6" strokeWidth="2.5" strokeLinecap="round">
        <animate attributeName="opacity" values="1;0.1;1" dur="1.5s" repeatCount="indefinite"/>
      </line>
      {/* LED d'état */}
      <circle cx="174" cy="146" r="4.5" fill="#14b8a6">
        <animate attributeName="opacity" values="1;0.2;1" dur="1.5s" repeatCount="indefinite"/>
      </circle>

      {/* ── Carte CIN ───────────────────────────────────── */}
      <rect x="40" y="18" width="120" height="82" rx="7"
            fill="#152238" stroke="#3b82f6" strokeWidth="1.5"/>
      {/* Bande couleur supérieure */}
      <rect x="40" y="18" width="120" height="15" rx="7" fill="#1e3a5f"/>
      <rect x="40" y="26" width="120" height="7" fill="#1e3a5f"/>
      {/* Zone photo */}
      <rect x="50" y="39" width="30" height="38" rx="3"
            fill="#0d1929" stroke="#263f5e" strokeWidth="1"/>
      <circle cx="65" cy="50" r="8" fill="#1e3a5f"/>
      <path d="M50 77 Q65 70 80 77" fill="#1e3a5f"/>
      {/* Lignes de texte simulées */}
      <rect x="88" y="40" width="56" height="5" rx="2" fill="#1e3a5f"/>
      <rect x="88" y="50" width="40" height="4" rx="2" fill="#0d1929" stroke="#1e3a5f" strokeWidth="0.5"/>
      <rect x="88" y="59" width="48" height="4" rx="2" fill="#0d1929" stroke="#1e3a5f" strokeWidth="0.5"/>
      <rect x="88" y="68" width="33" height="4" rx="2" fill="#0d1929" stroke="#1e3a5f" strokeWidth="0.5"/>
      {/* Bande MRZ */}
      <rect x="50" y="86" width="100" height="3.5" rx="1"
            fill="#0d1929" stroke="#1e3a5f" strokeWidth="0.4"/>
      <rect x="50" y="93" width="100" height="3.5" rx="1"
            fill="#0d1929" stroke="#1e3a5f" strokeWidth="0.4"/>

      {/* ── Flèche "glissez vers le bas" ────────────────── */}
      <path d="M100 106 L100 124"
            stroke="#14b8a6" strokeWidth="2.5" strokeLinecap="round"/>
      <path d="M93 118 L100 127 L107 118"
            fill="none" stroke="#14b8a6" strokeWidth="2.5"
            strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

// ── Étape 3-A : Thermomètre infrarouge sur le front ───────────────────────────
export function IllustrationThermometre() {
  return (
    <svg viewBox="0 0 210 168" className="illustration-geste" aria-hidden="true">

      {/* ── Visage (vue de face, simplifié) ─────────────── */}
      <ellipse cx="68" cy="82" rx="42" ry="48"
               fill="#1e293b" stroke="#334155" strokeWidth="1.5"/>
      {/* Cheveux */}
      <ellipse cx="68" cy="37" rx="40" ry="14" fill="#1e3a5f"/>
      {/* Yeux */}
      <ellipse cx="55" cy="76" rx="6" ry="7" fill="#0d1929"/>
      <ellipse cx="81" cy="76" rx="6" ry="7" fill="#0d1929"/>
      <circle cx="56" cy="75" r="2.2" fill="#3b82f6" opacity="0.75"/>
      <circle cx="82" cy="75" r="2.2" fill="#3b82f6" opacity="0.75"/>
      {/* Nez */}
      <path d="M68 87 Q64 96 62 99 Q68 102 74 99 Q72 96 68 87 Z"
            fill="#152238" stroke="#334155" strokeWidth="0.8"/>
      {/* Bouche */}
      <path d="M60 112 Q68 119 76 112"
            fill="none" stroke="#475569" strokeWidth="1.5" strokeLinecap="round"/>
      {/* Cible sur le front */}
      <circle cx="68" cy="57" r="7"
              fill="none" stroke="#ef4444" strokeWidth="1.5" strokeDasharray="3 2" opacity="0.8">
        <animate attributeName="opacity" values="0.8;0.25;0.8" dur="1.4s" repeatCount="indefinite"/>
      </circle>
      <circle cx="68" cy="57" r="2.2" fill="#ef4444" opacity="0.55">
        <animate attributeName="opacity" values="0.55;0.1;0.55" dur="1.4s" repeatCount="indefinite"/>
      </circle>

      {/* ── Thermomètre IR (pistolet) ────────────────────── */}
      {/* Canon */}
      <rect x="128" y="44" width="56" height="28" rx="7"
            fill="#152238" stroke="#3b82f6" strokeWidth="1.5"/>
      {/* Poignée */}
      <rect x="142" y="70" width="24" height="42" rx="7"
            fill="#1e3a5f" stroke="#3b82f6" strokeWidth="1.5"/>
      {/* Lentille émettrice (côté gauche) */}
      <circle cx="133" cy="58" r="9" fill="#0d1929" stroke="#14b8a6" strokeWidth="1.5"/>
      <circle cx="133" cy="58" r="4.5" fill="#14b8a6" opacity="0.30">
        <animate attributeName="opacity" values="0.30;0.08;0.30" dur="1.4s" repeatCount="indefinite"/>
      </circle>
      {/* Écran */}
      <rect x="150" y="50" width="26" height="14" rx="3" fill="#060e1c"/>
      <text x="163" y="61" textAnchor="middle"
            fill="#14b8a6" fontSize="9" fontFamily="monospace">36.8°</text>
      {/* Gâchette */}
      <rect x="148" y="68" width="10" height="6" rx="3"
            fill="#263f5e" stroke="#3b82f6" strokeWidth="0.8"/>

      {/* ── Faisceaux IR (pointillés) ────────────────────── */}
      <line x1="124" y1="53" x2="110" y2="56"
            stroke="#14b8a6" strokeWidth="1.2" strokeDasharray="4 3" opacity="0.9"/>
      <line x1="124" y1="58" x2="108" y2="58"
            stroke="#14b8a6" strokeWidth="1.2" strokeDasharray="4 3" opacity="0.7"/>
      <line x1="124" y1="63" x2="110" y2="60"
            stroke="#14b8a6" strokeWidth="1.2" strokeDasharray="4 3" opacity="0.5"/>
    </svg>
  )
}

// ── Étape 3-B : Doigt sur le capteur MAX30105 — SpO₂ ─────────────────────────
// Le capteur MAX30105 mesure SpO₂ ET fréquence cardiaque via le même geste.
export function IllustrationSpo2() {
  return (
    <svg viewBox="0 0 210 174" className="illustration-geste" aria-hidden="true">

      {/* ── Main ────────────────────────────────────────── */}
      {/* Paume */}
      <path d="M60 174 L60 96 Q60 84 72 83 L128 83 Q140 84 140 96 L140 174 Z"
            fill="#1e293b" stroke="#334155" strokeWidth="1.5"/>
      {/* Index (pointé vers le haut) */}
      <rect x="88" y="32" width="24" height="57" rx="12"
            fill="#1e293b" stroke="#334155" strokeWidth="1.5"/>
      <ellipse cx="100" cy="32" rx="12" ry="11"
               fill="#1e293b" stroke="#334155" strokeWidth="1.5"/>
      {/* Ongle */}
      <rect x="92" y="22" width="16" height="20" rx="6"
            fill="#152238" stroke="#263f5e" strokeWidth="0.8"/>
      {/* Doigts latéraux */}
      <rect x="63" y="81" width="20" height="28" rx="10"
            fill="#152238" stroke="#263f5e" strokeWidth="1"/>
      <rect x="117" y="78" width="20" height="30" rx="10"
            fill="#152238" stroke="#263f5e" strokeWidth="1"/>

      {/* ── Pince capteur MAX30105 ───────────────────────── */}
      {/* Partie haute (LED rouge) */}
      <rect x="81" y="18" width="38" height="20" rx="7"
            fill="#1e3a5f" stroke="#3b82f6" strokeWidth="1.5"/>
      {/* Partie basse (photorécepteur) */}
      <rect x="81" y="46" width="38" height="20" rx="7"
            fill="#1e3a5f" stroke="#3b82f6" strokeWidth="1.5"/>
      {/* LED rouge — clignote */}
      <circle cx="100" cy="28" r="5" fill="#ef4444">
        <animate attributeName="opacity" values="1;0.2;1" dur="1.1s" repeatCount="indefinite"/>
      </circle>
      {/* Photorécepteur */}
      <circle cx="100" cy="56" r="5" fill="#14b8a6" opacity="0.7">
        <animate attributeName="opacity" values="0.7;0.2;0.7" dur="1.1s" repeatCount="indefinite"/>
      </circle>
      {/* Charnière */}
      <rect x="119" y="32" width="8" height="10" rx="3"
            fill="#152238" stroke="#3b82f6" strokeWidth="1"/>

      {/* ── Bulle résultat SpO₂ ──────────────────────────── */}
      <rect x="148" y="20" width="52" height="36" rx="9"
            fill="#0d1929" stroke="#3b82f6" strokeWidth="1"/>
      <text x="174" y="35" textAnchor="middle"
            fill="#14b8a6" fontSize="8" fontFamily="monospace">SpO₂</text>
      <text x="174" y="51" textAnchor="middle"
            fill="#f1f5f9" fontSize="14" fontWeight="bold" fontFamily="monospace">98 %</text>
      <line x1="148" y1="38" x2="128" y2="38"
            stroke="#1e3a5f" strokeWidth="1" strokeDasharray="3 2"/>
    </svg>
  )
}

// ── Étape 3-C : Doigt sur le capteur MAX30105 — Fréquence cardiaque ───────────
export function IllustrationFreqCardiaque() {
  return (
    <svg viewBox="0 0 210 174" className="illustration-geste" aria-hidden="true">

      {/* ── Main (identique à SpO₂) ─────────────────────── */}
      <path d="M60 174 L60 96 Q60 84 72 83 L128 83 Q140 84 140 96 L140 174 Z"
            fill="#1e293b" stroke="#334155" strokeWidth="1.5"/>
      <rect x="88" y="32" width="24" height="57" rx="12"
            fill="#1e293b" stroke="#334155" strokeWidth="1.5"/>
      <ellipse cx="100" cy="32" rx="12" ry="11"
               fill="#1e293b" stroke="#334155" strokeWidth="1.5"/>
      <rect x="92" y="22" width="16" height="20" rx="6"
            fill="#152238" stroke="#263f5e" strokeWidth="0.8"/>
      <rect x="63" y="81" width="20" height="28" rx="10"
            fill="#152238" stroke="#263f5e" strokeWidth="1"/>
      <rect x="117" y="78" width="20" height="30" rx="10"
            fill="#152238" stroke="#263f5e" strokeWidth="1"/>

      {/* ── Pince capteur MAX30105 ───────────────────────── */}
      <rect x="81" y="18" width="38" height="20" rx="7"
            fill="#1e3a5f" stroke="#3b82f6" strokeWidth="1.5"/>
      <rect x="81" y="46" width="38" height="20" rx="7"
            fill="#1e3a5f" stroke="#3b82f6" strokeWidth="1.5"/>
      {/* LED rouge — clignote au rythme cardiaque */}
      <circle cx="100" cy="28" r="5" fill="#ef4444">
        <animate attributeName="opacity" values="1;0.05;1;0.05;1" dur="0.85s" repeatCount="indefinite"/>
      </circle>
      <circle cx="100" cy="56" r="5" fill="#14b8a6" opacity="0.6"/>
      <rect x="119" y="32" width="8" height="10" rx="3"
            fill="#152238" stroke="#3b82f6" strokeWidth="1"/>

      {/* ── Courbe ECG ───────────────────────────────────── */}
      <polyline
        points="142,52 152,52 156,34 161,68 166,40 171,52 182,52"
        fill="none" stroke="#ef4444" strokeWidth="2.2"
        strokeLinecap="round" strokeLinejoin="round">
        <animate attributeName="opacity" values="1;0.25;1" dur="0.85s" repeatCount="indefinite"/>
      </polyline>

      {/* ── Bulle BPM ────────────────────────────────────── */}
      <rect x="148" y="60" width="54" height="26" rx="8"
            fill="#0d1929" stroke="#ef4444" strokeWidth="1"/>
      <text x="175" y="77" textAnchor="middle"
            fill="#ef4444" fontSize="12" fontWeight="bold" fontFamily="monospace">72 bpm</text>
    </svg>
  )
}

// ── Étape 3-D : Brassard de tension artérielle sur le bras ────────────────────
export function IllustrationTension() {
  return (
    <svg viewBox="0 0 210 172" className="illustration-geste" aria-hidden="true">

      {/* ── Bras gauche ──────────────────────────────────── */}
      <path d="M58 16 Q52 88 54 146 Q62 160 82 160 Q102 160 110 146 Q112 88 102 16 Q92 6 80 8 Q68 6 58 16 Z"
            fill="#1e293b" stroke="#334155" strokeWidth="1.5"/>
      {/* Ombrage bras */}
      <path d="M74 18 Q70 88 72 146"
            stroke="#152238" strokeWidth="4" fill="none" opacity="0.45"/>

      {/* ── Brassard gonflable ───────────────────────────── */}
      <path d="M40 60 Q40 52 50 50 L110 50 Q120 52 120 60 L120 108 Q120 116 110 118 L50 118 Q40 116 40 108 Z"
            fill="#1e3a5f" stroke="#3b82f6" strokeWidth="1.5"/>
      {/* Stries textile */}
      {[0,1,2,3,4,5,6].map(i => (
        <line key={i}
              x1={50 + i * 10} y1="54" x2={50 + i * 10} y2="114"
              stroke="#152238" strokeWidth="1" opacity="0.30"/>
      ))}
      {/* Bords velcro */}
      <path d="M40 60 Q40 52 50 50" stroke="#475569" strokeWidth="2.5" fill="none" strokeLinecap="round"/>
      <path d="M110 50 Q120 52 120 60" stroke="#475569" strokeWidth="2.5" fill="none" strokeLinecap="round"/>

      {/* ── Tuyau reliant au manomètre ───────────────────── */}
      <path d="M80 50 Q80 32 97 26 Q112 20 122 28"
            fill="none" stroke="#475569" strokeWidth="3" strokeLinecap="round"/>

      {/* ── Afficheur numérique ──────────────────────────── */}
      <rect x="120" y="12" width="68" height="50" rx="9"
            fill="#0d1929" stroke="#3b82f6" strokeWidth="1.5"/>
      <rect x="127" y="18" width="54" height="38" rx="5" fill="#060e1c"/>
      <text x="154" y="34" textAnchor="middle"
            fill="#14b8a6" fontSize="15" fontWeight="bold" fontFamily="monospace">120</text>
      <text x="154" y="50" textAnchor="middle"
            fill="#475569" fontSize="9" fontFamily="monospace">/ 80 mmHg</text>

      {/* ── Flèche indicative ────────────────────────────── */}
      <path d="M42 128 Q30 140 34 154"
            fill="none" stroke="#14b8a6" strokeWidth="1.8"
            strokeDasharray="4 3" strokeLinecap="round" opacity="0.7"/>
      <circle cx="34" cy="156" r="3.5" fill="#14b8a6" opacity="0.7"/>
    </svg>
  )
}
