#!/usr/bin/env python3
"""
MedAlign - Get All Notes for a Single Patient
==============================================
Fetches every note from the `note` table for a given person_id and
writes each one to its own text file:

    <output_dir>/<person_id>/<note_id>_<date>_<title>.txt

Usage:
    python medalign_scripts/get_patient_notes.py --person-id 124692603
    python medalign_scripts/get_patient_notes.py --person-id 124692603 --output-dir data/patient_notes
    python medalign_scripts/get_patient_notes.py --person-id 124692603 --print-only
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import duckdb

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).parent.parent
DEFAULT_DB_PATH = _REPO_ROOT / "data" / "medalign" / "medalign.duckdb"
DEFAULT_OUTPUT_DIR = _REPO_ROOT / "data" / "patient_notes"


def _safe_filename(value: str, max_len: int = 50) -> str:
    """Strip characters that are unsafe in filenames."""
    value = re.sub(r'[^\w\-. ]', '_', str(value))
    return value[:max_len].strip()


def get_patient_notes(
    person_id: int,
    db_path: Path = DEFAULT_DB_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    print_only: bool = False,
) -> None:
    """
    Fetch all notes for a patient and save each to a text file.

    Args:
        person_id:  OMOP person_id.
        db_path:    Path to the MedAlign DuckDB file.
        output_dir: Root directory for output; a sub-folder named after
                    person_id is created inside it.
        print_only: If True, print notes to stdout without saving files.
    """
    if not db_path.exists():
        raise FileNotFoundError(
            f"Database not found at {db_path}. "
            "Run medalign_scripts/ingest_medalign_to_duckdb.py first."
        )

    conn = duckdb.connect(str(db_path), read_only=True)

    rows = conn.execute(
        """
        SELECT
            n.note_id,
            n.note_DATE,
            n.note_title,
            nt.concept_name  AS note_type,
            nc.concept_name  AS note_class,
            n.note_text
        FROM note n
        LEFT JOIN concept nt ON n.note_type_concept_id  = nt.concept_id
        LEFT JOIN concept nc ON n.note_class_concept_id = nc.concept_id
        WHERE n.person_id = ?
        ORDER BY n.note_DATE, n.note_id
        """,
        [person_id],
    ).fetchall()

    conn.close()

    if not rows:
        print(f"[WARN] No notes found for person_id={person_id}.")
        return

    print(f"[INFO] Found {len(rows)} note(s) for person_id={person_id}.")

    if not print_only:
        patient_dir = Path(output_dir) / str(person_id)
        patient_dir.mkdir(parents=True, exist_ok=True)

    for note_id, note_date, note_title, note_type, note_class, note_text in rows:
        header_lines = [
            "=" * 60,
            f"note_id    : {note_id}",
            f"date       : {note_date}",
            f"title      : {note_title}",
            f"type       : {note_type}",
            f"class      : {note_class}",
            "=" * 60,
            "",
        ]
        header = "\n".join(header_lines)
        body = note_text or "(no text)"
        content = header + body + "\n"

        if print_only:
            print(content)
        else:
            safe_date = _safe_filename(str(note_date))
            safe_title = _safe_filename(str(note_title or "untitled"))
            filename = f"{note_id}_{safe_date}_{safe_title}.txt"
            out_file = patient_dir / filename
            out_file.write_text(content, encoding="utf-8")
            print(f"[OK] {out_file}")

    if not print_only:
        print(f"[DONE] Notes saved to {patient_dir}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Save all OMOP notes for a patient to individual text files.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--person-id",
        type=int,
        required=True,
        help="OMOP person_id of the patient",
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
        help="Root directory for saved notes (a sub-folder per patient is created)",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print notes to stdout instead of saving to files",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    get_patient_notes(
        person_id=args.person_id,
        db_path=args.db_path,
        output_dir=args.output_dir,
        print_only=args.print_only,
    )


if __name__ == "__main__":
    main()
