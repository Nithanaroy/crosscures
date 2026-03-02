#!/usr/bin/env python3
"""
Direct Epic Token Refresh
==========================
Refreshes Epic access token using saved refresh token.
NO BROWSER REQUIRED - direct API call only.

Usage:
    python refresh_token_direct.py
    
Returns:
    New access token saved to .epic_tokens.json
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / '.env')
except ImportError:
    print("[WARN] python-dotenv not installed, using system env vars")

import httpx

# Configuration
CLIENT_ID = os.environ.get("EPIC_CLIENT_ID_SANDBOX", "")
CLIENT_SECRET = os.environ.get("EPIC_CLIENT_SECRET", "")
TOKEN_ENDPOINT = "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token"
TOKEN_FILE = Path(__file__).parent / ".epic_tokens.json"


def load_refresh_token():
    """Load refresh token from saved file."""
    if not TOKEN_FILE.exists():
        print(f"[ERROR] No saved tokens found at {TOKEN_FILE}")
        print("Run test_epic_connection.py first to get initial tokens via browser")
        sys.exit(1)
    
    with open(TOKEN_FILE, "r") as f:
        tokens = json.load(f)
    
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        print("[ERROR] No refresh token found in saved tokens")
        sys.exit(1)
    
    return tokens


def refresh_access_token(refresh_token):
    """Refresh access token using refresh token (direct API call)."""
    print("[INFO] Refreshing access token via direct API call...")
    
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    
    # Use Basic auth (confidential client)
    if CLIENT_SECRET:
        auth = (CLIENT_ID, CLIENT_SECRET)
    else:
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
            sys.exit(1)
        
        return response.json()


def save_updated_tokens(old_tokens, new_token_response):
    """Update and save tokens."""
    # Update with new access token
    old_tokens["access_token"] = new_token_response["access_token"]
    old_tokens["expires_in"] = new_token_response.get("expires_in")
    old_tokens["token_type"] = new_token_response.get("token_type")
    old_tokens["saved_at"] = datetime.now().isoformat()
    
    # Update refresh token if provided (usually same)
    if "refresh_token" in new_token_response:
        old_tokens["refresh_token"] = new_token_response["refresh_token"]
    
    # Update patient if provided
    if "patient" in new_token_response:
        old_tokens["patient"] = new_token_response["patient"]
    
    with open(TOKEN_FILE, "w") as f:
        json.dump(old_tokens, f, indent=2)
    
    print(f"[OK] Updated tokens saved to {TOKEN_FILE}")


def main():
    """Main entry point."""
    print("=" * 60)
    print("Epic FHIR Token Refresh (Direct API Call)")
    print("=" * 60)
    print()
    
    if not CLIENT_ID or not CLIENT_SECRET:
        print("[ERROR] EPIC_CLIENT_ID_SANDBOX or EPIC_CLIENT_SECRET not set")
        sys.exit(1)
    
    # Load saved tokens
    print("[INFO] Loading saved refresh token...")
    tokens = load_refresh_token()
    print("[OK] Found refresh token")
    print()
    
    # Refresh the access token
    new_tokens = refresh_access_token(tokens["refresh_token"])
    
    print("[OK] Successfully refreshed access token!")
    print()
    print("Token Details:")
    print(f"  - Type: {new_tokens.get('token_type')}")
    print(f"  - Expires in: {new_tokens.get('expires_in')} seconds")
    print(f"  - Access Token (first 20 chars): {new_tokens['access_token'][:20]}...")
    if new_tokens.get("patient"):
        print(f"  - Patient ID: {new_tokens.get('patient')}")
    print()
    
    # Save updated tokens
    save_updated_tokens(tokens, new_tokens)
    
    print()
    print("=" * 60)
    print("Success! You can now use this access token for API calls")
    print("=" * 60)
    print()
    print("Example usage:")
    print(f"  export ACCESS_TOKEN='{new_tokens['access_token'][:20]}...'")
    print("  curl -H \"Authorization: Bearer $ACCESS_TOKEN\" \\")
    print("       -H \"Accept: application/fhir+json\" \\")
    print("       \"https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/Patient/{patient_id}\"")
    print()


if __name__ == "__main__":
    main()
