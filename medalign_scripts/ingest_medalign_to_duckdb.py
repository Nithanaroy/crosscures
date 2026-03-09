#!/usr/bin/env python3
"""
MedAlign DuckDB Ingestion Script
=================================
Ingests all MedAlign data into a single DuckDB database:

  1. OMOP CDM tables  - CSV files under data/medalign/tables/
  2. Annotation TSVs  - all-instructions-rouge.tsv
                       clinician-instruction-responses.tsv
                       clinician-reviewed-model-responses.tsv

table names:
  - OMOP tables  : <stem>  (e.g. person, note, measurement, ...)
  - TSV tables   : instructions_rouge
                   clinician_instruction_responses
                   clinician_reviewed_model_responses

Usage:
    python medalign_scripts/ingest_medalign_to_duckdb.py
    python medalign_scripts/ingest_medalign_to_duckdb.py --db-path data/medalign/medalign.duckdb
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Dict, List, Tuple

import duckdb

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).parent.parent
DEFAULT_TABLES_PATH = _REPO_ROOT / "data" / "medalign" / "tables"
DEFAULT_FILES_PATH = (
    _REPO_ROOT
    / "data"
    / "medalign"
    / "files"
    / "medalign_instructions_v1_3"
)
DEFAULT_DB_PATH = _REPO_ROOT / "data" / "medalign" / "medalign.duckdb"

# ---------------------------------------------------------------------------
# TSV files to ingest  (file name -> table name)
# ---------------------------------------------------------------------------
TSV_FILES: Dict[str, str] = {
    "all-instructions-rouge.tsv": "instructions_rouge",
    "clinician-instruction-responses.tsv": "clinician_instruction_responses",
    "clinician-reviewed-model-responses.tsv": "clinician_reviewed_model_responses",
}

# ---------------------------------------------------------------------------
# Indexes for OMOP tables
# ---------------------------------------------------------------------------
TABLE_INDEXES: Dict[str, List[Tuple[str, str]]] = {
    "person": [
        ("person_id", "idx_person_id"),
    ],
    "visit_occurrence": [
        ("person_id", "idx_visit_person"),
        ("person_id, visit_start_DATE", "idx_visit_person_date"),
    ],
    "condition_occurrence": [
        ("person_id", "idx_condition_person"),
        ("person_id, condition_start_DATE", "idx_condition_person_date"),
        ("condition_concept_id", "idx_condition_concept"),
    ],
    "drug_exposure": [
        ("person_id", "idx_drug_person"),
        ("person_id, drug_exposure_start_DATE", "idx_drug_person_date"),
        ("drug_concept_id", "idx_drug_concept"),
    ],
    "procedure_occurrence": [
        ("person_id", "idx_procedure_person"),
        ("person_id, procedure_DATE", "idx_procedure_person_date"),
    ],
    "measurement": [
        ("person_id", "idx_measurement_person"),
        ("person_id, measurement_DATE", "idx_measurement_person_date"),
        ("measurement_concept_id", "idx_measurement_concept"),
    ],
    "observation": [
        ("person_id", "idx_observation_person"),
        ("person_id, observation_DATE", "idx_observation_person_date"),
    ],
    "note": [
        ("person_id", "idx_note_person"),
        ("person_id, note_DATE", "idx_note_person_date"),
    ],
    "death": [
        ("person_id", "idx_death_person"),
    ],
    "concept": [
        ("concept_id", "idx_concept_id"),
        ("vocabulary_id", "idx_concept_vocab"),
    ],
    "concept_relationship": [
        ("concept_id_1", "idx_concept_rel_1"),
        ("concept_id_2", "idx_concept_rel_2"),
    ],
    "concept_ancestor": [
        ("ancestor_concept_id", "idx_ancestor"),
        ("descendant_concept_id", "idx_descendant"),
    ],
    "clinician_instruction_responses": [
        ("instruction_id", "idx_cir_instruction"),
        ("person_id", "idx_cir_person"),
    ],
    "clinician_reviewed_model_responses": [
        ("instruction_id", "idx_crmr_instruction"),
        ("person_id", "idx_crmr_person"),
    ],
    "instructions_rouge": [
        ("instruction_id", "idx_ir_instruction"),
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def format_time(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}m"
    return f"{seconds / 3600:.1f}h"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest MedAlign data into DuckDB.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--tables-path",
        type=Path,
        default=DEFAULT_TABLES_PATH,
        help="Directory containing OMOP CDM CSV files",
    )
    parser.add_argument(
        "--files-path",
        type=Path,
        default=DEFAULT_FILES_PATH,
        help="Directory containing MedAlign TSV annotation files",
    )
    parser.add_argument(
        "--db-path",
        "-o",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Output DuckDB database file",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=4,
        help="Number of DuckDB threads",
    )
    parser.add_argument(
        "--memory-limit",
        default="8GB",
        help="DuckDB memory limit (e.g. '8GB')",
    )
    parser.add_argument(
        "--skip-indexes",
        action="store_true",
        help="Skip creating indexes (faster but slower queries)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

def ingest_csv(
    conn: duckdb.DuckDBPyConnection,
    path: Path,
    table_name: str,
) -> Tuple[int, float]:
    t0 = time.time()
    conn.execute(
        f"""
        CREATE OR REPLACE TABLE {table_name} AS
        SELECT * FROM read_csv_auto(
            ?,
            header=true,
            ignore_errors=true,
            sample_size=500000
        )
        """,
        [str(path)],
    )
    row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    return row_count, time.time() - t0


def ingest_tsv(
    conn: duckdb.DuckDBPyConnection,
    path: Path,
    table_name: str,
) -> Tuple[int, float]:
    t0 = time.time()
    conn.execute(
        f"""
        CREATE OR REPLACE TABLE {table_name} AS
        SELECT * FROM read_csv_auto(
            ?,
            header=true,
            delim='\t',
            quote='',
            ignore_errors=true,
            sample_size=500000
        )
        """,
        [str(path)],
    )
    row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    return row_count, time.time() - t0


def create_indexes(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
) -> None:
    specs = TABLE_INDEXES.get(table_name)
    if not specs:
        return
    for columns, idx_name in specs:
        try:
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table_name} ({columns})"
            )
        except Exception as exc:
            print(f"    [WARN] Index {idx_name} on {table_name}: {exc}")


def print_summary(conn: duckdb.DuckDBPyConnection) -> None:
    tables = conn.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main' AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    ).fetchall()

    print()
    print("=" * 65)
    print("DATABASE SUMMARY")
    print("=" * 65)
    print(f"  {'Table':<45} {'Rows':>15}")
    print(f"  {'-' * 45} {'-' * 15}")

    total_rows = 0
    for (tname,) in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {tname}").fetchone()[0]
        total_rows += count
        print(f"  {tname:<45} {count:>15,}")

    print(f"  {'-' * 45} {'-' * 15}")
    print(f"  {'TOTAL':<45} {total_rows:>15,}")
    print("=" * 65)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    missing = [
        p for p in (args.tables_path, args.files_path) if not p.exists()
    ]
    if missing:
        for p in missing:
            print(f"[ERROR] Path not found: {p}")
        return

    # Ensure output directory exists
    args.db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(str(args.db_path))
    conn.execute(f"PRAGMA threads={int(args.threads)}")
    conn.execute(f"PRAGMA memory_limit='{args.memory_limit}'")

    print("=" * 65)
    print("MedAlign DuckDB Ingestion")
    print("=" * 65)
    print(f"[INFO] OMOP tables  : {args.tables_path}")
    print(f"[INFO] TSV files    : {args.files_path}")
    print(f"[INFO] Database     : {args.db_path}")
    print()

    # ------------------------------------------------------------------
    # 1. OMOP CDM CSV tables
    # ------------------------------------------------------------------
    csv_files = sorted(args.tables_path.glob("*.csv"))
    print(f"[OMOP] Ingesting {len(csv_files)} CSV table(s)...")
    for csv_path in csv_files:
        table_name = csv_path.stem.lower()
        print(f"  -> {csv_path.name:<40} ", end="", flush=True)
        try:
            rows, elapsed = ingest_csv(conn, csv_path, table_name)
            print(f"[OK] {rows:>12,} rows  {format_time(elapsed)}")
            if not args.skip_indexes:
                create_indexes(conn, table_name)
        except Exception as exc:
            print(f"[ERROR] {exc}")

    # ------------------------------------------------------------------
    # 2. TSV annotation files
    # ------------------------------------------------------------------
    print()
    print(f"[TSV] Ingesting {len(TSV_FILES)} annotation file(s)...")
    for filename, table_name in TSV_FILES.items():
        tsv_path = args.files_path / filename
        if not tsv_path.exists():
            print(f"  -> {filename:<40} [WARN] file not found, skipping")
            continue
        print(f"  -> {filename:<40} ", end="", flush=True)
        try:
            rows, elapsed = ingest_tsv(conn, tsv_path, table_name)
            print(f"[OK] {rows:>12,} rows  {format_time(elapsed)}")
            if not args.skip_indexes:
                create_indexes(conn, table_name)
        except Exception as exc:
            print(f"[ERROR] {exc}")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print_summary(conn)
    conn.close()
    print(f"\n[DONE] Database saved to: {args.db_path}")


if __name__ == "__main__":
    main()
