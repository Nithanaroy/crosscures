#!/usr/bin/env python3
"""
ULTRA-MINIMAL Epic OAuth URL Generator
Just builds and opens the URL - no server needed
"""

import webbrowser
from urllib.parse import urlencode

# Configuration from Epic App ID 51512
CLIENT_ID = "dfe21367-2dfe-46de-86f1-0bbbc4ccce9f"
AUTH_URL = "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize"

params = {
    'response_type': 'code',
    'client_id': CLIENT_ID,
    'redirect_uri': 'http://localhost:8080/callback',
    'scope': 'openid fhirUser patient/Patient.read',
    'state': 'test',
    'aud': 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4'
}

url = f"{AUTH_URL}?{urlencode(params)}"

print("EPIC OAUTH TEST")
print("="*70)
print(f"Non-Production Client ID: {CLIENT_ID}")
print(f"Expected: Sandbox login (test patients)")
print(f"Question: Which login page actually appears?")
print("="*70)
print(f"\n{url}\n")

webbrowser.open(url)
