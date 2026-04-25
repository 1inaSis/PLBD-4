"""
queue_manager.py — Gestionnaire de file d'attente dynamique APQ-h pour HealthGate
Projet HealthGate | Centrale Casablanca | PLBD 4 | 2025-2026

Algorithme APQ-h (Adaptive Priority Queue - health) :
- Priorité initiale basée sur le niveau ESI
- Score dynamique qui évolue avec le temps d'attente
- Dégradation clinique détectée automatiquement
- Bonus de vulnérabilité pour les très jeunes et très âgés
- Alertes automatiques si seuil critique dépassé
"""

import threading
import time
from datetime import datetime
from typing import Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Configuration de l'algorithme APQ-h
# ─────────────────────────────────────────────────────────────────────────────

# Score de priorité de base par niveau ESI (plus le score est élevé = plus urgent)
SCORE_BASE_PAR_ESI = {
    1: 100,   # Critique : traitement immédiat
    2: 80,    # Urgent
    3: 60,    # Semi-urgent
    4: 30,    # Non urgent
    5: 10,    # Sans urgence
}

# Accumulation du score par minute d'attente (par niveau ESI)
ACCUMULATION_PAR_MINUTE = {
    1: 5.0,   # Critique : monte très vite (ne devrait pas attendre)
    2: 3.0,
    3: 1.5,
    4: 0.8,
    5: 0.4,
}

# Seuil d'alerte : si score dépasse ce seuil → alerte infirmier
SEUIL_ALERTE = {
    1: 100,   # Alerte immédiate dès l'arrivée
    2: 90,
    3: 80,
    4: 70,
    5: 60,
}

# Bonus de vulnérabilité (âge < 5 ans ou > 70 ans)
BONUS_VULNERABILITE = 15

# Intervalle de mise à jour de la file (en secondes)
INTERVALLE_MISE_A_JOUR = 60  # toutes les minutes en production


class PatientEnFile:
    """Représente un patient dans la file d'attente dynamique."""

    def __init__(
        self,
        patient_id: str,
        esi_predit: int,
        age: int,
        constantes: dict,
        heure_arrivee: Optional[datetime] = None,
    ):
        self.patient_id    = patient_id
        self.esi_predit    = esi_predit
        self.esi_actuel    = esi_predit   # peut changer si dégradation
        self.age           = age
        self.constantes    = constantes.copy()
        self.heure_arrivee = heure_arrivee or datetime.now()
        self.alerte_active = False
        self.alerte_lue    = False
        self.historique_scores: List[dict] = []

        # Calcul du score initial
        self.score         = self._calculer_score_initial()
        # Vérifier alerte dès l'arrivée (ESI 1 et 2 peuvent être immédiatement critiques)
        self._verifier_alerte()

    # ─────────────────────────────────────────────────────────────────────────
    # Calcul du score de priorité
    # ─────────────────────────────────────────────────────────────────────────

    def _calculer_score_initial(self) -> float:
        """Score de priorité à l'arrivée du patient."""
        score = float(SCORE_BASE_PAR_ESI[self.esi_actuel])
        score += self._bonus_vulnerabilite()
        self._enregistrer_historique(score, "arrivée")
        return score

    def _bonus_vulnerabilite(self) -> float:
        """Retourne un bonus si le patient est vulnérable (âge < 5 ou > 70)."""
        if self.age < 5 or self.age > 70:
            return BONUS_VULNERABILITE
        return 0.0

    def temps_attente_minutes(self) -> float:
        """Calcule le temps d'attente actuel en minutes."""
        delta = datetime.now() - self.heure_arrivee
        return delta.total_seconds() / 60.0

    def recalculer_score(self) -> float:
        """
        Recalcule le score dynamique :
        score = score_base + accumulation_temps + bonus_vulnerabilite
        """
        score_base   = float(SCORE_BASE_PAR_ESI[self.esi_actuel])
        attente      = self.temps_attente_minutes()
        accumulation = attente * ACCUMULATION_PAR_MINUTE[self.esi_actuel]
        vulnerabilite = self._bonus_vulnerabilite()

        self.score = score_base + accumulation + vulnerabilite
        self._verifier_alerte()
        self._enregistrer_historique(self.score, "mise à jour")

        return self.score

    def signaler_degradation(self, nouvelles_constantes: dict, nouvel_esi: int) -> None:
        """
        Signale une dégradation clinique : met à jour les constantes et l'ESI.
        Le score monte brusquement au niveau ESI critique.
        """
        ancien_esi      = self.esi_actuel
        self.esi_actuel = nouvel_esi
        self.constantes = nouvelles_constantes.copy()

        # Recalcul immédiat avec bonus de dégradation
        score_base    = float(SCORE_BASE_PAR_ESI[nouvel_esi])
        bonus_degrad  = 20.0  # bonus supplémentaire pour urgence soudaine
        vulnerabilite = self._bonus_vulnerabilite()
        self.score    = score_base + bonus_degrad + vulnerabilite

        self._verifier_alerte()
        self._enregistrer_historique(
            self.score,
            f"dégradation ESI {ancien_esi} → ESI {nouvel_esi}"
        )

    def _verifier_alerte(self) -> None:
        """Déclenche une alerte si le score dépasse le seuil critique."""
        if self.score >= SEUIL_ALERTE[self.esi_actuel] and not self.alerte_active:
            self.alerte_active = True
            self.alerte_lue    = False
            print(f"[🚨 ALERTE] Patient {self.patient_id} | "
                  f"ESI {self.esi_actuel} | Score {self.score:.1f} | "
                  f"Attente : {self.temps_attente_minutes():.0f} min")

    def _enregistrer_historique(self, score: float, evenement: str) -> None:
        """Enregistre l'historique des scores pour la traçabilité."""
        self.historique_scores.append({
            "horodatage": datetime.now().isoformat(),
            "score":      round(score, 2),
            "esi":        self.esi_actuel,
            "evenement":  evenement,
        })

    def to_dict(self) -> dict:
        """Sérialise le patient pour l'API Flask."""
        return {
            "patient_id":        self.patient_id,
            "esi_predit":        self.esi_predit,
            "esi_actuel":        self.esi_actuel,
            "age":               self.age,
            "score_priorite":    round(self.score, 2),
            "temps_attente_min": round(self.temps_attente_minutes(), 1),
            "alerte_active":     self.alerte_active,
            "heure_arrivee":     self.heure_arrivee.strftime("%H:%M"),
            "constantes":        self.constantes,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Gestionnaire de la file d'attente
# ─────────────────────────────────────────────────────────────────────────────

class GestionnaireFile:
    """
    Gestionnaire de la file d'attente dynamique APQ-h.
    Thread-safe pour utilisation concurrente avec l'API Flask.
    """

    def __init__(self):
        self.file: Dict[str, PatientEnFile] = {}
        self._verrou = threading.Lock()
        self._thread_actif = False

    # ─────────────────────────────────────────────────────────────────────────
    # Opérations sur la file
    # ─────────────────────────────────────────────────────────────────────────

    def ajouter_patient(
        self,
        patient_id: str,
        esi_predit: int,
        age: int,
        constantes: dict,
        heure_arrivee: Optional[datetime] = None,
    ) -> PatientEnFile:
        """Ajoute un nouveau patient dans la file d'attente."""
        with self._verrou:
            patient = PatientEnFile(
                patient_id=patient_id,
                esi_predit=esi_predit,
                age=age,
                constantes=constantes,
                heure_arrivee=heure_arrivee,
            )
            self.file[patient_id] = patient
            print(f"[+] Patient ajouté : {patient_id} | ESI {esi_predit} | "
                  f"Score initial : {patient.score:.1f}")
            return patient

    def retirer_patient(self, patient_id: str) -> Optional[PatientEnFile]:
        """Retire un patient de la file (après prise en charge)."""
        with self._verrou:
            patient = self.file.pop(patient_id, None)
            if patient:
                print(f"[-] Patient retiré : {patient_id} | "
                      f"Attente totale : {patient.temps_attente_minutes():.0f} min")
            return patient

    def signaler_degradation(
        self,
        patient_id: str,
        nouvelles_constantes: dict,
        nouvel_esi: int,
    ) -> bool:
        """Signale une dégradation clinique pour un patient dans la file."""
        with self._verrou:
            if patient_id not in self.file:
                return False
            self.file[patient_id].signaler_degradation(nouvelles_constantes, nouvel_esi)
            return True

    def get_file_triee(self) -> List[PatientEnFile]:
        """Retourne la liste des patients triée par score décroissant."""
        with self._verrou:
            return sorted(
                self.file.values(),
                key=lambda p: p.score,
                reverse=True
            )

    def get_position_patient(self, patient_id: str) -> Optional[int]:
        """Retourne la position d'un patient dans la file (1 = premier à être vu)."""
        file_triee = self.get_file_triee()
        for i, patient in enumerate(file_triee, start=1):
            if patient.patient_id == patient_id:
                return i
        return None

    def get_alertes_actives(self) -> List[PatientEnFile]:
        """Retourne la liste des patients avec alerte active non lue."""
        with self._verrou:
            return [p for p in self.file.values()
                    if p.alerte_active and not p.alerte_lue]

    def marquer_alerte_lue(self, patient_id: str) -> bool:
        """Marque l'alerte d'un patient comme lue."""
        with self._verrou:
            if patient_id in self.file:
                self.file[patient_id].alerte_lue = True
                return True
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # Mise à jour automatique des scores (thread en arrière-plan)
    # ─────────────────────────────────────────────────────────────────────────

    def _boucle_mise_a_jour(self, intervalle: int) -> None:
        """Boucle de mise à jour des scores toutes les `intervalle` secondes."""
        while self._thread_actif:
            time.sleep(intervalle)
            with self._verrou:
                for patient in self.file.values():
                    patient.recalculer_score()

    def demarrer_mise_a_jour_auto(self, intervalle: int = INTERVALLE_MISE_A_JOUR) -> None:
        """Démarre le thread de mise à jour automatique des scores."""
        if not self._thread_actif:
            self._thread_actif = True
            thread = threading.Thread(
                target=self._boucle_mise_a_jour,
                args=(intervalle,),
                daemon=True   # se termine avec le processus principal
            )
            thread.start()
            print(f"[INFO] Mise à jour automatique activée (intervalle : {intervalle}s)")

    def arreter_mise_a_jour_auto(self) -> None:
        """Arrête le thread de mise à jour automatique."""
        self._thread_actif = False

    # ─────────────────────────────────────────────────────────────────────────
    # État de la file pour l'API Flask
    # ─────────────────────────────────────────────────────────────────────────

    def etat_file(self) -> dict:
        """Retourne l'état complet de la file sous forme de dictionnaire."""
        file_triee = self.get_file_triee()
        alertes    = self.get_alertes_actives()

        return {
            "horodatage":      datetime.now().isoformat(),
            "nb_patients":     len(file_triee),
            "nb_alertes":      len(alertes),
            "file_attente":    [
                {**p.to_dict(), "position": i + 1}
                for i, p in enumerate(file_triee)
            ],
            "alertes_actives": [p.to_dict() for p in alertes],
        }

    def afficher_file(self) -> None:
        """Affiche la file d'attente dans le terminal (pour le débogage)."""
        file_triee = self.get_file_triee()
        print("\n" + "=" * 65)
        print(f"FILE D'ATTENTE APQ-h — {datetime.now().strftime('%H:%M:%S')}")
        print(f"Patients en attente : {len(file_triee)}")
        print("=" * 65)
        print(f"{'Pos':<4} {'ID':<10} {'ESI':<5} {'Score':<8} "
              f"{'Attente':<10} {'Age':<5} {'Alerte'}")
        print("-" * 65)
        for i, patient in enumerate(file_triee, start=1):
            alerte = "🚨" if patient.alerte_active and not patient.alerte_lue else "  "
            print(f"{i:<4} {patient.patient_id:<10} "
                  f"ESI {patient.esi_actuel:<3} "
                  f"{patient.score:<8.1f} "
                  f"{patient.temps_attente_minutes():<10.1f} "
                  f"{patient.age:<5} "
                  f"{alerte}")
        print("=" * 65)


# ─────────────────────────────────────────────────────────────────────────────
# Instance globale de la file (partagée avec l'API Flask)
# ─────────────────────────────────────────────────────────────────────────────
gestionnaire_file = GestionnaireFile()


# ─────────────────────────────────────────────────────────────────────────────
# Démonstration en ligne de commande
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 65)
    print("DÉMONSTRATION DE LA FILE D'ATTENTE APQ-h — HealthGate")
    print("=" * 65)

    file = GestionnaireFile()

    # Simulation d'arrivées
    from datetime import timedelta

    patients_test = [
        ("PT001", 3, 35, {"spo2": 95, "heart_rate": 88}, 45),   # arrive il y a 45 min
        ("PT002", 2, 72, {"spo2": 91, "heart_rate": 115}, 20),  # arrive il y a 20 min (vulnérable)
        ("PT003", 4, 25, {"spo2": 98, "heart_rate": 75}, 10),   # arrive il y a 10 min
        ("PT004", 3, 3,  {"spo2": 94, "heart_rate": 100}, 30),  # enfant de 3 ans (vulnérable)
        ("PT005", 1, 58, {"spo2": 82, "heart_rate": 145}, 0),   # vient d'arriver
    ]

    for pid, esi, age, constantes, minutes_passes in patients_test:
        heure = datetime.now() - timedelta(minutes=minutes_passes)
        file.ajouter_patient(pid, esi, age, constantes, heure)

    print("\n[ÉTAT INITIAL DE LA FILE]")
    file.afficher_file()

    # Simulation dégradation du patient PT003
    print("\n[SIMULATION] Dégradation du patient PT003 : ESI 4 → ESI 2")
    file.signaler_degradation(
        "PT003",
        nouvelles_constantes={"spo2": 89, "heart_rate": 130},
        nouvel_esi=2
    )
    file.afficher_file()

    # Retrait d'un patient pris en charge
    print("\n[SIMULATION] Prise en charge du patient PT005 (ESI 1)")
    file.retirer_patient("PT005")
    file.afficher_file()

    # Positions
    for pid, *_ in patients_test[:-1]:
        pos = file.get_position_patient(pid)
        if pos:
            print(f"  {pid} → position {pos} dans la file")
