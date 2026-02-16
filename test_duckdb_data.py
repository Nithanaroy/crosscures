#!/usr/bin/env python3
"""Quick benchmark of DuckDB query performance."""

import duckdb
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "patient_data.duckdb"
conn = duckdb.connect(str(DB_PATH), read_only=True)

# Test 1: Get patient timeline
print('🔍 Query 1: Get full patient timeline (all events)')
start = time.time()
df = conn.execute("""
    SELECT event_date, event_type, concept_name, source_value
    FROM patient_timeline
    WHERE person_id = 115970875
    ORDER BY event_date
""").df()
print(f'   Results: {len(df):,} events in {(time.time()-start)*1000:.1f}ms')
print(df.head(5).to_string())

print()

# Test 2: Patient summary
print('🔍 Query 2: Get patient summary')
start = time.time()
df = conn.execute('SELECT * FROM patient_summary WHERE person_id = 115970875').df()
print(f'   Results in {(time.time()-start)*1000:.1f}ms')
print(df.to_string())

print()

# Test 3: Search across 40M measurements
print('🔍 Query 3: Search measurements for a patient (40M row table)')
start = time.time()
df = conn.execute("""
    SELECT measurement_DATE, c.concept_name, value_as_number, unit_source_value
    FROM measurement m
    JOIN concept c ON m.measurement_concept_id = c.concept_id
    WHERE m.person_id = 115970875
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
