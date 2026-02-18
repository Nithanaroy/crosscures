#!/usr/bin/env python3
"""Quick benchmark of DuckDB query performance."""

import duckdb
import time
import argparse
from pathlib import Path

# Default configuration
DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "patient_data.duckdb"
DEFAULT_PERSON_ID = 115970875


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Benchmark DuckDB query performance on OMOP CDM data.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--db-path", "-d",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to DuckDB database file"
    )
    parser.add_argument(
        "--person-id", "-p",
        type=int,
        default=DEFAULT_PERSON_ID,
        help="Patient person_id to use for queries"
    )
    return parser.parse_args()


def main(db_path: Path, person_id: int):
    """Run benchmark queries."""
    conn = duckdb.connect(str(db_path), read_only=True)
    
    # Test 1: Get patient timeline
    print('🔍 Query 1: Get full patient timeline (all events)')
    start = time.time()
    df = conn.execute(f"""
        SELECT event_date, event_type, concept_name, source_value
        FROM patient_timeline
        WHERE person_id = {person_id}
        ORDER BY event_date
    """).df()
    print(f'   Results: {len(df):,} events in {(time.time()-start)*1000:.1f}ms')
    print(df.head(5).to_string())

    print()

    # Test 2: Patient summary
    print('🔍 Query 2: Get patient summary')
    start = time.time()
    df = conn.execute(f'SELECT * FROM patient_summary WHERE person_id = {person_id}').df()
    print(f'   Results in {(time.time()-start)*1000:.1f}ms')
    print(df.to_string())

    print()

    # Test 3: Search across 40M measurements
    print('🔍 Query 3: Search measurements for a patient (40M row table)')
    start = time.time()
    df = conn.execute(f"""
        SELECT measurement_DATE, c.concept_name, value_as_number, unit_source_value
        FROM measurement m
        JOIN concept c ON m.measurement_concept_id = c.concept_id
        WHERE m.person_id = {person_id}
        ORDER BY measurement_DATE DESC
        LIMIT 10
    """).df()
    print(f'   Results in {(time.time()-start)*1000:.1f}ms')
    print(df.to_string())

    print()

    # Test 4: Count all events per type across entire dataset
    print('🔍 Query 4: Aggregate - count events by type (248M rows)')
    start = time.time()
    df = conn.execute("""
        SELECT event_type, COUNT(*) as count
        FROM patient_timeline
        GROUP BY event_type
        ORDER BY count DESC
    """).df()
    print(f'   Results in {(time.time()-start)*1000:.1f}ms')
    print(df.to_string())

    conn.close()


if __name__ == "__main__":
    args = parse_args()
    main(db_path=args.db_path, person_id=args.person_id)
