## CrossCures

### Setup

1. Clone the repository
2. Install `uv`
3. `uv sync`
4. Download the tables.zip and unzip it in data/ folder
5. Ingest data into local database using `uv run python ingest_to_duckdb.py`. This uses about ~12 GB of disk space and takes about 5 minutes to run.
6. Construct a sample longitudinal patient record using `uv run python patient_longitudinal_data.py`