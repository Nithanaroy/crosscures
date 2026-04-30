"""Assemble model input from DuckDB notes for a given eval case."""
import duckdb
from offline_eval.config import DUCKDB_PATH
from offline_eval.models import CaseInput


def assemble_input(case_id: str, db_path: str = None) -> CaseInput:
    """Retrieve and concatenate notes for a single eval case."""
    db_path = db_path or str(DUCKDB_PATH)
    con = duckdb.connect(db_path, read_only=True)

    case = con.execute(
        "SELECT case_id, patient_id, cutoff_date, case_domain, case_name, "
        "note_ids_included, input_summary FROM eval_cases WHERE case_id = ?",
        [case_id]
    ).fetchone()

    if not case:
        con.close()
        raise ValueError(f"Case {case_id} not found")

    note_ids = case[5]  # BIGINT[] column

    if not note_ids:
        con.close()
        return CaseInput(
            case_id=case[0],
            patient_id=case[1],
            cutoff_date=str(case[2]),
            case_domain=case[3],
            case_name=case[4],
            note_count=0,
            notes_text="",
            char_count=0,
        )

    # Pull notes in chronological order
    placeholders = ",".join(str(nid) for nid in note_ids)
    notes = con.execute(f"""
        SELECT note_id, note_DATE, note_title, note_text
        FROM note
        WHERE note_id IN ({placeholders})
        ORDER BY note_DATETIME ASC
    """).fetchall()

    con.close()

    # Concatenate with clear separators
    parts = []
    for note_id, note_date, title, text in notes:
        header = f"--- Note {note_id} | {note_date} | {title or 'Untitled'} ---"
        parts.append(f"{header}\n{text}\n")

    notes_text = "\n".join(parts)

    return CaseInput(
        case_id=case[0],
        patient_id=case[1],
        cutoff_date=str(case[2]),
        case_domain=case[3],
        case_name=case[4],
        note_count=len(notes),
        notes_text=notes_text,
        char_count=len(notes_text),
    )


def get_all_case_ids(db_path: str = None) -> list:
    """Return all case_ids in order."""
    db_path = db_path or str(DUCKDB_PATH)
    con = duckdb.connect(db_path, read_only=True)
    rows = con.execute("SELECT case_id FROM eval_cases ORDER BY case_id").fetchall()
    con.close()
    return [r[0] for r in rows]


if __name__ == "__main__":
    for cid in get_all_case_ids():
        result = assemble_input(cid)
        print(f"{result['case_id']:20} {result['note_count']} notes, {result['char_count']:,} chars")
