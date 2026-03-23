"""
Data providers and session storage (Repository implementations)
"""
from crosscures.repositories.base import PatientDataProvider
from crosscures.models import PatientProfile, PatientCondition
from typing import Optional, List
from datetime import datetime
import uuid


class MockPatientDataProvider(PatientDataProvider):
    """Mock patient data for demo purposes"""
    
    MOCK_PATIENTS = {
        "PAT001": PatientProfile(
            patient_id="PAT001",
            name="John Smith",
            conditions=[
                PatientCondition(
                    condition_name="Type 2 Diabetes",
                    condition_code="E11.9",
                    onset_date=datetime(2018, 6, 15),
                ),
                PatientCondition(
                    condition_name="Hypertension",
                    condition_code="I10",
                    onset_date=datetime(2015, 3, 20),
                ),
            ],
            current_medications=["Metformin 1000mg", "Lisinopril 10mg"],
        ),
        "PAT002": PatientProfile(
            patient_id="PAT002",
            name="Sarah Johnson",
            conditions=[
                PatientCondition(
                    condition_name="Coronary Artery Disease",
                    condition_code="I25.10",
                    onset_date=datetime(2020, 1, 10),
                ),
                PatientCondition(
                    condition_name="Hypertension",
                    condition_code="I10",
                    onset_date=datetime(2019, 5, 12),
                ),
            ],
            current_medications=["Atorvastatin 40mg", "Aspirin 81mg", "Metoprolol 50mg"],
        ),
        "PAT003": PatientProfile(
            patient_id="PAT003",
            name="Michael Chen",
            conditions=[
                PatientCondition(
                    condition_name="COPD",
                    condition_code="J44.9",
                    onset_date=datetime(2016, 11, 3),
                ),
                PatientCondition(
                    condition_name="Asthma",
                    condition_code="J45.9",
                    onset_date=datetime(2010, 7, 22),
                ),
            ],
            current_medications=["Albuterol inhaler", "Fluticasone/Salmeterol inhaler"],
        ),
        "PAT004": PatientProfile(
            patient_id="PAT004",
            name="Emily Davis",
            conditions=[],  # No significant conditions
            current_medications=[],
        ),
    }
    
    def get_patient(self, patient_id: str) -> Optional[PatientProfile]:
        """Retrieve mock patient by ID"""
        return self.MOCK_PATIENTS.get(patient_id)
    
    def list_all_patients(self) -> List[PatientProfile]:
        """List all mock patients"""
        return list(self.MOCK_PATIENTS.values())


class DuckDBPatientDataProvider(PatientDataProvider):
    """Load patient data from DuckDB"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._connection = None
    
    def get_connection(self):
        """Lazy load DuckDB connection"""
        if self._connection is None:
            import duckdb
            self._connection = duckdb.connect(self.db_path, read_only=True)
        return self._connection
    
    def get_patient(self, patient_id: str) -> Optional[PatientProfile]:
        """
        Query patient from DuckDB
        Assumes tables: person, condition_occurrence, drug_exposure
        """
        try:
            conn = self.get_connection()
            
            # Get patient basic info
            patient_query = f"""
            SELECT person_id, birth_date, gender_concept_id
            FROM person
            WHERE person_id = {patient_id}
            LIMIT 1
            """
            person_result = conn.execute(patient_query).fetchall()
            
            if not person_result:
                return None
            
            person_id = person_result[0][0]
            
            # Get conditions
            conditions_query = f"""
            SELECT DISTINCT 
                c.concept_name,
                co.condition_concept_id,
                co.condition_start_date
            FROM condition_occurrence co
            JOIN concept c ON co.condition_concept_id = c.concept_id
            WHERE co.person_id = {person_id} AND co.condition_status_concept_id = 0
            ORDER BY co.condition_start_date DESC
            """
            conditions_result = conn.execute(conditions_query).fetchall()
            
            conditions = [
                PatientCondition(
                    condition_name=row[0],
                    condition_code=str(row[1]),
                    onset_date=row[2] if row[2] else None,
                )
                for row in conditions_result
            ]
            
            # Get current medications
            meds_query = f"""
            SELECT DISTINCT c.concept_name
            FROM drug_exposure de
            JOIN concept c ON de.drug_concept_id = c.concept_id
            WHERE de.person_id = {person_id}
            AND de.drug_exposure_end_date >= CURRENT_DATE
            ORDER BY de.drug_exposure_start_date DESC
            LIMIT 10
            """
            meds_result = conn.execute(meds_query).fetchall()
            medications = [row[0] for row in meds_result]
            
            return PatientProfile(
                patient_id=str(person_id),
                name=f"Patient {person_id}",
                conditions=conditions,
                current_medications=medications,
            )
        
        except Exception as e:
            print(f"Error loading from DuckDB: {e}")
            return None
    
    def list_all_patients(self) -> List[PatientProfile]:
        """List all patients in DuckDB (limit to first 10 for demo)"""
        try:
            conn = self.get_connection()
            query = "SELECT person_id FROM person LIMIT 10"
            results = conn.execute(query).fetchall()
            return [
                self.get_patient(str(row[0]))
                for row in results
                if self.get_patient(str(row[0])) is not None
            ]
        except Exception:
            return []


class SessionStore:
    """In-memory session storage for demo (would be Redis in production)"""
    
    def __init__(self):
        self.sessions = {}
    
    def create_session(self, session_id: str, session_data: dict):
        """Create a new session"""
        self.sessions[session_id] = session_data
    
    def get_session(self, session_id: str) -> Optional[dict]:
        """Retrieve session data"""
        return self.sessions.get(session_id)
    
    def update_session(self, session_id: str, session_data: dict):
        """Update existing session"""
        if session_id in self.sessions:
            self.sessions[session_id].update(session_data)
    
    def delete_session(self, session_id: str):
        """Delete session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
