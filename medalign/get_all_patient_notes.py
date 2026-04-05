#!/usr/bin/env python3
"""
MedAlign - Get Notes for All Patients
=====================================
Runs the existing single-patient notes exporter for every patient that has
at least one note in the `note` table.

Usage:
    python medalign/get_all_patient_notes.py
    python medalign/get_all_patient_notes.py --limit 100
    python medalign/get_all_patient_notes.py --start-at-person-id 124000000
    python medalign/get_all_patient_notes.py --print-only
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

try:
    # Supports running as a script from repo root.
    from get_patient_notes import (  # type: ignore[import-not-found]
        DEFAULT_DB_PATH,
        DEFAULT_OUTPUT_DIR,
        get_patient_notes,
    )
except ImportError:
    # Supports running as a module: python -m medalign.get_all_patient_notes
    from medalign.get_patient_notes import (  # type: ignore[import-not-found]
        DEFAULT_DB_PATH,
        DEFAULT_OUTPUT_DIR,
        get_patient_notes,
    )
from tqdm import tqdm


def list_patient_ids_with_notes(db_path: Path) -> list[int]:
    """Return all distinct person_id values present in the note table."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at {db_path}.")

    conn = duckdb.connect(str(db_path), read_only=True)
    rows = conn.execute(
        """
        SELECT DISTINCT person_id
        FROM note
        WHERE person_id IS NOT NULL
        ORDER BY person_id
        """
    ).fetchall()
    conn.close()

    return [int(row[0]) for row in rows]


def run_all_patient_notes(
    db_path: Path = DEFAULT_DB_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    print_only: bool = False,
    limit: int | None = None,
    start_at_person_id: int | None = None,
    stop_on_error: bool = False,
) -> None:
    """Export notes for each patient with notes in the database."""
    person_ids = list_patient_ids_with_notes(db_path)

    if start_at_person_id is not None:
        person_ids = [pid for pid in person_ids if pid >= start_at_person_id]

    if limit is not None:
        person_ids = person_ids[:limit]

    if not person_ids:
        print("[WARN] No matching patients found.")
        return

    print(f"[INFO] Processing {len(person_ids)} patient(s).")

    success_count = 0
    failed_ids: list[int] = []

    iterator = enumerate(tqdm(person_ids, desc="Exporting patients", unit="patient"), start=1)

    for idx, person_id in iterator:
        try:
            get_patient_notes(
                person_id=person_id,
                db_path=db_path,
                output_dir=output_dir,
                print_only=print_only,
            )
            success_count += 1
        except Exception as exc:
            failed_ids.append(person_id)
            print(f"[ERROR] person_id={person_id} failed: {exc}")
            if stop_on_error:
                raise

    print("\n" + "=" * 60)
    print("[SUMMARY]")
    print(f"[INFO] Succeeded: {success_count}")
    print(f"[INFO] Failed   : {len(failed_ids)}")
    if failed_ids:
        print(f"[INFO] Failed IDs: {failed_ids}")
    if not print_only:
        print(f"[INFO] Output root: {output_dir}")
    print("=" * 60)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the patient-notes export for all patients with notes.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to the MedAlign DuckDB file",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Root directory for saved notes",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print notes to stdout instead of writing files",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only process the first N matching patients",
    )
    parser.add_argument(
        "--start-at-person-id",
        type=int,
        default=None,
        help="Only process person_id values >= this value",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop immediately if any patient fails",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_all_patient_notes(
        db_path=args.db_path,
        output_dir=args.output_dir,
        print_only=args.print_only,
        limit=args.limit,
        start_at_person_id=args.start_at_person_id,
        stop_on_error=args.stop_on_error,
    )


if __name__ == "__main__":
    main()
