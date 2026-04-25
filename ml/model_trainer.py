"""
model_trainer.py — Entraînement du modèle Random Forest pour HealthGate
Projet HealthGate | Centrale Casablanca | PLBD 4 | 2025-2026

Pipeline complet :
1. Chargement et préparation des données patients
2. Enrichissement NLP (symptom_text → features binaires)
3. Entraînement d'un Random Forest pour prédire le niveau ESI (1 à 5)
4. Évaluation complète (accuracy, rapport de classification, matrice de confusion)
5. Sauvegarde du modèle (.pkl) pour utilisation par l'API Flask
"""

import os
import pickle
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
)
from nlp_extractor import enrichir_dataframe

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CHEMIN_DATA     = os.path.join(BASE_DIR, "data", "patients_50000.csv")
CHEMIN_MODELE   = os.path.join(BASE_DIR, "models", "random_forest_esi.pkl")
CHEMIN_SCALER   = os.path.join(BASE_DIR, "models", "scaler.pkl")
CHEMIN_FEATURES = os.path.join(BASE_DIR, "models", "feature_names.pkl")

# Colonnes de features utilisées pour l'entraînement
FEATURES_VITALES = [
    "age", "sex",
    "temperature", "heart_rate", "bp_systolic", "bp_diastolic",
    "spo2", "respiratory_rate", "glucose", "pain_score",
]

FEATURES_BINAIRES = [
    "chest_pain", "dyspnea", "loss_of_consciousness", "severe_bleeding",
    "neurological_symptoms", "abdominal_pain", "fever", "trauma",
]

FEATURES_NLP = [
    "nlp_chest_pain", "nlp_dyspnea", "nlp_loss_of_consciousness",
    "nlp_severe_bleeding", "nlp_neurological", "nlp_abdominal_pain",
    "nlp_fever", "nlp_trauma", "nlp_pain", "nlp_pain_score",
    "nlp_urgence_critique",
]

CIBLE = "esi_level"


def charger_et_preparer_donnees(chemin: str) -> pd.DataFrame:
    """Charge le CSV et enrichit avec les features NLP."""
    print(f"[1/5] Chargement des données : {chemin}")
    df = pd.read_csv(chemin)
    print(f"      → {len(df)} patients chargés, {df.shape[1]} colonnes")

    print("[2/5] Enrichissement NLP en cours...")
    df = enrichir_dataframe(df)
    print(f"      → {df.shape[1]} colonnes après enrichissement NLP")

    return df


def construire_features(df: pd.DataFrame) -> tuple:
    """Construit les matrices X (features) et y (cible)."""
    toutes_features = FEATURES_VITALES + FEATURES_BINAIRES + FEATURES_NLP

    # Vérifier que toutes les colonnes existent
    manquantes = [c for c in toutes_features if c not in df.columns]
    if manquantes:
        raise ValueError(f"Colonnes manquantes dans le dataset : {manquantes}")

    X = df[toutes_features].copy()
    y = df[CIBLE].copy()

    # Gestion des valeurs manquantes
    X = X.fillna(X.median())

    return X, y, toutes_features


def entrainer_modele(X_train: np.ndarray, y_train: np.ndarray) -> RandomForestClassifier:
    """
    Entraîne le modèle Random Forest avec les hyperparamètres optimisés
    pour la classification ESI multi-classes.
    """
    modele = RandomForestClassifier(
        n_estimators=200,        # 200 arbres pour la robustesse
        max_depth=15,            # Profondeur suffisante sans surapprentissage
        min_samples_split=5,     # Évite le surapprentissage
        min_samples_leaf=2,      # Feuilles avec au moins 2 exemples
        max_features="sqrt",     # Nombre de features par split
        class_weight="balanced", # Compense les classes minoritaires (ESI 1 rare)
        random_state=42,
        n_jobs=-1,               # Utilise tous les cœurs disponibles
    )
    modele.fit(X_train, y_train)
    return modele


def evaluer_modele(modele, X_test, y_test, noms_features) -> None:
    """Évalue le modèle et affiche les métriques complètes."""
    y_pred = modele.predict(X_test)

    print("\n" + "=" * 60)
    print("RÉSULTATS D'ÉVALUATION — Random Forest ESI")
    print("=" * 60)

    # Accuracy globale
    acc = accuracy_score(y_test, y_pred)
    print(f"\n[ACCURACY GLOBALE] {acc:.4f} ({acc*100:.2f}%)")

    # Rapport détaillé par classe
    print("\n[RAPPORT DE CLASSIFICATION PAR NIVEAU ESI]")
    print(classification_report(
        y_test, y_pred,
        target_names=[f"ESI {i}" for i in range(1, 6)],
        zero_division=0
    ))

    # Matrice de confusion
    print("[MATRICE DE CONFUSION]")
    cm = confusion_matrix(y_test, y_pred, labels=[1, 2, 3, 4, 5])
    cm_df = pd.DataFrame(
        cm,
        index=[f"Réel ESI {i}" for i in range(1, 6)],
        columns=[f"Prédit ESI {i}" for i in range(1, 6)]
    )
    print(cm_df.to_string())

    # Importance des features (top 15)
    print("\n[TOP 15 FEATURES LES PLUS IMPORTANTES]")
    importances = pd.Series(modele.feature_importances_, index=noms_features)
    top15 = importances.sort_values(ascending=False).head(15)
    for feature, score in top15.items():
        barre = "█" * int(score * 100)
        print(f"  {feature:<35} {score:.4f}  {barre}")


def sauvegarder_artefacts(modele, scaler, noms_features) -> None:
    """Sauvegarde le modèle, le scaler et les noms de features."""
    os.makedirs(os.path.join(BASE_DIR, "models"), exist_ok=True)

    with open(CHEMIN_MODELE, "wb") as f:
        pickle.dump(modele, f)
    print(f"\n[OK] Modèle sauvegardé → {CHEMIN_MODELE}")

    with open(CHEMIN_SCALER, "wb") as f:
        pickle.dump(scaler, f)
    print(f"[OK] Scaler sauvegardé → {CHEMIN_SCALER}")

    with open(CHEMIN_FEATURES, "wb") as f:
        pickle.dump(noms_features, f)
    print(f"[OK] Noms des features sauvegardés → {CHEMIN_FEATURES}")


def charger_modele():
    """Charge le modèle entraîné depuis le disque (utilisé par l'API Flask)."""
    with open(CHEMIN_MODELE, "rb") as f:
        modele = pickle.load(f)
    with open(CHEMIN_SCALER, "rb") as f:
        scaler = pickle.load(f)
    with open(CHEMIN_FEATURES, "rb") as f:
        noms_features = pickle.load(f)
    return modele, scaler, noms_features


def predire_esi(donnees_patient: dict) -> dict:
    """
    Prédit le niveau ESI d'un patient à partir de ses données brutes.

    Paramètre
    ---------
    donnees_patient : dict avec les constantes vitales + symptômes binaires
                      + symptom_text (optionnel)

    Retourne
    --------
    dict avec : esi_predit, probabilites, confiance
    """
    from nlp_extractor import extraire_features_nlp

    modele, scaler, noms_features = charger_modele()

    # Extraction NLP si texte disponible
    features_nlp = extraire_features_nlp(donnees_patient.get("symptom_text", ""))

    # Construction du vecteur de features
    vecteur = {}
    for feat in noms_features:
        if feat in donnees_patient:
            vecteur[feat] = donnees_patient[feat]
        elif feat in features_nlp:
            vecteur[feat] = features_nlp[feat]
        else:
            vecteur[feat] = 0  # valeur par défaut

    X = pd.DataFrame([vecteur])[noms_features]
    X = X.fillna(0)
    X_scaled = scaler.transform(X)

    # Prédiction
    esi_predit = int(modele.predict(X_scaled)[0])
    probas = modele.predict_proba(X_scaled)[0]
    confiance = float(round(max(probas) * 100, 1))

    return {
        "esi_predit":   esi_predit,
        "probabilites": {
            f"ESI_{i+1}": round(float(p) * 100, 1)
            for i, p in enumerate(probas)
        },
        "confiance":    confiance,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline principal
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("ENTRAÎNEMENT DU MODÈLE — HealthGate")
    print("=" * 60)

    # 1. Chargement et préparation
    df = charger_et_preparer_donnees(CHEMIN_DATA)

    # 2. Construction des features
    print("[3/5] Construction de la matrice de features...")
    X, y, noms_features = construire_features(df)
    print(f"      → Features : {X.shape[1]} | Patients : {X.shape[0]}")
    print(f"      → Distribution ESI : {dict(y.value_counts().sort_index())}")

    # 3. Division train/test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"      → Train : {len(X_train)} | Test : {len(X_test)}")

    # Normalisation (utile pour certains algorithmes, conservé pour la pipeline)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled  = scaler.transform(X_test)

    # 4. Entraînement
    print("\n[4/5] Entraînement du Random Forest...")
    modele = entrainer_modele(X_train_scaled, y_train)
    print("      → Entraînement terminé ✓")

    # Validation croisée
    scores_cv = cross_val_score(modele, X_train_scaled, y_train, cv=5, scoring="accuracy")
    print(f"      → Validation croisée 5-fold : {scores_cv.mean():.4f} ± {scores_cv.std():.4f}")

    # 5. Évaluation
    print("\n[5/5] Évaluation sur le jeu de test...")
    evaluer_modele(modele, X_test_scaled, y_test, noms_features)

    # 6. Sauvegarde
    sauvegarder_artefacts(modele, scaler, noms_features)

    print("\n[TERMINÉ] Modèle prêt à l'emploi pour l'API Flask.")


if __name__ == "__main__":
    main()
