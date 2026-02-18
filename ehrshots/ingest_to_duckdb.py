#!/usr/bin/env python3
"""
DuckDB Ingestion Script for OMOP CDM Data
==========================================
This script ingests all CSV files from data/tables into a DuckDB database,
creates optimized indexes for fast patient-level queries, and sets up
views for common longitudinal data access patterns.

Usage:
    python ingest_to_duckdb.py

The script will:
1. Create a new DuckDB database file (patient_data.duckdb)
2. Import all CSV files from data/tables/
3. Create indexes on person_id and date columns for fast queries
4. Create helpful views for longitudinal data access
5. Print statistics and sample queries
"""

import duckdb
import os
import time
import argparse
from pathlib import Path
from typing import Dict, List, Tuple

# Default Configuration
DEFAULT_DATA_PATH = Path(__file__).parent.parent / "data" / "tables"
DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "patient_data.duckdb"

# Define indexes for each table: table_name -> list of (column(s), index_name)
# These are optimized for patient longitudinal queries
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
}


def get_csv_files(data_path: Path) -> List[Path]:
    """Get all CSV files in the data directory."""
    return sorted(data_path.glob("*.csv"))


def get_table_name(csv_path: Path) -> str:
    """Convert CSV filename to table name."""
    return csv_path.stem.lower()


def format_size(size_bytes: float) -> str:
    """Format bytes to human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def format_time(seconds: float) -> str:
    """Format seconds to human-readable time."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"


def ingest_csv_to_duckdb(conn: duckdb.DuckDBPyConnection, csv_path: Path) -> Tuple[str, int, float]:
    """
    Ingest a single CSV file into DuckDB.
    
    Returns:
        Tuple of (table_name, row_count, time_taken)
    """
    table_name = get_table_name(csv_path)
    file_size = csv_path.stat().st_size
    
    print(f"  -> Importing {table_name} ({format_size(file_size)})...", end=" ", flush=True)
    
    start_time = time.time()
    
    # Use DuckDB's native CSV reader - very fast and memory efficient
    conn.execute(f"""
        CREATE OR REPLACE TABLE {table_name} AS 
        SELECT * FROM read_csv_auto(
            '{csv_path}',
            header=true,
            ignore_errors=true,
            sample_size=100000
        )
    """)
    
    # Get row count
    result = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    row_count = result[0] if result else 0
    
    elapsed = time.time() - start_time
    print(f"[OK] {row_count:,} rows ({format_time(elapsed)})")
    
    return table_name, row_count, elapsed


def create_indexes(conn: duckdb.DuckDBPyConnection, table_name: str) -> int:
    """
    Create indexes for a table if defined.
    
    Returns:
        Number of indexes created
    """
    if table_name not in TABLE_INDEXES:
        return 0
    
    indexes_created = 0
    for columns, index_name in TABLE_INDEXES[table_name]:
        try:
            # Check if columns exist in table
            conn.execute(f"""
                CREATE INDEX IF NOT EXISTS {index_name} 
                ON {table_name} ({columns})
            """)
            indexes_created += 1
        except Exception as e:
            # Column might not exist in this dataset
            print(f"    [WARN] Could not create index {index_name}: {e}")
    
    return indexes_created


def create_longitudinal_views(conn: duckdb.DuckDBPyConnection):
    """Create helpful views for longitudinal data access."""
    
    print("\n[VIEWS] Creating longitudinal views...")
    
    # View: Patient timeline with all events unified
    conn.execute("""
        CREATE OR REPLACE VIEW patient_timeline AS
        WITH all_events AS (
            -- Visits
            SELECT 
                person_id,
                visit_start_DATE as event_date,
                'visit' as event_type,
                visit_occurrence_id as event_id,
                visit_concept_id as concept_id,
                NULL as value_as_number,
                visit_source_value as source_value
            FROM visit_occurrence
            
            UNION ALL
            
            -- Conditions
            SELECT 
                person_id,
                condition_start_DATE as event_date,
                'condition' as event_type,
                condition_occurrence_id as event_id,
                condition_concept_id as concept_id,
                NULL as value_as_number,
                condition_source_value as source_value
            FROM condition_occurrence
            
            UNION ALL
            
            -- Drugs
            SELECT 
                person_id,
                drug_exposure_start_DATE as event_date,
                'drug' as event_type,
                drug_exposure_id as event_id,
                drug_concept_id as concept_id,
                quantity as value_as_number,
                drug_source_value as source_value
            FROM drug_exposure
            
            UNION ALL
            
            -- Procedures
            SELECT 
                person_id,
                procedure_DATE as event_date,
                'procedure' as event_type,
                procedure_occurrence_id as event_id,
                procedure_concept_id as concept_id,
                NULL as value_as_number,
                procedure_source_value as source_value
            FROM procedure_occurrence
            
            UNION ALL
            
            -- Measurements
            SELECT 
                person_id,
                measurement_DATE as event_date,
                'measurement' as event_type,
                measurement_id as event_id,
                measurement_concept_id as concept_id,
                value_as_number,
                measurement_source_value as source_value
            FROM measurement
            
            UNION ALL
            
            -- Observations
            SELECT 
                person_id,
                observation_DATE as event_date,
                'observation' as event_type,
                observation_id as event_id,
                observation_concept_id as concept_id,
                value_as_number,
                observation_source_value as source_value
            FROM observation
        )
        SELECT 
            e.*,
            c.concept_name,
            c.vocabulary_id
        FROM all_events e
        LEFT JOIN concept c ON e.concept_id = c.concept_id
    """)
    print("  [OK] Created view: patient_timeline")
    
    # View: Patient summary statistics
    conn.execute("""
        CREATE OR REPLACE VIEW patient_summary AS
        SELECT 
            p.person_id,
            p.year_of_birth,
            p.gender_source_value as gender,
            p.race_source_value as race,
            p.ethnicity_source_value as ethnicity,
            d.death_DATE,
            (SELECT COUNT(*) FROM visit_occurrence v WHERE v.person_id = p.person_id) as visit_count,
            (SELECT COUNT(*) FROM condition_occurrence c WHERE c.person_id = p.person_id) as condition_count,
            (SELECT COUNT(*) FROM drug_exposure dr WHERE dr.person_id = p.person_id) as drug_count,
            (SELECT COUNT(*) FROM procedure_occurrence pr WHERE pr.person_id = p.person_id) as procedure_count,
            (SELECT COUNT(*) FROM measurement m WHERE m.person_id = p.person_id) as measurement_count,
            (SELECT COUNT(*) FROM observation o WHERE o.person_id = p.person_id) as observation_count,
            (SELECT MIN(visit_start_DATE) FROM visit_occurrence v WHERE v.person_id = p.person_id) as first_visit,
            (SELECT MAX(visit_start_DATE) FROM visit_occurrence v WHERE v.person_id = p.person_id) as last_visit
        FROM person p
        LEFT JOIN death d ON p.person_id = d.person_id
    """)
    print("  [OK] Created view: patient_summary")
    
    # View: Concept lookup helper
    conn.execute("""
        CREATE OR REPLACE VIEW concept_lookup AS
        SELECT 
            concept_id,
            concept_name,
            domain_id,
            vocabulary_id,
            concept_class_id,
            concept_code
        FROM concept
        WHERE concept_id != 0
    """)
    print("  [OK] Created view: concept_lookup")


def print_database_stats(conn: duckdb.DuckDBPyConnection, db_path: Path):
    """Print summary statistics about the database."""
    
    print("\n" + "="*60)
    print("DATABASE STATISTICS")
    print("="*60)
    
    # Get all tables
    tables = conn.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'main' AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """).fetchall()
    
    total_rows = 0
    print(f"\n{'Table':<30} {'Rows':>15}")
    print("-"*47)
    
    for (table_name,) in tables:
        result = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
        count = result[0] if result else 0
        total_rows += count
        print(f"{table_name:<30} {count:>15,}")
    
    print("-"*47)
    print(f"{'TOTAL':<30} {total_rows:>15,}")
    
    # Database file size
    if db_path.exists():
        db_size = db_path.stat().st_size
        print(f"\n[SIZE] Database file size: {format_size(db_size)}")


def print_sample_queries():
    """Print example queries for using the database."""
    
    print("\n" + "="*60)
    print("SAMPLE QUERIES")
    print("="*60)
    
    queries = [
        ("Get patient demographics", """
SELECT * FROM person WHERE person_id = 115970875;
"""),
        ("Get patient timeline (all events)", """
SELECT event_date, event_type, concept_name, value_as_number, source_value
FROM patient_timeline
WHERE person_id = 115970875
ORDER BY event_date;
"""),
        ("Get patient summary", """
SELECT * FROM patient_summary WHERE person_id = 115970875;
"""),
        ("Count events by type for a patient", """
SELECT event_type, COUNT(*) as count
FROM patient_timeline
WHERE person_id = 115970875
GROUP BY event_type
ORDER BY count DESC;
"""),
        ("Find patients with a specific condition", """
SELECT DISTINCT c.person_id, p.year_of_birth, co.concept_name
FROM condition_occurrence c
JOIN person p ON c.person_id = p.person_id
JOIN concept co ON c.condition_concept_id = co.concept_id
WHERE co.concept_name ILIKE '%diabetes%'
LIMIT 10;
"""),
        ("Get all measurements for a patient in date range", """
SELECT m.measurement_DATE, c.concept_name, m.value_as_number, m.unit_source_value
FROM measurement m
JOIN concept c ON m.measurement_concept_id = c.concept_id
WHERE m.person_id = 115970875
  AND m.measurement_DATE BETWEEN '2020-01-01' AND '2020-12-31'
ORDER BY m.measurement_DATE;
"""),
    ]
    
    for title, query in queries:
        print(f"\n-- {title}")
        print(query.strip())


def main(data_path: Path = DEFAULT_DATA_PATH, db_path: Path = DEFAULT_DB_PATH, 
         threads: int = 4, memory_limit: str = "4GB"):
    """Main ingestion function."""
    
    print("="*60)
    print("DuckDB Ingestion Script for OMOP CDM Data")
    print("="*60)
    
    # Check data directory exists
    if not data_path.exists():
        print(f"[ERROR] Data directory not found: {data_path}")
        return
    
    # Get all CSV files
    csv_files = get_csv_files(data_path)
    if not csv_files:
        print(f"[ERROR] No CSV files found in {data_path}")
        return
    
    print(f"\n[INFO] Found {len(csv_files)} CSV files in {data_path}")
    print(f"[INFO] Creating database: {db_path}")
    
    # Remove existing database for fresh start
    if db_path.exists():
        print(f"[WARN] Removing existing database...")
        db_path.unlink()
    
    # Connect to DuckDB
    conn = duckdb.connect(str(db_path))
    
    # Configure DuckDB for optimal performance
    conn.execute(f"SET threads TO {threads}")
    conn.execute(f"SET memory_limit = '{memory_limit}'")
    
    print("\n[IMPORT] Importing tables...")
    total_start = time.time()
    total_rows = 0
    table_stats = []
    
    # Import all CSV files
    for csv_path in csv_files:
        try:
            table_name, row_count, elapsed = ingest_csv_to_duckdb(conn, csv_path)
            table_stats.append((table_name, row_count, elapsed))
            total_rows += row_count
        except Exception as e:
            print(f"  [ERROR] Failed to import {csv_path.name}: {e}")
    
    total_import_time = time.time() - total_start
    print(f"\n[OK] Imported {total_rows:,} total rows in {format_time(total_import_time)}")
    
    # Create indexes
    print("\n[INDEX] Creating indexes...")
    index_start = time.time()
    total_indexes = 0
    
    for table_name, _, _ in table_stats:
        indexes_created = create_indexes(conn, table_name)
        if indexes_created > 0:
            print(f"  [OK] {table_name}: {indexes_created} indexes")
            total_indexes += indexes_created
    
    index_time = time.time() - index_start
    print(f"\n[OK] Created {total_indexes} indexes in {format_time(index_time)}")
    
    # Create views
    create_longitudinal_views(conn)
    
    # Analyze tables for query optimization
    print("\n[ANALYZE] Analyzing tables for query optimization...")
    conn.execute("ANALYZE")
    print("  [OK] Analysis complete")
    
    # Print statistics
    print_database_stats(conn, db_path)
    
    # Print sample queries
    print_sample_queries()
    
    # Close connection
    conn.close()
    
    total_time = time.time() - total_start
    print("\n" + "="*60)
    print(f"[DONE] INGESTION COMPLETE in {format_time(total_time)}")
    print("="*60)
    print(f"\nDatabase ready at: {db_path}")
    print("\nTo use in Python:")
    print(f'''
import duckdb
conn = duckdb.connect('{db_path}')

# Get patient timeline
df = conn.execute(\'\'\'
    SELECT * FROM patient_timeline 
    WHERE person_id = 115970875 
    ORDER BY event_date
\'\'\').df()
print(df)
''')


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Ingest OMOP CDM CSV files into DuckDB for fast querying.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--data-path", "-d",
        type=Path,
        default=DEFAULT_DATA_PATH,
        help="Path to directory containing OMOP CDM CSV files"
    )
    parser.add_argument(
        "--db-path", "-o",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Output path for DuckDB database file"
    )
    parser.add_argument(
        "--memory-limit",
        type=str,
        default="4GB",
        help="Memory limit for DuckDB (e.g., '4GB', '8GB')"
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=4,
        help="Number of threads for DuckDB to use"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(
        data_path=args.data_path, 
        db_path=args.db_path,
        threads=args.threads,
        memory_limit=args.memory_limit
    )
