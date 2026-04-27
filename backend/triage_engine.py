class TriageEngine:
    REGLES = [
        # (condition, niveau, motif)
        # Niveau 1 — Rouge
        (lambda d: d['spo2'] < 90,                          1, "Détresse respiratoire — SpO2 critique"),
        (lambda d: d['temperature'] > 41.0,                 1, "Hyperthermie maligne"),
        (lambda d: d['frequence_cardiaque'] > 150,          1, "Tachycardie sévère"),
        (lambda d: d['frequence_cardiaque'] < 40,           1, "Bradycardie sévère"),
        (lambda d: d['tension_systolique'] < 80,            1, "Choc hypotensif"),
        (lambda d: d.get('dyspnea', 0) == 1 and d.get('dyspnea_aggrave_effort', 0) == 1, 1, "Détresse respiratoire aggravée à l'effort"),
        (lambda d: d.get('chest_pain', 0) == 1,             1, "Douleur thoracique aiguë"),
        # Niveau 2 — Orange
        (lambda d: d['spo2'] < 94,                          2, "Saturation insuffisante"),
        (lambda d: d['temperature'] >= 40.0,                2, "Fièvre très élevée"),
        (lambda d: d['douleur'] >= 8,                       2, "Douleur intense"),
        (lambda d: d['tension_systolique'] > 180,           2, "Hypertension sévère"),
        (lambda d: d['age'] < 3 and d['temperature'] > 38, 2, "Nourrisson fébrile"),
        (lambda d: d['age'] > 75 and (d.get('dyspnea', 0) == 1 or d['douleur'] >= 5), 2, "Patient âgé avec symptôme majeur"),
        # Niveau 3 — Jaune
        (lambda d: d['temperature'] >= 38.5,                3, "Fièvre modérée"),
        (lambda d: d['douleur'] >= 5,                       3, "Douleur modérée"),
        (lambda d: d['tension_systolique'] > 160,           3, "Hypertension modérée"),
        # Niveau 4 — Vert
        (lambda d: d['douleur'] >= 2,                       4, "Douleur légère"),
        (lambda d: d['temperature'] >= 37.5,                4, "Légère hyperthermie"),
    ]
    def evaluer(self, donnees_patient: dict) -> dict:
        d = self._normaliser(donnees_patient)
        for condition, niveau, motif in self.REGLES:
            try:
                if condition(d):
                    return {
                        "niveau": niveau,
                        "couleur": self._couleur(niveau),
                        "motif": motif,
                        "donnees_utilisees": d
                    }
            except KeyError:
                continue
        # Sécurité : si symptômes majeurs présents, ne jamais classer ESI 4
        if (
            d.get('dyspnea', False) or
            d.get('douleur', 0) >= 5 or
            d.get('spo2', 98) < 94
        ):
            return {
                "niveau": 3,
                "couleur": self._couleur(3),
                "motif": "Symptôme majeur sans critère d'urgence immédiate",
                "donnees_utilisees": d
            }
        return {"niveau": 5, "couleur": "BLEU", "motif": "Consultation standard"}
    def _normaliser(self, d: dict) -> dict:
        defaults = {
            'age': 30, 'temperature': 37.0, 'spo2': 98.0,
            'frequence_cardiaque': 75, 'douleur': 0,
            'tension_systolique': 120, 'tension_diastolique': 80
        }
        return {**defaults, **d}
    
    def _couleur(self, niveau: int) -> str:
        return {1: "ROUGE", 2: "ORANGE", 3: "JAUNE", 4: "VERT", 5: "BLEU"}[niveau]
    
    def degradation_temporelle(self, niveau: int, minutes_attente: int) -> int:
        """Remonte le niveau si le patient attend trop longtemps"""
        seuils = {3: 60, 4: 120, 5: 180}  # niveau: minutes max
        if niveau in seuils and minutes_attente > seuils[niveau]:
            return niveau - 1
        return niveau