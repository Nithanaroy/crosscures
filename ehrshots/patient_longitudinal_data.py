#!/usr/bin/env python3
"""
Patient Longitudinal Data Constructor (DuckDB Backend)
=======================================================
This script constructs a comprehensive longitudinal health record for patients
using OMOP CDM formatted data stored in DuckDB.

The longitudinal record includes:
- Demographics
- Visit history
- Conditions/Diagnoses
- Medications/Drug exposures
- Procedures
- Measurements (labs, vitals)
- Observations
- Death records (if applicable)

All events are ordered chronologically to provide a complete patient timeline.

Prerequisites:
    Run `python ingest_to_duckdb.py` first to create the DuckDB database.
"""

import duckdb
import pandas as pd
import os
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import warnings
import json

warnings.filterwarnings('ignore')

# Default path to DuckDB database
DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "patient_data.duckdb"


class PatientLongitudinalData:
    """
    Class to construct and manage patient longitudinal health records.
    Uses DuckDB for fast, memory-efficient queries.
    """
    
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        """
        Initialize with path to DuckDB database.
        
        Args:
            db_path: Path to the DuckDB database file
        """
        self.db_path = db_path
        self._conn = None
        
    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """Get or create a DuckDB connection."""
        if self._conn is None:
            if not self.db_path.exists():
                raise FileNotFoundError(
                    f"DuckDB database not found at {self.db_path}. "
                    "Please run 'python ingest_to_duckdb.py' first."
                )
            self._conn = duckdb.connect(str(self.db_path), read_only=True)  # type: ignore[assignment]
        return self._conn  # type: ignore[return-value]
    
    def close(self):
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def get_concept_name(self, concept_id: int) -> str:
        """
        Get the human-readable name for a concept ID.
        
        Args:
            concept_id: OMOP concept ID
            
        Returns:
            Concept name or 'Unknown' if not found
        """
        if pd.isna(concept_id) or concept_id == 0:
            return "Unknown"
        
        conn = self._get_connection()
        result = conn.execute(
            "SELECT concept_name FROM concept WHERE concept_id = ?",
            [int(concept_id)]
        ).fetchone()
        
        if result:
            return result[0]
        return f"Concept_{concept_id}"
    
    def get_patient_demographics(self, person_id: int) -> Dict[str, Any]:
        """
        Get demographic information for a patient.
        
        Args:
            person_id: The patient's person_id
            
        Returns:
            Dictionary with demographic information
        """
        conn = self._get_connection()
        
        result = conn.execute("""
            SELECT 
                p.person_id,
                g.concept_name as gender,
                p.year_of_birth,
                p.month_of_birth,
                p.day_of_birth,
                p.birth_DATETIME,
                p.race_source_value,
                p.ethnicity_source_value
            FROM person p
            LEFT JOIN concept g ON p.gender_concept_id = g.concept_id
            WHERE p.person_id = ?
        """, [int(person_id)]).fetchone()
        
        if result is None:
            return {"error": f"Patient {person_id} not found"}
        
        return {
            "person_id": result[0],
            "gender": result[1] or "Unknown",
            "year_of_birth": result[2],
            "month_of_birth": result[3],
            "day_of_birth": result[4],
            "birth_datetime": str(result[5]) if result[5] else None,
            "race": result[6] or "Unknown",
            "ethnicity": result[7] or "Unknown",
        }
    
    def get_patient_visits(self, person_id: int) -> pd.DataFrame:
        """
        Get all visits/encounters for a patient.
        
        Args:
            person_id: The patient's person_id
            
        Returns:
            DataFrame with visit records sorted by date
        """
        conn = self._get_connection()
        
        df = conn.execute("""
            SELECT 
                v.visit_occurrence_id,
                v.person_id,
                v.visit_concept_id,
                v.visit_start_DATE,
                v.visit_end_DATE,
                v.visit_source_value,
                c.concept_name as visit_type,
                'visit' as event_type
            FROM visit_occurrence v
            LEFT JOIN concept c ON v.visit_concept_id = c.concept_id
            WHERE v.person_id = ?
            ORDER BY v.visit_start_DATE
        """, [int(person_id)]).df()
        
        return df
    
    def get_patient_conditions(self, person_id: int) -> pd.DataFrame:
        """
        Get all conditions/diagnoses for a patient.
        
        Args:
            person_id: The patient's person_id
            
        Returns:
            DataFrame with condition records sorted by date
        """
        conn = self._get_connection()
        
        df = conn.execute("""
            SELECT 
                co.condition_occurrence_id,
                co.person_id,
                co.condition_concept_id,
                co.condition_start_DATE,
                co.condition_end_DATE,
                co.condition_source_value,
                co.visit_occurrence_id,
                c.concept_name as condition_name,
                'condition' as event_type
            FROM condition_occurrence co
            LEFT JOIN concept c ON co.condition_concept_id = c.concept_id
            WHERE co.person_id = ?
            ORDER BY co.condition_start_DATE
        """, [int(person_id)]).df()
        
        return df
    
    def get_patient_drugs(self, person_id: int) -> pd.DataFrame:
        """
        Get all drug exposures/medications for a patient.
        
        Args:
            person_id: The patient's person_id
            
        Returns:
            DataFrame with drug exposure records sorted by date
        """
        conn = self._get_connection()
        
        df = conn.execute("""
            SELECT 
                de.drug_exposure_id,
                de.person_id,
                de.drug_concept_id,
                de.drug_exposure_start_DATE,
                de.drug_exposure_end_DATE,
                de.drug_source_value,
                de.quantity,
                de.days_supply,
                de.route_source_value,
                de.visit_occurrence_id,
                c.concept_name as drug_name,
                'drug' as event_type
            FROM drug_exposure de
            LEFT JOIN concept c ON de.drug_concept_id = c.concept_id
            WHERE de.person_id = ?
            ORDER BY de.drug_exposure_start_DATE
        """, [int(person_id)]).df()
        
        return df
    
    def get_patient_procedures(self, person_id: int) -> pd.DataFrame:
        """
        Get all procedures for a patient.
        
        Args:
            person_id: The patient's person_id
            
        Returns:
            DataFrame with procedure records sorted by date
        """
        conn = self._get_connection()
        
        df = conn.execute("""
            SELECT 
                po.procedure_occurrence_id,
                po.person_id,
                po.procedure_concept_id,
                po.procedure_DATE,
                po.procedure_source_value,
                po.visit_occurrence_id,
                c.concept_name as procedure_name,
                'procedure' as event_type
            FROM procedure_occurrence po
            LEFT JOIN concept c ON po.procedure_concept_id = c.concept_id
            WHERE po.person_id = ?
            ORDER BY po.procedure_DATE
        """, [int(person_id)]).df()
        
        return df
    
    def get_patient_measurements(self, person_id: int) -> pd.DataFrame:
        """
        Get all measurements (labs, vitals) for a patient.
        
        Args:
            person_id: The patient's person_id
            
        Returns:
            DataFrame with measurement records sorted by date
        """
        conn = self._get_connection()
        
        df = conn.execute("""
            SELECT 
                m.measurement_id,
                m.person_id,
                m.measurement_concept_id,
                m.measurement_DATE,
                m.measurement_DATETIME,
                m.value_as_number,
                m.value_source_value,
                m.unit_source_value,
                m.measurement_source_value,
                m.visit_occurrence_id,
                c.concept_name as measurement_name,
                'measurement' as event_type
            FROM measurement m
            LEFT JOIN concept c ON m.measurement_concept_id = c.concept_id
            WHERE m.person_id = ?
            ORDER BY m.measurement_DATE
        """, [int(person_id)]).df()
        
        return df
    
    def get_patient_observations(self, person_id: int) -> pd.DataFrame:
        """
        Get all observations for a patient.
        
        Args:
            person_id: The patient's person_id
            
        Returns:
            DataFrame with observation records sorted by date
        """
        conn = self._get_connection()
        
        df = conn.execute("""
            SELECT 
                o.observation_id,
                o.person_id,
                o.observation_concept_id,
                o.observation_DATE,
                o.value_as_number,
                o.value_as_string,
                o.observation_source_value,
                o.visit_occurrence_id,
                c.concept_name as observation_name,
                'observation' as event_type
            FROM observation o
            LEFT JOIN concept c ON o.observation_concept_id = c.concept_id
            WHERE o.person_id = ?
            ORDER BY o.observation_DATE
        """, [int(person_id)]).df()
        
        return df
    
    def get_patient_death(self, person_id: int) -> Optional[Dict[str, Any]]:
        """
        Get death record for a patient if exists.
        
        Args:
            person_id: The patient's person_id
            
        Returns:
            Dictionary with death information or None
        """
        conn = self._get_connection()
        
        result = conn.execute("""
            SELECT 
                d.death_DATE,
                d.death_DATETIME,
                c.concept_name as cause,
                d.cause_source_value
            FROM death d
            LEFT JOIN concept c ON d.cause_concept_id = c.concept_id
            WHERE d.person_id = ?
        """, [int(person_id)]).fetchone()
        
        if result is None:
            return None
        
        return {
            "death_date": str(result[0]) if result[0] else None,
            "death_datetime": str(result[1]) if result[1] else None,
            "cause": result[2] or "Unknown",
            "cause_source_value": result[3]
        }
    
    def build_longitudinal_timeline(self, person_id: int) -> pd.DataFrame:
        """
        Build a unified chronological timeline of all patient events.
        Uses the pre-built patient_timeline view for optimal performance.
        
        Args:
            person_id: The patient's person_id
            
        Returns:
            DataFrame with all events sorted chronologically
        """
        conn = self._get_connection()
        
        df = conn.execute("""
            SELECT 
                event_date as date,
                event_type,
                event_id,
                concept_name as description,
                source_value,
                value_as_number as value
            FROM patient_timeline
            WHERE person_id = ?
            ORDER BY event_date
        """, [int(person_id)]).df()
        
        return df
    
    def get_patient_summary(self, person_id: int) -> Dict[str, Any]:
        """
        Get summary statistics for a patient using the pre-built view.
        
        Args:
            person_id: The patient's person_id
            
        Returns:
            Dictionary with summary statistics
        """
        conn = self._get_connection()
        
        result = conn.execute("""
            SELECT *
            FROM patient_summary
            WHERE person_id = ?
        """, [int(person_id)]).fetchone()
        
        if result is None:
            return {"error": f"Patient {person_id} not found"}
        
        columns = ['person_id', 'year_of_birth', 'gender', 'race', 'ethnicity',
                   'death_DATE', 'visit_count', 'condition_count', 'drug_count',
                   'procedure_count', 'measurement_count', 'observation_count',
                   'first_visit', 'last_visit']
        
        return dict(zip(columns, result))
    
    def get_complete_patient_record(self, person_id: int) -> Dict[str, Any]:
        """
        Get a complete longitudinal record for a patient.
        
        Args:
            person_id: The patient's person_id
            
        Returns:
            Dictionary containing all patient data
        """
        print(f"\n{'='*60}")
        print(f"Building complete record for patient {person_id}")
        print('='*60)
        
        # Demographics
        print("  Loading demographics...")
        demographics = self.get_patient_demographics(person_id)
        if "error" in demographics:
            return demographics
        
        # Death record
        print("  Checking death records...")
        death = self.get_patient_death(person_id)
        
        # Build timeline (uses optimized view)
        print("  Building timeline...")
        timeline = self.build_longitudinal_timeline(person_id)
        
        # Summary statistics
        print("  Calculating summary...")
        summary = {
            "total_events": len(timeline),
            "event_counts": timeline['event_type'].value_counts().to_dict() if len(timeline) > 0 else {},
            "date_range": {
                "first_event": str(timeline['date'].min()) if len(timeline) > 0 else None,
                "last_event": str(timeline['date'].max()) if len(timeline) > 0 else None
            }
        }
        
        print(f"  Found {len(timeline)} total events")
        
        return {
            "demographics": demographics,
            "death": death,
            "summary": summary,
            "timeline": timeline
        }
    
    def export_patient_record(self, person_id: int, output_dir: str = "output") -> str:
        """
        Export a patient's complete longitudinal record to files.
        
        Args:
            person_id: The patient's person_id
            output_dir: Directory to save output files
            
        Returns:
            Path to the output directory
        """
        # Create output directory
        patient_dir = os.path.join(output_dir, f"patient_{person_id}")
        os.makedirs(patient_dir, exist_ok=True)
        
        # Get complete record
        record = self.get_complete_patient_record(person_id)
        
        if "error" in record:
            print(record["error"])
            return ""
        
        # Save demographics
        with open(os.path.join(patient_dir, "demographics.json"), 'w') as f:
            json.dump(record["demographics"], f, indent=2, default=str)
        
        # Save death record if exists
        if record["death"]:
            with open(os.path.join(patient_dir, "death.json"), 'w') as f:
                json.dump(record["death"], f, indent=2, default=str)
        
        # Save summary
        with open(os.path.join(patient_dir, "summary.json"), 'w') as f:
            json.dump(record["summary"], f, indent=2, default=str)
        
        # Save timeline
        if len(record["timeline"]) > 0:
            record["timeline"].to_csv(
                os.path.join(patient_dir, "timeline.csv"), 
                index=False
            )
        
        print(f"\nExported patient record to: {patient_dir}")
        return patient_dir
    
    def list_patients(self, limit: int = 10) -> pd.DataFrame:
        """
        List available patients in the dataset.
        
        Args:
            limit: Maximum number of patients to return
            
        Returns:
            DataFrame with patient IDs and basic info
        """
        conn = self._get_connection()
        
        return conn.execute(f"""
            SELECT person_id, year_of_birth, gender_source_value
            FROM person
            LIMIT {limit}
        """).df()
    
    def search_patients_by_condition(self, condition_name: str, limit: int = 10) -> pd.DataFrame:
        """
        Search for patients with a specific condition.
        
        Args:
            condition_name: Condition name to search for (case-insensitive, partial match)
            limit: Maximum number of patients to return
            
        Returns:
            DataFrame with matching patients
        """
        conn = self._get_connection()
        
        return conn.execute(f"""
            SELECT DISTINCT 
                p.person_id, 
                p.year_of_birth, 
                p.gender_source_value,
                c.concept_name as condition
            FROM condition_occurrence co
            JOIN person p ON co.person_id = p.person_id
            JOIN concept c ON co.condition_concept_id = c.concept_id
            WHERE c.concept_name ILIKE '%' || ? || '%'
            LIMIT {limit}
        """, [condition_name]).df()
    
    def get_patient_summary_report(self, person_id: int, complete: bool = False) -> str:
        """
        Generate a human-readable summary report for a patient.
        
        Args:
            person_id: The patient's person_id
            complete: If True, include all events; if False, show only last 10 events
            
        Returns:
            Formatted string report
        """
        record = self.get_complete_patient_record(person_id)
        
        if "error" in record:
            return record["error"]
        
        demo = record["demographics"]
        summary = record["summary"]
        timeline = record["timeline"]
        
        # Build report
        report = []
        report.append("\n" + "="*70)
        report.append(f"PATIENT LONGITUDINAL SUMMARY REPORT")
        report.append("="*70)
        
        # Demographics section
        report.append("\n[DEMOGRAPHICS]")
        report.append("-"*40)
        report.append(f"  Patient ID: {demo['person_id']}")
        report.append(f"  Gender: {demo['gender']}")
        report.append(f"  Birth Date: {demo.get('birth_datetime', 'Unknown')}")
        report.append(f"  Race: {demo['race']}")
        report.append(f"  Ethnicity: {demo['ethnicity']}")
        
        # Death info if applicable
        if record["death"]:
            report.append(f"\n[DECEASED] {record['death']['death_date']}")
        
        # Summary statistics
        report.append("\n[SUMMARY]")
        report.append("-"*40)
        report.append(f"  Total Events: {summary['total_events']}")
        report.append(f"  Date Range: {summary['date_range']['first_event']} to {summary['date_range']['last_event']}")
        
        report.append("\n  Event Breakdown:")
        for event_type, count in summary['event_counts'].items():
            label = {
                'visit': '[V]',
                'condition': '[C]',
                'drug': '[D]',
                'procedure': '[P]',
                'measurement': '[M]',
                'observation': '[O]'
            }.get(event_type, '*')
            report.append(f"    {label} {event_type.capitalize()}: {count}")
        
        # Events section
        if len(timeline) > 0:
            if complete:
                report.append(f"\n[ALL EVENTS] ({len(timeline)} total)")
                report.append("-"*40)
                for _, event in timeline.iterrows():
                    date_str = str(event['date'])[:10] if pd.notna(event['date']) else 'Unknown'
                    report.append(f"  [{date_str}] {event['event_type'].upper()}: {event['description']}")
            else:
                report.append("\n[RECENT EVENTS] (Last 10)")
                report.append("-"*40)
                recent = timeline.tail(10)
                for _, event in recent.iterrows():
                    date_str = str(event['date'])[:10] if pd.notna(event['date']) else 'Unknown'
                    report.append(f"  [{date_str}] {event['event_type'].upper()}: {event['description']}")
        
        report.append("\n" + "="*70)
        
        return "\n".join(report)


def main(db_path: Path = DEFAULT_DB_PATH, person_id: int = None, output_dir: str = None, complete: bool = False, output_file: str = None):  # type: ignore[assignment]
    """Main function to demonstrate the longitudinal data extraction."""
    
    print("Patient Longitudinal Data Constructor (DuckDB Backend)")
    print("=" * 55 + "\n")
    
    # Initialize the extractor
    with PatientLongitudinalData(db_path=db_path) as extractor:
        # List some patients
        print("Available patients (first 10):")
        patients = extractor.list_patients(10)
        print(patients.to_string(index=False))
        
        # Use provided person_id or default to first patient
        if person_id is None and len(patients) > 0:
            person_id = patients.iloc[0]['person_id']
        
        if person_id is not None:
            # Generate and print summary report
            report = extractor.get_patient_summary_report(person_id, complete=complete)
            if not complete:
                # too long to print the entire report to stdout
                print(report)
            
            # Save to output file if specified
            if output_file:
                with open(output_file, 'w') as f:
                    f.write(report)
                print(f"\n[OK] Report saved to: {output_file}")
            
            # Export if output directory specified
            if output_dir:
                output_path = extractor.export_patient_record(person_id, output_dir)
                if output_path:
                    print(f"\n[OK] Complete record exported to: {output_path}")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract longitudinal patient data from OMOP CDM DuckDB database.",
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
        default=None,
        help="Patient person_id to extract (default: first patient in database)"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default=None,
        help="Directory to export patient record files (JSON/CSV)"
    )
    parser.add_argument(
        "--output", "-f",
        type=str,
        default=None,
        help="Output file to save the patient summary report (txt format)"
    )
    parser.add_argument(
        "--complete",
        action="store_true",
        help="Print all events instead of just the last 10"
    )
    parser.add_argument(
        "--list-patients", "-l",
        action="store_true",
        help="List available patients and exit"
    )
    parser.add_argument(
        "--search-condition", "-s",
        type=str,
        default=None,
        help="Search for patients with a specific condition (partial match)"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    
    # Validate that --output is provided when --complete is used
    if args.complete and not args.output:
        print("Error: --output flag is required when --complete flag is used")
        print("Usage: python patient_longitudinal_data.py --person-id <id> --complete --output <file>")
        exit(1)
    
    if args.list_patients:
        with PatientLongitudinalData(db_path=args.db_path) as extractor:
            print("Available patients:")
            print(extractor.list_patients(50).to_string(index=False))
    elif args.search_condition:
        with PatientLongitudinalData(db_path=args.db_path) as extractor:
            print(f"Patients with condition matching '{args.search_condition}':")
            print(extractor.search_patients_by_condition(args.search_condition, limit=20).to_string(index=False))
    else:
        main(db_path=args.db_path, person_id=args.person_id, output_dir=args.output_dir, complete=args.complete, output_file=args.output)
