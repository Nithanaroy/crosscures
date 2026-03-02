#!/usr/bin/env python3
"""
CrossCures - EHR Data Summarizer
================================
Fetch patient data from Epic FHIR API and generate longitudinal summaries.
"""

import os
import sys
from epic_fhir_client import EpicFHIRClient, EpicFHIRConfig, get_authorization_url
from fhir_summarizer import FHIRSummarizer, summarize_patient_data


def demo_with_sample_data():
    """Demo the summarizer with sample FHIR data."""
    sample_data = {
        "patient": {
            "id": "example-patient-123",
            "name": [{"given": ["Jane"], "family": "Smith"}],
            "birthDate": "1975-08-22",
            "gender": "female",
            "telecom": [
                {"system": "phone", "value": "(555) 123-4567"},
                {"system": "email", "value": "jane.smith@email.com"},
            ],
            "address": [{"line": ["123 Main St"], "city": "Boston", "state": "MA", "postalCode": "02101"}],
        },
        "conditions": [
            {
                "id": "cond-1",
                "code": {"coding": [{"system": "http://snomed.info/sct", "code": "44054006", "display": "Type 2 Diabetes Mellitus"}]},
                "clinicalStatus": {"coding": [{"code": "active", "display": "Active"}]},
                "onsetDateTime": "2018-03-15",
                "recordedDate": "2018-03-15",
            },
            {
                "id": "cond-2",
                "code": {"coding": [{"system": "http://snomed.info/sct", "code": "38341003", "display": "Essential Hypertension"}]},
                "clinicalStatus": {"coding": [{"code": "active", "display": "Active"}]},
                "onsetDateTime": "2019-07-20",
                "recordedDate": "2019-07-20",
            },
        ],
        "medications": [
            {
                "id": "med-1",
                "medicationCodeableConcept": {"coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "860975", "display": "Metformin 500 MG Oral Tablet"}]},
                "status": "active",
                "dosageInstruction": [{"text": "Take 1 tablet twice daily with meals"}],
                "authoredOn": "2023-01-15T10:30:00Z",
            },
            {
                "id": "med-2",
                "medicationCodeableConcept": {"coding": [{"display": "Lisinopril 10 MG Oral Tablet"}]},
                "status": "active",
                "dosageInstruction": [{"text": "Take 1 tablet daily in the morning"}],
                "authoredOn": "2023-02-20T09:00:00Z",
            },
        ],
        "allergies": [
            {
                "id": "allergy-1",
                "code": {"coding": [{"display": "Penicillin"}]},
                "clinicalStatus": {"coding": [{"code": "active", "display": "Active"}]},
                "reaction": [{"manifestation": [{"coding": [{"display": "Hives"}]}]}],
                "criticality": "high",
            },
            {
                "id": "allergy-2",
                "code": {"coding": [{"display": "Sulfa drugs"}]},
                "clinicalStatus": {"coding": [{"code": "active", "display": "Active"}]},
                "reaction": [{"manifestation": [{"coding": [{"display": "Rash"}]}]}],
                "criticality": "low",
            },
        ],
        "observations": [
            {
                "id": "obs-1",
                "code": {"coding": [{"system": "http://loinc.org", "code": "4548-4", "display": "Hemoglobin A1c"}]},
                "valueQuantity": {"value": 7.2, "unit": "%"},
                "effectiveDateTime": "2024-01-10T08:00:00Z",
                "status": "final",
                "category": [{"coding": [{"code": "laboratory"}]}],
                "referenceRange": [{"low": {"value": 4.0}, "high": {"value": 5.6}}],
            },
            {
                "id": "obs-2",
                "code": {"coding": [{"system": "http://loinc.org", "code": "2339-0", "display": "Glucose"}]},
                "valueQuantity": {"value": 145, "unit": "mg/dL"},
                "effectiveDateTime": "2024-01-10T08:00:00Z",
                "status": "final",
                "category": [{"coding": [{"code": "laboratory"}]}],
                "referenceRange": [{"low": {"value": 70}, "high": {"value": 100}}],
            },
            {
                "id": "obs-3",
                "code": {"coding": [{"display": "Blood Pressure"}]},
                "valueQuantity": {"value": 138, "unit": "mmHg"},
                "effectiveDateTime": "2024-01-15T10:30:00Z",
                "status": "final",
                "category": [{"coding": [{"code": "vital-signs"}]}],
            },
        ],
        "encounters": [
            {
                "id": "enc-1",
                "status": "finished",
                "class": {"code": "AMB", "display": "Ambulatory"},
                "type": [{"coding": [{"display": "Office Visit"}]}],
                "period": {"start": "2024-01-15T09:00:00Z", "end": "2024-01-15T09:30:00Z"},
                "reasonCode": [{"coding": [{"display": "Diabetes follow-up"}]}],
            },
        ],
        "procedures": [
            {
                "id": "proc-1",
                "code": {"coding": [{"display": "Comprehensive metabolic panel"}]},
                "status": "completed",
                "performedDateTime": "2024-01-10T08:00:00Z",
            },
        ],
        "immunizations": [
            {
                "id": "imm-1",
                "vaccineCode": {"coding": [{"display": "Influenza vaccine"}]},
                "status": "completed",
                "occurrenceDateTime": "2023-10-15T10:00:00Z",
            },
            {
                "id": "imm-2",
                "vaccineCode": {"coding": [{"display": "COVID-19 vaccine"}]},
                "status": "completed",
                "occurrenceDateTime": "2023-09-01T14:00:00Z",
            },
        ],
    }
    
    print("=" * 60)
    print("CrossCures - EHR Data Summarizer Demo")
    print("=" * 60)
    print()
    print(summarize_patient_data(sample_data, format="markdown"))


def main():
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo_with_sample_data()
        return
    
    # Check for Epic credentials
    client_id = os.environ.get("EPIC_CLIENT_ID")
    
    if not client_id:
        print("CrossCures - EHR Data Summarizer")
        print("=" * 40)
        print()
        print("To connect to Epic FHIR API:")
        print("1. Register an app at https://fhir.epic.com/")
        print("2. Set environment variable: export EPIC_CLIENT_ID=your-client-id")
        print("3. Run this script again")
        print()
        print("For a demo with sample data, run:")
        print("  python main.py --demo")
        print()
        
        # Show authorization URL example
        config = EpicFHIRConfig(client_id="your-client-id")
        print("Sample Authorization URL:")
        print(get_authorization_url(config))
        return
    
    # Create client and show auth URL
    config = EpicFHIRConfig.from_env()
    print("Epic FHIR Client configured!")
    print()
    print("Authorization URL:")
    print(get_authorization_url(config))
    print()
    print("After authorization, you'll receive an access token.")
    print("Use the EpicFHIRClient and FHIRSummarizer classes to fetch and summarize data.")


if __name__ == "__main__":
    main()
