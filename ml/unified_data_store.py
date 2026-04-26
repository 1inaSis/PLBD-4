"""
unified_data_store.py — Base unifiee HealthGate (patients + questions)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_UNIFIED_DB_PATH = BASE_DIR / "data" / "healthgate_unified.db"


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS patients (
            patient_id TEXT PRIMARY KEY,
            age INTEGER,
            sex INTEGER,
            temperature REAL,
            heart_rate INTEGER,
            bp_systolic INTEGER,
            bp_diastolic INTEGER,
            spo2 REAL,
            respiratory_rate INTEGER,
            glucose REAL,
            pain_score INTEGER,
            chest_pain INTEGER,
            dyspnea INTEGER,
            loss_of_consciousness INTEGER,
            severe_bleeding INTEGER,
            neurological_symptoms INTEGER,
            abdominal_pain INTEGER,
            fever INTEGER,
            trauma INTEGER,
            triage_score_raw REAL,
            esi_level INTEGER,
            diagnostic_probable TEXT,
            diagnostic_encode INTEGER,
            comorbidites TEXT,
            motif_visite TEXT,
            symptom_text TEXT,
            arrival_time TEXT,
            periode_journee TEXT,
            jour_semaine TEXT,
            wait_time_minutes INTEGER
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS question_bank (
            question_uid TEXT PRIMARY KEY,
            scenario TEXT,
            feature_name TEXT,
            type TEXT,
            texte TEXT,
            choix_json TEXT,
            placeholder TEXT,
            poids INTEGER
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS patient_question_responses (
            response_id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT NOT NULL,
            question_uid TEXT NOT NULL,
            response_value TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(patient_id) REFERENCES patients(patient_id),
            FOREIGN KEY(question_uid) REFERENCES question_bank(question_uid)
        )
        """
    )

    conn.execute("CREATE INDEX IF NOT EXISTS idx_questions_scenario ON question_bank(scenario)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_questions_feature ON question_bank(feature_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_patients_esi ON patients(esi_level)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_responses_patient ON patient_question_responses(patient_id)")


def build_unified_database(
    patients_df: pd.DataFrame,
    question_rows: Iterable[dict],
    db_path: str | Path = DEFAULT_UNIFIED_DB_PATH,
) -> Path:
    target = Path(db_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(target) as conn:
        _create_schema(conn)

        patients_df.to_sql("patients", conn, if_exists="replace", index=False)

        questions_df = pd.DataFrame(list(question_rows))
        if not questions_df.empty:
            questions_df.to_sql("question_bank", conn, if_exists="replace", index=False)

        conn.execute("VACUUM")

    return target


def load_patients_dataframe(db_path: str | Path = DEFAULT_UNIFIED_DB_PATH) -> pd.DataFrame:
    source = Path(db_path)
    if not source.exists():
        raise FileNotFoundError(f"Base unifiee introuvable: {source}")

    with sqlite3.connect(source) as conn:
        return pd.read_sql_query("SELECT * FROM patients", conn)


def load_question_rows(db_path: str | Path = DEFAULT_UNIFIED_DB_PATH) -> list[dict]:
    source = Path(db_path)
    if not source.exists():
        return []

    with sqlite3.connect(source) as conn:
        df = pd.read_sql_query(
            """
            SELECT question_uid, scenario, feature_name, type, texte, choix_json, placeholder, poids
            FROM question_bank
            """,
            conn,
        )

    return df.to_dict(orient="records")
