
import os
import pickle
from pathlib import Path
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
from questions_moteur import FEATURES_QUESTIONS, encoder_reponses
from unified_data_store import DEFAULT_UNIFIED_DB_PATH, load_patients_dataframe

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CHEMIN_DATA     = os.path.join(BASE_DIR, "data", "patients_50000.csv")
CHEMIN_DB_UNIFIE = str(DEFAULT_UNIFIED_DB_PATH)
CHEMIN_MODELE   = os.path.join(BASE_DIR, "models", "random_forest_esi.pkl")
CHEMIN_SCALER   = os.path.join(BASE_DIR, "models", "scaler.pkl")
CHEMIN_FEATURES = os.path.join(BASE_DIR, "models", "feature_names.pkl")
CHEMIN_DIAGNOSTIC_ENCODER = os.path.join(BASE_DIR, "models", "diagnostic_encoder.pkl")

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

FEATURES_DIAGNOSTIC = ["diagnostic_encode"]

CIBLE = "esi_level"


def charger_et_preparer_donnees(chemin: str) -> pd.DataFrame:
    """Charge les donnees depuis base unifiee (prioritaire) ou CSV puis enrichit NLP."""
    source = Path(chemin)

    if source.suffix.lower() == ".db" and source.exists():
        print(f"[1/5] Chargement des donnees depuis base unifiee : {source}")
        df = load_patients_dataframe(source)
    elif source.exists():
        print(f"[1/5] Chargement des donnees CSV : {source}")
        df = pd.read_csv(source)
    else:
        db_default = Path(CHEMIN_DB_UNIFIE)
        csv_default = Path(CHEMIN_DATA)
        if db_default.exists():
            print(f"[1/5] Chargement des donnees depuis base unifiee : {db_default}")
            df = load_patients_dataframe(db_default)
        elif csv_default.exists():
            print(f"[1/5] Chargement des donnees CSV : {csv_default}")
            df = pd.read_csv(csv_default)
        else:
            raise FileNotFoundError(
                f"Aucune source de donnees trouvee: {db_default} ou {csv_default}"
            )

    print(f"      → {len(df)} patients chargés, {df.shape[1]} colonnes")

    print("[2/5] Enrichissement NLP en cours...")
    df = enrichir_dataframe(df)
    print(f"      → {df.shape[1]} colonnes après enrichissement NLP")

    return df


def enrichir_features_questions(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute des réponses de questions ciblées synthétiques au DataFrame."""
    df = df.copy()

    def col_texte(nom: str) -> pd.Series:
        if nom in df.columns:
            return df[nom].fillna("").astype(str).str.lower()
        return pd.Series([""] * len(df), index=df.index)

    def col_numerique(nom: str, defaut: float = 0.0) -> pd.Series:
        if nom in df.columns:
            return pd.to_numeric(df[nom], errors="coerce").fillna(defaut)
        return pd.Series([defaut] * len(df), index=df.index, dtype=float)

    texte = col_texte("symptom_text")
    diag = col_texte("diagnostic_probable")
    comorbs = col_texte("comorbidites")

    age = col_numerique("age", 30)
    sex = col_numerique("sex", 0)
    temp = col_numerique("temperature", 37.0)
    fc = col_numerique("heart_rate", 75)
    ta_sys = col_numerique("bp_systolic", 120)
    ta_dia = col_numerique("bp_diastolic", 80)
    spo2 = col_numerique("spo2", 98.0)
    fr = col_numerique("respiratory_rate", 16)
    glucose = col_numerique("glucose", 90)
    douleur = col_numerique("pain_score", 0)

    chest = col_numerique("chest_pain", 0)
    dyspnea = col_numerique("dyspnea", 0)
    loss = col_numerique("loss_of_consciousness", 0)
    bleed = col_numerique("severe_bleeding", 0)
    neuro = col_numerique("neurological_symptoms", 0)
    abdominal = col_numerique("abdominal_pain", 0)
    fever = col_numerique("fever", 0)
    trauma = col_numerique("trauma", 0)

    df["diagnostic_encode"] = col_numerique("diagnostic_encode", 0).astype(int)

    df["q_douleur_irradiee_bras"] = (
        (chest > 0)
        & (
            (fc > 110)
            | diag.str.contains("infarct|cardiaque|stemi|nstemi|angine", regex=True)
            | texte.str.contains("bras gauche|mâchoire|machoire|épaule|epaule")
        )
    ).astype(int)

    df["q_antecedent_infarctus"] = (
        age > 55
    ).astype(int) & (
        diag.str.contains("infarct|cardiaque|ischémi|ischemi|angine", regex=True)
        | comorbs.str.contains("cardiopath|hypertension", regex=True)
    ).astype(int)

    df["q_medicaments_coeur"] = (
        comorbs.str.contains("cardiopath|hypertension", regex=True)
        | diag.str.contains("infarct|cardiaque|angine|hypertension", regex=True)
    ).astype(int)

    df["q_douleur_repos_effort"] = np.select(
        [
            chest > 0,
            (chest > 0) & (fc > 115),
            (chest > 0) & (fr > 22),
        ],
        [1, 2, 3],
        default=0,
    )

    df["q_duree_dyspnee"] = np.select(
        [spo2 < 88, spo2 < 93, dyspnea > 0],
        [3, 2, 1],
        default=0,
    )
    df["q_dyspnee_aggrave_effort"] = ((dyspnea > 0) & ((fr > 22) | (spo2 < 94))).astype(int)
    df["q_antecedent_asthme"] = (
        comorbs.str.contains("asthme|bpc|bpco|tuberculose|pneumonie", regex=True)
        | diag.str.contains("asthme|bpc|bpco|tuberculose|pneumonie", regex=True)
    ).astype(int)

    df["q_duree_fievre"] = np.select(
        [temp >= 40.0, temp >= 39.0, fever > 0],
        [2, 1, 1],
        default=0,
    )
    df["q_frissons_sueurs"] = ((fever > 0) | (temp >= 38.8) | diag.str.contains("palud|typho|infection", regex=True)).astype(int)
    df["q_voyage_paludisme"] = (
        diag.str.contains("palud|malaria", regex=True)
        | texte.str.contains("voyage|village|campagne|zone de paludisme")
    ).astype(int)

    df["q_hypertension_connue"] = (
        (ta_sys >= 160)
        | (ta_dia >= 100)
        | comorbs.str.contains("hypertension|hta", regex=True)
        | diag.str.contains("hypertension|crise hypertensive", regex=True)
    ).astype(int)
    df["q_medicaments_tension"] = (
        df["q_hypertension_connue"] > 0
    ).astype(int)
    df["q_maux_tete_vision"] = (
        (ta_sys >= 170)
        | diag.str.contains("hypertension|avc|crise hypertensive", regex=True)
        | texte.str.contains("maux de tête|tête|vision|vertige")
    ).astype(int)

    df["q_a_mange_aujourdhui"] = (glucose < 70).astype(int)
    df["q_insuline_pris"] = (
        (glucose < 70)
        | comorbs.str.contains("diabète|diabet", regex=True)
        | diag.str.contains("diabète|hypoglycémie", regex=True)
    ).astype(int)

    df["q_localisation_abdomen"] = np.select(
        [
            abdominal > 0,
            diag.str.contains("appendic|flanc droit", regex=True),
            diag.str.contains("gastro|diffus|centre", regex=True),
        ],
        [3, 1, 3],
        default=0,
    )
    df["q_fievre_associee_abdomen"] = ((abdominal > 0) & ((fever > 0) | (temp >= 38.0))).astype(int)
    df["q_vomissements_abdomen"] = (
        (abdominal > 0)
        & (texte.str.contains("vomit|vomiss|naus", regex=True) | diag.str.contains("appendic|gastro", regex=True))
    ).astype(int)

    df["q_trauma_perte_conscience"] = ((trauma > 0) & (loss > 0)).astype(int)
    df["q_trauma_saignement"] = ((trauma > 0) & (bleed > 0)).astype(int)
    df["q_trauma_zone"] = np.select(
        [
            trauma > 0,
            texte.str.contains("tête|crâne|cran", regex=True),
            texte.str.contains("poitrine|thorax", regex=True),
            texte.str.contains("ventre|abdomen", regex=True),
        ],
        [4, 1, 2, 3],
        default=0,
    )

    df["q_neuro_faiblesse"] = ((neuro > 0) & (texte.str.contains("faiblesse|paralys|hémipl|hemipl|côté", regex=True) | diag.str.contains("avc|attaque", regex=True))).astype(int)
    df["q_neuro_parole"] = ((neuro > 0) & (texte.str.contains("parle|parole|mots", regex=True) | diag.str.contains("avc|aphasie", regex=True))).astype(int)
    df["q_neuro_confusion"] = ((neuro > 0) & (texte.str.contains("confus|désorient|desorient|ne sait plus", regex=True) | diag.str.contains("méning|mening|avc", regex=True))).astype(int)

    df["q_pediatrie_hydratation"] = ((age < 5) & ((fever > 0) | (dyspnea > 0) | (abdominal > 0))).astype(int)
    df["q_grossesse_possible"] = ((sex == 0) & (age.between(12, 55)) & ((abdominal > 0) | (fever > 0) | texte.str.contains("saign", regex=True))).astype(int)

    df["q_antecedent_symptome"] = (
        texte.str.contains("depuis|déjà eu|deja eu|reviens|revient", regex=True)
        | diag.str.contains("chronique|récidiv|recidiv", regex=True)
    ).astype(int)
    df["q_aggravation_effort"] = ((chest > 0) | (dyspnea > 0) | (douleur >= 6)).astype(int)
    df["q_prise_medicament"] = (
        texte.str.contains("médicament|traitement|ordonnance|pilule|insuline", regex=True)
        | comorbs.str.contains("hypertension|diabète|asthme|drépanocytose", regex=True)
    ).astype(int)
    df["q_duree_symptomes"] = np.select(
        [texte.str.contains("depuis hier|depuis ce matin|depuis quelques", regex=True), texte.str.contains("depuis plusieurs|depuis 3 jours|depuis 4 jours|depuis 2 jours", regex=True)],
        [1, 2],
        default=0,
    )

    return df


def construire_features(df: pd.DataFrame) -> tuple:
    """Construit les matrices X (features) et y (cible)."""
    df = enrichir_features_questions(df)
    toutes_features = FEATURES_VITALES + FEATURES_BINAIRES + FEATURES_NLP + FEATURES_DIAGNOSTIC + FEATURES_QUESTIONS

    # Vérifier que toutes les colonnes existent
    manquantes = [c for c in toutes_features if c not in df.columns]
    if manquantes:
        raise ValueError(f"Colonnes manquantes dans le dataset : {manquantes}")

    X = df[toutes_features].copy()
    y = df[CIBLE].copy()

    # Gestion des valeurs manquantes
    X = X.fillna(X.median())

    return X, y, toutes_features


def charger_donnees(chemin: str = CHEMIN_DB_UNIFIE) -> pd.DataFrame:
    """Alias requis pour compatibilite avec le contrat projet."""
    return charger_et_preparer_donnees(chemin)


def preparer_features(df: pd.DataFrame) -> tuple:
    """Alias requis pour compatibilite avec le contrat projet."""
    return construire_features(df)


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

    # Conserve explicitement l'encodeur de diagnostic attendu par la structure finale.
    try:
        from data_generator import DIAGNOSTIC_ENCODE

        with open(CHEMIN_DIAGNOSTIC_ENCODER, "wb") as f:
            pickle.dump(DIAGNOSTIC_ENCODE, f)
        print(f"[OK] Encodeur diagnostic sauvegardé → {CHEMIN_DIAGNOSTIC_ENCODER}")
    except Exception:
        with open(CHEMIN_DIAGNOSTIC_ENCODER, "wb") as f:
            pickle.dump({}, f)
        print(f"[WARN] Encodeur diagnostic par défaut sauvegardé → {CHEMIN_DIAGNOSTIC_ENCODER}")


def sauvegarder(modele, scaler, noms_features) -> None:
    """Alias requis pour compatibilite avec le contrat projet."""
    sauvegarder_artefacts(modele, scaler, noms_features)


def charger_modele():
    """Charge le modèle entraîné depuis le disque (utilisé par l'API Flask)."""
    with open(CHEMIN_MODELE, "rb") as f:
        modele = pickle.load(f)
    with open(CHEMIN_SCALER, "rb") as f:
        scaler = pickle.load(f)
    with open(CHEMIN_FEATURES, "rb") as f:
        noms_features = pickle.load(f)
    return modele, scaler, noms_features


def _encodage_diagnostic_probable(diagnostic: str) -> int:
    """Retourne un encodage numérique du diagnostic probable."""
    if not diagnostic:
        return 0

    try:
        from data_generator import DIAGNOSTIC_ENCODE

        return int(DIAGNOSTIC_ENCODE.get(diagnostic, 0))
    except Exception:
        return 0


def _estimer_diagnostic_probable(donnees_patient: dict, features_nlp: dict) -> str:
    """Estime un diagnostic probable simple à afficher dans le rapport."""
    constantes = donnees_patient
    texte = str(donnees_patient.get("symptom_text", "")).lower()

    if features_nlp.get("nlp_loss_of_consciousness", 0) or features_nlp.get("nlp_severe_bleeding", 0) or features_nlp.get("nlp_trauma", 0):
        return "Traumatisme grave / urgence vitale"
    if features_nlp.get("nlp_chest_pain", 0) and (features_nlp.get("nlp_dyspnea", 0) or constantes.get("heart_rate", 0) > 110):
        return "Syndrome coronarien aigu"
    if constantes.get("spo2", 98) < 93 or features_nlp.get("nlp_dyspnea", 0):
        return "Détresse respiratoire"
    if constantes.get("temperature", 37) >= 39 or features_nlp.get("nlp_fever", 0):
        if "palud" in texte or "voyage" in texte:
            return "Paludisme / syndrome fébrile"
        return "Syndrome infectieux fébrile"
    if constantes.get("bp_systolic", 120) >= 160 or constantes.get("bp_diastolic", 80) >= 100:
        return "Hypertension artérielle sévère"
    if constantes.get("glucose", 90) < 70:
        return "Hypoglycémie"
    if features_nlp.get("nlp_abdominal_pain", 0):
        return "Douleur abdominale aiguë"
    if features_nlp.get("nlp_neurological", 0):
        return "Atteinte neurologique aiguë"
    if features_nlp.get("nlp_pain_score", 0) >= 7:
        return "Douleur aiguë intense"
    return "Évaluation clinique complémentaire"


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
    questions = donnees_patient.get("questions") or []
    reponses_questions = donnees_patient.get("question_reponses") or donnees_patient.get("reponses_questions") or {}
    features_questions = encoder_reponses(questions, reponses_questions) if questions else {feat: 0 for feat in FEATURES_QUESTIONS}

    diagnostic_probable = donnees_patient.get("diagnostic_probable") or _estimer_diagnostic_probable(donnees_patient, features_nlp)
    diagnostic_encode = donnees_patient.get("diagnostic_encode")
    if diagnostic_encode is None:
        diagnostic_encode = _encodage_diagnostic_probable(diagnostic_probable)

    # Construction du vecteur de features
    vecteur = {}
    for feat in noms_features:
        if feat in donnees_patient:
            vecteur[feat] = donnees_patient[feat]
        elif feat in features_questions:
            vecteur[feat] = features_questions[feat]
        elif feat == "diagnostic_encode":
            vecteur[feat] = diagnostic_encode
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
        "diagnostic_probable": diagnostic_probable,
        "diagnostic_encode": int(diagnostic_encode),
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
    source = CHEMIN_DB_UNIFIE if os.path.exists(CHEMIN_DB_UNIFIE) else CHEMIN_DATA
    df = charger_et_preparer_donnees(source)

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
