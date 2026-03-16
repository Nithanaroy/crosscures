#!/usr/bin/env python3
"""
MedAlign - Get All Records for a Single Patient
================================================
Queries the MedAlign DuckDB database and prints every record across all
OMOP CDM tables and MedAlign annotation tables for a given person_id.

Usage:
    python medalign_scripts/get_patient_records.py --person-id 12345
    python medalign_scripts/get_patient_records.py --person-id 12345 --db-path data/medalign/medalign.duckdb
    python medalign_scripts/get_patient_records.py --list-patients
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).parent.parent
DEFAULT_DB_PATH = _REPO_ROOT / "data" / "medalign" / "medalign.duckdb"

# ---------------------------------------------------------------------------
# OMOP CDM tables that have a person_id column
# ---------------------------------------------------------------------------
OMOP_PATIENT_TABLES = [
    "visit_occurrence",
    "condition_occurrence",
    "drug_exposure",
    "procedure_occurrence",
    "measurement",
    "observation",
    "note",
    "death",
    "drug_era",
    "condition_era",
    "observation_period",
    "visit_detail",
    "fact_relationship",
    "payer_plan_period",
]

# ---------------------------------------------------------------------------
# Annotation tables (MedAlign-specific) that have a person_id column
# ---------------------------------------------------------------------------
ANNOTATION_PATIENT_TABLES = [
    "clinician_instruction_responses",
    "clinician_reviewed_model_responses",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_section(title: str, df: pd.DataFrame) -> None:
    """Print a labelled section with row count and the dataframe."""
    sep = "-" * 60
    print(f"\n{sep}")
    print(f"[{title.upper()}] - {len(df)} row(s)")
    print(sep)
    if df.empty:
        print("  (no records)")
    else:
        with pd.option_context(
            "display.max_columns", None,
            "display.max_colwidth", 80,
            "display.width", 0,
        ):
            print(df.to_string(index=False))


def _table_exists(conn: duckdb.DuckDBPyConnection, table: str) -> bool:
    """Return True if the table exists in the database."""
    result = conn.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
        [table],
    ).fetchone()
    return bool(result and result[0] > 0)


def _has_column(conn: duckdb.DuckDBPyConnection, table: str, column: str) -> bool:
    """Return True if a table has the given column."""
    result = conn.execute(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_name = ? AND column_name = ?",
        [table, column],
    ).fetchone()
    return bool(result and result[0] > 0)


# ---------------------------------------------------------------------------
# Main query function
# ---------------------------------------------------------------------------

def get_patient_records(
    person_id: int,
    db_path: Path = DEFAULT_DB_PATH,
    output_dir: Optional[Path] = None,
) -> None:
    """
    Print all records for a single patient across every relevant table.
    Optionally write the output to a text file named <person_id>.txt.

    Args:
        person_id:  The OMOP person_id to look up.
        db_path:    Path to the MedAlign DuckDB file.
        output_dir: Directory in which to save <person_id>.txt.
                    If None, output is only printed to stdout.
    """
    if not db_path.exists():
        raise FileNotFoundError(
            f"Database not found at {db_path}. "
            "Run medalign_scripts/ingest_medalign_to_duckdb.py first."
        )

    # Capture all output so we can mirror it to a file if requested.
    buffer = io.StringIO()
    original_stdout = sys.stdout
    # We write to both the original stdout and the buffer simultaneously.
    class _Tee:
        def write(self, s: str) -> int:
            original_stdout.write(s)
            buffer.write(s)
            return len(s)
        def flush(self) -> None:
            original_stdout.flush()

    sys.stdout = _Tee()  # type: ignore[assignment]

    conn = duckdb.connect(str(db_path), read_only=True)

    print("=" * 60)
    print(f"[PATIENT RECORDS] person_id = {person_id}")
    print(f"[DATABASE] {db_path}")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Demographics
    # ------------------------------------------------------------------
    if _table_exists(conn, "person"):
        df = conn.execute(
            """
            SELECT
                p.*,
                g.concept_name  AS gender_name,
                r.concept_name  AS race_name,
                e.concept_name  AS ethnicity_name
            FROM person p
            LEFT JOIN concept g ON p.gender_concept_id    = g.concept_id
            LEFT JOIN concept r ON p.race_concept_id      = r.concept_id
            LEFT JOIN concept e ON p.ethnicity_concept_id = e.concept_id
            WHERE p.person_id = ?
            """,
            [person_id],
        ).df()
        _print_section("DEMOGRAPHICS (person)", df)

    # ------------------------------------------------------------------
    # 2. OMOP clinical tables
    # ------------------------------------------------------------------
    for table in OMOP_PATIENT_TABLES:
        if not _table_exists(conn, table):
            continue
        if not _has_column(conn, table, "person_id"):
            continue

        df = conn.execute(
            f"SELECT * FROM {table} WHERE person_id = ? ORDER BY 1",  # noqa: S608
            [person_id],
        ).df()
        _print_section(table, df)

    # ------------------------------------------------------------------
    # 3. MedAlign annotation tables
    # ------------------------------------------------------------------
    for table in ANNOTATION_PATIENT_TABLES:
        if not _table_exists(conn, table):
            continue
        if not _has_column(conn, table, "person_id"):
            continue

        df = conn.execute(
            f"SELECT * FROM {table} WHERE person_id = ? ORDER BY 1",  # noqa: S608
            [person_id],
        ).df()
        _print_section(table, df)

    # ------------------------------------------------------------------
    # 4. Instructions linked to this patient via annotation tables
    # ------------------------------------------------------------------
    if _table_exists(conn, "instructions_rouge") and _table_exists(
        conn, "clinician_instruction_responses"
    ):
        df = conn.execute(
            """
            SELECT ir.*
            FROM instructions_rouge ir
            JOIN clinician_instruction_responses cir
              ON ir.instruction_id = cir.instruction_id
            WHERE cir.person_id = ?
            ORDER BY ir.instruction_id
            """,
            [person_id],
        ).df()
        _print_section("INSTRUCTIONS (instructions_rouge)", df)

    conn.close()
    print("\n[DONE]")

    sys.stdout = original_stdout

    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        out_file = output_dir / f"{person_id}.txt"
        out_file.write_text(buffer.getvalue(), encoding="utf-8")
        print(f"[INFO] Saved to {out_file}")


# ---------------------------------------------------------------------------
# Utility: list available patients
# ---------------------------------------------------------------------------

def list_patients(
    db_path: Path = DEFAULT_DB_PATH,
    limit: int = 20,
) -> None:
    """Print a sample of person_ids available in the database."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at {db_path}.")

    conn = duckdb.connect(str(db_path), read_only=True)
    df = conn.execute(
        f"SELECT person_id, year_of_birth, race_source_value, ethnicity_source_value "  # noqa: S608
        f"FROM person ORDER BY person_id LIMIT {limit}"
    ).df()
    conn.close()

    print(f"[INFO] First {limit} patients in the database:")
    print(df.to_string(index=False))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Retrieve all records for a single patient from MedAlign DuckDB.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--person-id",
        type=int,
        default=None,
        help="OMOP person_id of the patient to retrieve",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to the MedAlign DuckDB file",
    )
    parser.add_argument(
        "--list-patients",
        action="store_true",
        help="List sample patient IDs from the database and exit",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of patients to show with --list-patients",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory to save <person_id>.txt output file (created if missing)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.list_patients:
        list_patients(db_path=args.db_path, limit=args.limit)
        return

    if args.person_id is None:
        print("[ERROR] Provide --person-id <id> or use --list-patients to find valid IDs.")
        raise SystemExit(1)

    get_patient_records(
        person_id=args.person_id,
        db_path=args.db_path,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
