#!/usr/bin/env python3
"""
Test Epic FHIR Connection
=========================
This script tests the Epic FHIR API connection by:
1. Starting a local callback server
2. Initiating the OAuth flow
3. Exchanging the authorization code for an access token
4. Fetching patient data

Usage:
    python test_epic_connection.py
"""

import os
import sys
import json
import webbrowser
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from pathlib import Path
from datetime import datetime, timedelta

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / '.env')
except ImportError:
    print("[WARN] python-dotenv not installed, using system env vars")

import httpx

# Configuration from environment
CLIENT_ID = os.environ.get("EPIC_CLIENT_ID_SANDBOX", "")
CLIENT_SECRET = os.environ.get("EPIC_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("EPIC_REDIRECT_URI", "http://localhost:8080/callback")
FHIR_BASE_URL = os.environ.get("EPIC_FHIR_BASE_URL", "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4")

# Token storage path
TOKEN_FILE = Path(__file__).parent / ".epic_tokens.json"

# Epic OAuth endpoints
AUTH_ENDPOINT = "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize"
TOKEN_ENDPOINT = "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token"

# Required FHIR R4 APIs for CKD Summarizer (20 total)
REQUIRED_APIS = [
    "AllergyIntolerance.Read (Patient Chart) (R4)",
    "AllergyIntolerance.Search (Patient Chart) (R4)",
    "Condition.Read (Problems) (R4)",
    "Condition.Search (Problems) (R4)",
    "DiagnosticReport.Read (Results) (R4)",
    "DiagnosticReport.Search (Results) (R4)",
    "Encounter.Read (Patient Chart) (R4)",
    "Encounter.Search (Patient Chart) (R4)",
    "Immunization.Read (Patient Chart) (R4)",
    "Immunization.Search (Patient Chart) (R4)",
    "MedicationRequest.Read (Signed Medication Order) (R4)",
    "MedicationRequest.Search (Signed Medication Order) (R4)",
    "Observation.Read (Labs) (R4)",
    "Observation.Read (Vital Signs) (R4)",
    "Observation.Search (Labs) (R4)",
    "Observation.Search (Vital Signs) (R4)",
    "Patient.Read (Demographics) (R4)",
    "Patient.Search (Demographics) (R4)",
    "Procedure.Read (Orders) (R4)",
    "Procedure.Search (Orders) (R4)",
]

# Scopes for patient data access
SCOPES = [
    "openid",
    "fhirUser",
    "patient/Patient.read",
    "patient/Condition.read",
    "patient/MedicationRequest.read",
    "patient/Observation.read",
    "patient/Encounter.read",
    "patient/AllergyIntolerance.read",
    "patient/Immunization.read",
    "patient/DiagnosticReport.read",
    "patient/Procedure.read",
]


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback."""
    
    authorization_code = None
    error = None
    
    def do_GET(self):
        """Handle the OAuth callback."""
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        
        if "code" in params:
            OAuthCallbackHandler.authorization_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
            <html>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: green;">[OK] Authorization Successful!</h1>
                <p>You can close this window and return to the terminal.</p>
            </body>
            </html>
            """)
        elif "error" in params:
            OAuthCallbackHandler.error = params.get("error_description", params["error"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            error_msg = OAuthCallbackHandler.error
            self.wfile.write(f"""
            <html>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: red;">[ERROR] Authorization Failed</h1>
                <p>{error_msg}</p>
            </body>
            </html>
            """.encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def save_tokens(token_response):
    """Save tokens to local file for reuse."""
    token_data = {
        "access_token": token_response.get("access_token"),
        "refresh_token": token_response.get("refresh_token"),
        "expires_in": token_response.get("expires_in"),
        "token_type": token_response.get("token_type"),
        "scope": token_response.get("scope"),
        "patient": token_response.get("patient"),
        "saved_at": datetime.now().isoformat(),
    }
    
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)
    
    print(f"[OK] Tokens saved to {TOKEN_FILE}")
    if token_response.get("refresh_token"):
        print("[OK] Refresh token available - no browser login needed next time!")


def load_tokens():
    """Load saved tokens from file."""
    if not TOKEN_FILE.exists():
        return None
    
    try:
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] Failed to load tokens: {e}")
        return None


def refresh_access_token(refresh_token):
    """Exchange refresh token for new access token (no browser needed)."""
    print("[INFO] Using refresh token to get new access token...")
    
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    
    # Use Basic auth if we have a client secret (confidential client)
    if CLIENT_SECRET:
        auth = (CLIENT_ID, CLIENT_SECRET)
    else:
        # Public client - include client_id in form data
        data["client_id"] = CLIENT_ID
        auth = None
    
    with httpx.Client() as client:
        response = client.post(
            TOKEN_ENDPOINT,
            data=data,
            auth=auth,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code != 200:
            print(f"[ERROR] Token refresh failed: {response.status_code}")
            print(f"Response: {response.text}")
            return None
        
        token_response = response.json()
        print("[OK] Successfully refreshed access token!")
        return token_response


def get_authorization_url():
    """Generate the OAuth authorization URL."""
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "state": "epic-test-state",
        "aud": FHIR_BASE_URL,
    }
    return f"{AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"


def exchange_code_for_token(code):
    """Exchange authorization code for access token."""
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    
    # Use Basic auth if we have a client secret (confidential client)
    if CLIENT_SECRET:
        auth = (CLIENT_ID, CLIENT_SECRET)
        print("[INFO] Using confidential client authentication (Basic auth)")
    else:
        # Public client - include client_id in form data
        data["client_id"] = CLIENT_ID
        auth = None
        print("[INFO] Using public client authentication")
    
    with httpx.Client() as client:
        response = client.post(
            TOKEN_ENDPOINT,
            data=data,
            auth=auth,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code != 200:
            print(f"[ERROR] Token exchange failed: {response.status_code}")
            print(f"Response: {response.text}")
            return None
        
        return response.json()


def fetch_patient_data(access_token, patient_id):
    """Fetch patient data using the access token."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/fhir+json",
    }
    
    results = {}
    
    with httpx.Client(timeout=30.0) as client:
        # Fetch patient demographics
        print("[INFO] Fetching Patient demographics...")
        try:
            resp = client.get(f"{FHIR_BASE_URL}/Patient/{patient_id}", headers=headers)
            if resp.status_code == 200:
                results["patient"] = resp.json()
                patient = results["patient"]
                name = patient.get("name", [{}])[0]
                print(f"  - Name: {name.get('given', [''])[0]} {name.get('family', '')}")
                print(f"  - Birth Date: {patient.get('birthDate', 'N/A')}")
                print(f"  - Gender: {patient.get('gender', 'N/A')}")
            else:
                print(f"  [WARN] Status: {resp.status_code}")
        except Exception as e:
            print(f"  [ERROR] {e}")
        
        # Fetch conditions
        print("[INFO] Fetching Conditions...")
        try:
            resp = client.get(f"{FHIR_BASE_URL}/Condition", params={"patient": patient_id}, headers=headers)
            if resp.status_code == 200:
                bundle = resp.json()
                entries = bundle.get("entry", [])
                results["conditions"] = [e["resource"] for e in entries]
                print(f"  - Found {len(entries)} conditions")
                for entry in entries[:5]:
                    cond = entry["resource"]
                    code = cond.get("code", {}).get("text") or cond.get("code", {}).get("coding", [{}])[0].get("display", "Unknown")
                    print(f"    * {code}")
            else:
                print(f"  [WARN] Status: {resp.status_code}")
        except Exception as e:
            print(f"  [ERROR] {e}")
        
        # Fetch medications
        print("[INFO] Fetching Medications...")
        try:
            resp = client.get(f"{FHIR_BASE_URL}/MedicationRequest", params={"patient": patient_id}, headers=headers)
            if resp.status_code == 200:
                bundle = resp.json()
                entries = bundle.get("entry", [])
                results["medications"] = [e["resource"] for e in entries]
                print(f"  - Found {len(entries)} medication requests")
                for entry in entries[:5]:
                    med = entry["resource"]
                    name = med.get("medicationReference", {}).get("display") or \
                           med.get("medicationCodeableConcept", {}).get("text", "Unknown")
                    print(f"    * {name}")
            else:
                print(f"  [WARN] Status: {resp.status_code}")
        except Exception as e:
            print(f"  [ERROR] {e}")
        
        # Fetch observations (labs)
        print("[INFO] Fetching Lab Observations...")
        try:
            resp = client.get(f"{FHIR_BASE_URL}/Observation", params={"patient": patient_id, "category": "laboratory"}, headers=headers)
            if resp.status_code == 200:
                bundle = resp.json()
                entries = bundle.get("entry", [])
                results["labs"] = [e["resource"] for e in entries]
                print(f"  - Found {len(entries)} lab observations")
                for entry in entries[:5]:
                    obs = entry["resource"]
                    code = obs.get("code", {}).get("text") or obs.get("code", {}).get("coding", [{}])[0].get("display", "Unknown")
                    value = obs.get("valueQuantity", {}).get("value", "")
                    unit = obs.get("valueQuantity", {}).get("unit", "")
                    print(f"    * {code}: {value} {unit}")
            else:
                print(f"  [WARN] Status: {resp.status_code}")
        except Exception as e:
            print(f"  [ERROR] {e}")
    
    return results


def main():
    """Main entry point."""
    print("=" * 60)
    print("Epic FHIR API Connection Test")
    print("=" * 60)
    print()
    
    if not CLIENT_ID:
        print("[ERROR] EPIC_CLIENT_ID_SANDBOX not set in .env file")
        sys.exit(1)
    
    print(f"[INFO] Client ID: {CLIENT_ID[:8]}...{CLIENT_ID[-8:]}")
    print(f"[INFO] Full Client ID: {CLIENT_ID}")
    print(f"[INFO] Redirect URI: {REDIRECT_URI}")
    print(f"[INFO] FHIR Base URL: {FHIR_BASE_URL}")
    print(f"[INFO] Auth Endpoint: {AUTH_ENDPOINT}")
    print()
    
    # Check for saved tokens first
    saved_tokens = load_tokens()
    token_response = None
    
    if saved_tokens and saved_tokens.get("refresh_token"):
        print("[INFO] Found saved refresh token!")
        print("[INFO] Attempting to refresh access token (no browser needed)...")
        token_response = refresh_access_token(saved_tokens["refresh_token"])
        
        if token_response:
            # Update saved tokens with new access token
            save_tokens(token_response)
            print("[OK] Using refreshed access token - skipping browser login!")
            print()
        else:
            print("[WARN] Refresh token invalid/expired - falling back to browser login")
            token_response = None
    else:
        print("[INFO] No saved refresh token found - browser login required")
    
    # If no valid token yet, do browser OAuth flow
    if not token_response:
        # Parse redirect URI for server config
        parsed_uri = urllib.parse.urlparse(REDIRECT_URI)
        host = parsed_uri.hostname or "localhost"
        port = parsed_uri.port or 8080
        
        # Start the callback server
        print(f"[INFO] Starting callback server on {host}:{port}...")
        server = HTTPServer((host, port), OAuthCallbackHandler)
        server_thread = Thread(target=server.handle_request)
        server_thread.start()
        
        # Open browser for authorization
        auth_url = get_authorization_url()
        print("[INFO] Opening browser for authorization...")
        print(f"[INFO] Full Authorization URL:")
        print(f"       {auth_url}")
        print()
        print("-" * 60)
        print("INSTRUCTIONS:")
        print("1. A browser window will open to Epic's sandbox login")
        print("2. Log in with a test patient (e.g., fhircamila / epicepic1)")
        print("3. Authorize the app")
        print("4. You'll be redirected back to this script")
        print("-" * 60)
        print()
        
        webbrowser.open(auth_url)
        
        # Wait for callback
        print("[INFO] Waiting for authorization callback...")
        server_thread.join(timeout=120)  # 2 minute timeout
        server.server_close()
        
        if OAuthCallbackHandler.error:
            print(f"[ERROR] Authorization failed: {OAuthCallbackHandler.error}")
            sys.exit(1)
        
        if not OAuthCallbackHandler.authorization_code:
            print("[ERROR] No authorization code received (timeout)")
            sys.exit(1)
        
        code = OAuthCallbackHandler.authorization_code
        print(f"[OK] Received authorization code: {code[:10]}...")
        print()
        
        # Exchange code for token
        print("[INFO] Exchanging code for access token...")
        token_response = exchange_code_for_token(code)
        
        if not token_response:
            print("[ERROR] Failed to get access token")
            sys.exit(1)
        
        # Save tokens for reuse
        save_tokens(token_response)
        
        print("[OK] Token exchange successful!")
        print(f"  - Token type: {token_response.get('token_type')}")
        print(f"  - Expires in: {token_response.get('expires_in')} seconds")
        print(f"  - Scopes: {token_response.get('scope', 'N/A')}")
    
    # Extract access token and patient ID
    access_token = token_response.get("access_token")
    patient_id = token_response.get("patient") or (saved_tokens.get("patient") if saved_tokens else None)
    
    if not patient_id:
        print("[ERROR] No patient ID in token response")
        print(f"Full response: {json.dumps(token_response, indent=2)}")
        sys.exit(1)
    
    print(f"  - Patient ID: {patient_id}")
    print()
    
    # Fetch patient data
    print("=" * 60)
    print("Fetching Patient Data")
    print("=" * 60)
    print()
    
    results = fetch_patient_data(access_token, patient_id)
    
    # Save results to file
    output_file = Path(__file__).parent / "data" / "epic_test_output.json"
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print()
    print(f"[OK] Results saved to: {output_file}")
    print()
    print("=" * 60)
    print("Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
