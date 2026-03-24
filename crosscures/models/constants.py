from pathlib import Path

PROJECT_HOME = Path(__file__).parents[2]
DATA_DIR = PROJECT_HOME / "data"
DUCKDB_PATH = DATA_DIR / "patient_data.duckdb"