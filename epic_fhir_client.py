#!/usr/bin/env python3
"""
Epic FHIR Client
================
A client for accessing patient EHR data from Epic's FHIR R4 API.

Supports both:
- Patient Access (OAuth 2.0 with SMART on FHIR)
- Backend Services (for system-to-system integration)

Documentation: https://fhir.epic.com/
"""

import os
import httpx
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import json


class EpicEnvironment(Enum):
    """Epic FHIR API environments."""
    SANDBOX = "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"
    # Production URLs are health-system specific, e.g.:
    # "https://epicfhir.{organization}.org/FHIR/R4"


@dataclass
class EpicFHIRConfig:
    """Configuration for Epic FHIR API access."""
    client_id: str
    base_url: str = EpicEnvironment.SANDBOX.value
    redirect_uri: str = "http://localhost:8080/callback"
    scopes: List[str] = field(default_factory=lambda: [
        "patient/Patient.read",
        "patient/Condition.read",
        "patient/MedicationRequest.read",
        "patient/Observation.read",
        "patient/Encounter.read",
        "patient/Procedure.read",
        "patient/AllergyIntolerance.read",
        "patient/Immunization.read",
        "patient/DiagnosticReport.read",
    ])
    
    # For Backend Services (JWT auth)
    private_key_path: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "EpicFHIRConfig":
        """Create config from environment variables."""
        return cls(
            client_id=os.environ.get("EPIC_CLIENT_ID", ""),
            base_url=os.environ.get("EPIC_FHIR_BASE_URL", EpicEnvironment.SANDBOX.value),
            redirect_uri=os.environ.get("EPIC_REDIRECT_URI", "http://localhost:8080/callback"),
            private_key_path=os.environ.get("EPIC_PRIVATE_KEY_PATH"),
        )


class EpicFHIRClient:
    """
    Client for accessing Epic's FHIR R4 API.
    
    Usage:
        config = EpicFHIRConfig(client_id="your-client-id")
        client = EpicFHIRClient(config)
        
        # After OAuth flow, set the access token
        client.set_access_token(access_token, patient_id)
        
        # Fetch patient data
        patient = client.get_patient()
        conditions = client.get_conditions()
    """
    
    def __init__(self, config: EpicFHIRConfig):
        self.config = config
        self._access_token: Optional[str] = None
        self._patient_id: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._http_client = httpx.Client(timeout=30.0)
    
    def set_access_token(self, access_token: str, patient_id: str, expires_in: int = 3600):
        """
        Set the OAuth access token after completing the authorization flow.
        
        Args:
            access_token: The OAuth access token
            patient_id: The patient's FHIR ID (returned in token response)
            expires_in: Token validity in seconds
        """
        self._access_token = access_token
        self._patient_id = patient_id
        self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)
    
    @property
    def is_authenticated(self) -> bool:
        """Check if we have a valid access token."""
        if not self._access_token or not self._token_expires_at:
            return False
        return datetime.now() < self._token_expires_at
    
    @property
    def patient_id(self) -> Optional[str]:
        """Get the current patient ID."""
        return self._patient_id
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests."""
        if not self._access_token:
            raise ValueError("Access token not set. Complete OAuth flow first.")
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/fhir+json",
        }
    
    def _request(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make a request to the Epic FHIR API.
        
        Args:
            endpoint: The FHIR resource endpoint (e.g., "Patient", "Condition")
            params: Optional query parameters
            
        Returns:
            The JSON response
        """
        url = f"{self.config.base_url}/{endpoint}"
        response = self._http_client.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()
    
    def _search(self, resource_type: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Search for FHIR resources with automatic pagination.
        
        Args:
            resource_type: The FHIR resource type
            params: Search parameters
            
        Returns:
            List of matching resources
        """
        all_resources = []
        search_params = params or {}
        search_params["patient"] = self._patient_id
        
        bundle = self._request(resource_type, search_params)
        
        while bundle:
            entries = bundle.get("entry", [])
            all_resources.extend([e["resource"] for e in entries])
            
            # Check for next page
            next_link = None
            for link in bundle.get("link", []):
                if link.get("relation") == "next":
                    next_link = link.get("url")
                    break
            
            if next_link:
                response = self._http_client.get(next_link, headers=self._get_headers())
                response.raise_for_status()
                bundle = response.json()
            else:
                break
        
        return all_resources
    
    # =========================================================================
    # FHIR Resource Methods
    # =========================================================================
    
    def get_patient(self) -> Dict[str, Any]:
        """Get the patient's demographic information."""
        return self._request(f"Patient/{self._patient_id}")
    
    def get_conditions(self, clinical_status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get patient's conditions/diagnoses.
        
        Args:
            clinical_status: Filter by status (active, resolved, etc.)
        """
        params = {}
        if clinical_status:
            params["clinical-status"] = clinical_status
        return self._search("Condition", params)
    
    def get_medications(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get patient's medication requests.
        
        Args:
            status: Filter by status (active, completed, etc.)
        """
        params = {}
        if status:
            params["status"] = status
        return self._search("MedicationRequest", params)
    
    def get_observations(
        self, 
        category: Optional[str] = None,
        code: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get patient's observations (labs, vitals).
        
        Args:
            category: Filter by category (vital-signs, laboratory, etc.)
            code: Filter by LOINC code
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
        """
        params = {}
        if category:
            params["category"] = category
        if code:
            params["code"] = code
        if date_from:
            params["date"] = f"ge{date_from}"
        if date_to:
            params["date"] = f"le{date_to}"
        return self._search("Observation", params)
    
    def get_encounters(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get patient's encounters/visits.
        
        Args:
            status: Filter by status (finished, in-progress, etc.)
        """
        params = {}
        if status:
            params["status"] = status
        return self._search("Encounter", params)
    
    def get_procedures(self, date_from: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get patient's procedures."""
        params = {}
        if date_from:
            params["date"] = f"ge{date_from}"
        return self._search("Procedure", params)
    
    def get_allergies(self) -> List[Dict[str, Any]]:
        """Get patient's allergy intolerances."""
        return self._search("AllergyIntolerance")
    
    def get_immunizations(self) -> List[Dict[str, Any]]:
        """Get patient's immunization records."""
        return self._search("Immunization")
    
    def get_diagnostic_reports(self) -> List[Dict[str, Any]]:
        """Get patient's diagnostic reports."""
        return self._search("DiagnosticReport")
    
    def get_care_team(self) -> List[Dict[str, Any]]:
        """Get patient's care team members."""
        return self._search("CareTeam")
    
    def get_document_references(self) -> List[Dict[str, Any]]:
        """Get references to clinical documents."""
        return self._search("DocumentReference")
    
    # =========================================================================
    # Convenience Methods
    # =========================================================================
    
    def get_all_patient_data(self) -> Dict[str, Any]:
        """
        Fetch all available patient data in a single call.
        
        Returns:
            Dictionary with all FHIR resources organized by type
        """
        return {
            "patient": self.get_patient(),
            "conditions": self.get_conditions(),
            "medications": self.get_medications(),
            "observations": self.get_observations(),
            "encounters": self.get_encounters(),
            "procedures": self.get_procedures(),
            "allergies": self.get_allergies(),
            "immunizations": self.get_immunizations(),
            "diagnostic_reports": self.get_diagnostic_reports(),
        }
    
    def close(self):
        """Close the HTTP client."""
        self._http_client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# =============================================================================
# OAuth 2.0 Helper Functions
# =============================================================================

def get_authorization_url(config: EpicFHIRConfig, state: str = "random-state") -> str:
    """
    Generate the Epic OAuth authorization URL.
    
    Users should be redirected to this URL to authorize the app.
    
    Args:
        config: Epic FHIR configuration
        state: State parameter for CSRF protection
        
    Returns:
        The authorization URL
    """
    # Epic's authorization endpoint (sandbox)
    auth_endpoint = "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize"
    
    params = {
        "response_type": "code",
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "scope": " ".join(config.scopes),
        "state": state,
        "aud": config.base_url,
    }
    
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{auth_endpoint}?{query_string}"


def exchange_code_for_token(
    config: EpicFHIRConfig, 
    authorization_code: str
) -> Dict[str, Any]:
    """
    Exchange an authorization code for an access token.
    
    Args:
        config: Epic FHIR configuration
        authorization_code: The code from the OAuth callback
        
    Returns:
        Token response containing access_token, patient, expires_in, etc.
    """
    token_endpoint = "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token"
    
    data = {
        "grant_type": "authorization_code",
        "code": authorization_code,
        "redirect_uri": config.redirect_uri,
        "client_id": config.client_id,
    }
    
    with httpx.Client() as client:
        response = client.post(
            token_endpoint,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        response.raise_for_status()
        return response.json()


# =============================================================================
# Demo / Testing with Epic Sandbox
# =============================================================================

def create_sandbox_client() -> EpicFHIRClient:
    """
    Create a client configured for Epic's sandbox environment.
    
    Note: You still need to complete the OAuth flow to get an access token.
    Register your app at https://fhir.epic.com/ to get a client_id.
    """
    config = EpicFHIRConfig.from_env()
    if not config.client_id:
        print("Warning: EPIC_CLIENT_ID not set. Set it to use the Epic FHIR API.")
    return EpicFHIRClient(config)


if __name__ == "__main__":
    # Example usage
    print("Epic FHIR Client")
    print("================")
    print()
    print("To use this client:")
    print("1. Register an app at https://fhir.epic.com/")
    print("2. Set environment variable: EPIC_CLIENT_ID=your-client-id")
    print("3. Complete OAuth flow to get access token")
    print("4. Use the client to fetch patient data")
    print()
    
    # Demo with config
    config = EpicFHIRConfig(client_id="demo-client-id")
    auth_url = get_authorization_url(config)
    print(f"Authorization URL:\n{auth_url}")
