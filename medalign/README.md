# MedAlign Data Ingestion

Ingests the MedAlign dataset into a single DuckDB database for use by downstream modules (offline evaluation, patient record extraction, etc.).

## What gets ingested

1. **OMOP CDM tables** -- CSV files (person, note, condition_occurrence, drug_exposure, measurement, procedure_occurrence, visit_occurrence, observation, death, concept, concept_relationship, concept_ancestor)
2. **MedAlign annotation TSVs** -- clinician-generated instructions and model responses

## Prerequisites

- [uv](https://docs.astral.sh/uv/) installed
- Dependencies synced from the repo root: `uv sync`
- The raw MedAlign data files in place under `data/medalign/`:

```
data/medalign/
  tables/                                  # OMOP CDM CSV files
    person.csv
    note.csv
    condition_occurrence.csv
    drug_exposure.csv
    measurement.csv
    visit_occurrence.csv
    procedure_occurrence.csv
    observation.csv
    death.csv
    concept.csv
    concept_relationship.csv
    concept_ancestor.csv
  files/
    medalign_instructions_v1_3/            # Annotation TSVs
      all-instructions-rouge.tsv
      clinician-instruction-responses.tsv
      clinician-reviewed-model-responses.tsv
```

## Usage

From the repository root:

```bash
uv run python medalign/ingest_medalign_to_duckdb.py
```

This creates `data/medalign/medalign.duckdb` with all tables and indexes.

### Options

| Flag               | Default                                              | Description                                  |
| ------------------ | ---------------------------------------------------- | -------------------------------------------- |
| `--tables-path`    | `data/medalign/tables`                               | Directory containing OMOP CDM CSV files      |
| `--files-path`     | `data/medalign/files/medalign_instructions_v1_3`     | Directory containing annotation TSVs         |
| `--db-path`, `-o`  | `data/medalign/medalign.duckdb`                      | Output DuckDB file path                      |
| `--threads`        | `4`                                                  | Number of DuckDB threads                     |
| `--memory-limit`   | `8GB`                                                | DuckDB memory limit                          |
| `--skip-indexes`   | off                                                  | Skip index creation (faster ingest, slower queries) |

### Example with custom paths

```bash
uv run python medalign/ingest_medalign_to_duckdb.py \
  --tables-path /path/to/csv/files \
  --files-path /path/to/tsv/files \
  --db-path /path/to/output.duckdb
```

## Output

On completion, the script prints a summary table of all ingested tables and row counts. The resulting database contains approximately 275 patients and ~46K clinical notes.

## Other scripts

| Script                    | Purpose                                           |
| ------------------------- | ------------------------------------------------- |
| `get_patient_records.py`  | Retrieve structured patient records from DuckDB   |
| `get_patient_notes.py`    | Extract clinical notes for a specific patient     |
| `get_all_patient_notes.py`| Export notes for all patients                     |
