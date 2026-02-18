## CrossCures - EHRShot Data Processing

Tools for ingesting and querying OMOP CDM healthcare data using DuckDB.

### Setup

1. Clone the repository
2. Install `uv`
3. `uv sync`
4. Download the tables.zip and unzip it in `data/` folder
5. Ingest data into local database using `uv run python ehrshots/ingest_to_duckdb.py`. This uses about ~12 GB of disk space and takes about 5 minutes to run.
6. Construct a sample longitudinal patient record using `uv run python ehrshots/patient_longitudinal_data.py`

---

### CLI Reference

#### `ingest_to_duckdb.py` - Ingest CSV data into DuckDB

```bash
uv run python ehrshots/ingest_to_duckdb.py --help
```

| Argument | Short | Default | Description |
|----------|-------|---------|-------------|
| `--data-path` | `-d` | `../data/tables` | Path to directory containing OMOP CDM CSV files |
| `--db-path` | `-o` | `../data/patient_data.duckdb` | Output path for DuckDB database file |
| `--memory-limit` | | `4GB` | Memory limit for DuckDB (e.g., '4GB', '8GB') |
| `--threads` | | `4` | Number of threads for DuckDB to use |

**Examples:**

```bash
# Default ingestion
uv run python ehrshots/ingest_to_duckdb.py

# Custom paths with more resources
uv run python ehrshots/ingest_to_duckdb.py \
  --data-path /path/to/csv/files \
  --db-path /path/to/output.duckdb \
  --threads 8 \
  --memory-limit 16GB
```

---

#### `patient_longitudinal_data.py` - Extract patient longitudinal records

```bash
uv run python ehrshots/patient_longitudinal_data.py --help
```

| Argument | Short | Default | Description |
|----------|-------|---------|-------------|
| `--db-path` | `-d` | `../data/patient_data.duckdb` | Path to DuckDB database file |
| `--person-id` | `-p` | First patient | Patient person_id to extract |
| `--output-dir` | `-o` | None | Directory to export patient record files (JSON/CSV) |
| `--list-patients` | `-l` | | List available patients and exit |
| `--search-condition` | `-s` | | Search for patients with a specific condition |

**Examples:**

```bash
# View first patient's summary
uv run python ehrshots/patient_longitudinal_data.py

# Get a specific patient's record
uv run python ehrshots/patient_longitudinal_data.py --person-id 115970875

# Export patient data to files
uv run python ehrshots/patient_longitudinal_data.py \
  --person-id 115970875 \
  --output-dir ./exports

# List all available patients
uv run python ehrshots/patient_longitudinal_data.py --list-patients

# Search for patients with diabetes
uv run python ehrshots/patient_longitudinal_data.py --search-condition diabetes
```

---

#### `test_duckdb_data.py` - Benchmark query performance

```bash
uv run python ehrshots/test_duckdb_data.py --help
```

| Argument | Short | Default | Description |
|----------|-------|---------|-------------|
| `--db-path` | `-d` | `../data/patient_data.duckdb` | Path to DuckDB database file |
| `--person-id` | `-p` | `115970875` | Patient person_id to use for queries |

**Examples:**

```bash
# Run benchmark with defaults
uv run python ehrshots/test_duckdb_data.py

# Benchmark with a specific patient
uv run python ehrshots/test_duckdb_data.py --person-id 115971632
```

---

### Data Schema

The database uses the [OMOP Common Data Model](https://ohdsi.github.io/CommonDataModel/) with pre-built views for easy access:

| View | Description |
|------|-------------|
| `patient_timeline` | Unified chronological timeline of all patient events |
| `patient_summary` | Demographics and event counts per patient |
| `concept_lookup` | Helper view for looking up concept names |