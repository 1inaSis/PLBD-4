"""
build_unified_database.py — Construit une base SQLite unique patients + questions.

Usage:
  py build_unified_database.py
  py build_unified_database.py --patients-csv data/patients_50000.csv --question-count 50000 --db-out data/healthgate_unified.db
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from question_bank_generator import build_rows
from unified_data_store import build_unified_database


def main() -> None:
    parser = argparse.ArgumentParser(description="Construit la base unique HealthGate")
    parser.add_argument("--patients-csv", type=str, default="data/patients_50000.csv", help="CSV patients source")
    parser.add_argument("--question-count", type=int, default=50000, help="Nombre de questions a generer")
    parser.add_argument("--seed", type=int, default=42, help="Seed de generation des questions")
    parser.add_argument("--db-out", type=str, default="data/healthgate_unified.db", help="Sortie sqlite")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    patients_csv = base_dir / args.patients_csv
    db_out = base_dir / args.db_out

    if not patients_csv.exists():
        raise FileNotFoundError(f"CSV patients introuvable: {patients_csv}")

    print(f"[1/3] Chargement patients: {patients_csv}")
    patients_df = pd.read_csv(patients_csv)

    print(f"[2/3] Generation banque questions: {args.question_count}")
    question_rows = build_rows(args.question_count, seed=args.seed)

    print(f"[3/3] Construction base unifiee: {db_out}")
    final_db = build_unified_database(patients_df, question_rows, db_path=db_out)
    print(f"[OK] Base unifiee prete -> {final_db}")


if __name__ == "__main__":
    main()
