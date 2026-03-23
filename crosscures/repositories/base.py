"""
Repository base classes and interfaces
"""
from abc import ABC, abstractmethod
from typing import Optional, List
from crosscures.models import PatientProfile


class PatientDataProvider(ABC):
    """Abstract interface for patient data access"""
    
    @abstractmethod
    def get_patient(self, patient_id: str) -> Optional[PatientProfile]:
        """Retrieve a single patient by ID"""
        pass
    
    @abstractmethod
    def list_all_patients(self) -> List[PatientProfile]:
        """List all available patients"""
        pass
