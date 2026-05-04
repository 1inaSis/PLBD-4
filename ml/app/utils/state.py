import time

# Stockage en mémoire partagé entre toutes les pages
patients_db = {}
compteur_patients = 1

def ajouter_patient(donnees: dict) -> str:
    global compteur_patients
    global patients_db
    pid = f"PT-{int(time.time())}-{compteur_patients}"
    compteur_patients += 1
    
    donnees["patient_id"] = pid
    donnees["heure_arrivee"] = time.strftime('%H:%M')
    donnees["timestamp_arrivee"] = time.time()
    donnees["temps_attente_min"] = 0
    donnees["esi_actuel"] = int(donnees.get("esi_predit", 3))
    
    # Assignation simple (M1 pour urgences paires ou ESI 1/2) -> on alternera.
    if "medecin_id" not in donnees:
        donnees["medecin_id"] = "m1" if (compteur_patients % 2 == 0) else "m2"
        
    patients_db[pid] = donnees
    return pid

def obtenir_file_attente() -> list:
    """Retourne la file triée par ESI puis par temps d'attente"""
    file = list(patients_db.values())
    maintenant = time.time()
    for p in file:
        p["temps_attente_min"] = int((maintenant - p["timestamp_arrivee"]) / 60)
        
    # Tri: ESI croissant (1=urg, 5=non urg), puis attente décroissante
    file.sort(key=lambda p: (p.get("esi_actuel", 3), -p.get("temps_attente_min", 0)))
    return file

def obtenir_patients_medecin(medecin_id: str) -> list:
    file = obtenir_file_attente()
    return [p for p in file if p.get("medecin_id") == medecin_id]

def obtenir_rapport(pid: str) -> dict:
    return patients_db.get(pid, {})

def calculer_attente_moyenne(file: list) -> int:
    if not file: return 0
    total = sum(p.get("temps_attente_min", 0) for p in file)
    return total // len(file)

def retirer_patient(pid: str):
    if pid in patients_db:
        del patients_db[pid]
