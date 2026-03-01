#!/usr/bin/env python3
"""
Minimal OAuth test for Epic FHIR Sandbox
Demonstrates the issue: which login page appears when using Non-Production Client ID
"""

import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs
import threading

# Epic Sandbox Configuration
CLIENT_ID = "dfe21367-2dfe-46de-86f1-0bbbc4ccce9f"  # Non-Production Client ID
REDIRECT_URI = "http://localhost:8080/callback"
AUTH_URL = "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize"

# Minimal callback handler
class CallbackHandler(BaseHTTPRequestHandler):
    authorization_code = None
    
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        
        if 'code' in query:
            CallbackHandler.authorization_code = query['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<h1>Success! You can close this window.</h1>")
        else:
            self.send_response(400)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress server logs

# Start local server
server = HTTPServer(('localhost', 8080), CallbackHandler)
server_thread = threading.Thread(target=server.serve_forever, daemon=True)
server_thread.start()

# Build authorization URL
params = {
    'response_type': 'code',
    'client_id': CLIENT_ID,
    'redirect_uri': REDIRECT_URI,
    'scope': 'openid fhirUser patient/Patient.read',
    'state': 'test123',
    'aud': 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4'
}

auth_url = f"{AUTH_URL}?{urlencode(params)}"

print("=" * 70)
print("MINIMAL EPIC OAUTH TEST")
print("=" * 70)
print(f"\nClient ID: {CLIENT_ID}")
print(f"Redirect URI: {REDIRECT_URI}")
print(f"\nExpected: Epic SANDBOX login (for test patients like fhircamila)")
print(f"Actual: Please report what login page appears")
print(f"\nOpening browser in 2 seconds...")
print(f"\nFull URL:\n{auth_url}")
print("=" * 70)

import time
time.sleep(2)

# Open browser
webbrowser.open(auth_url)

print("\nWaiting for callback (60 seconds)...")
server_thread.join(timeout=60)

if CallbackHandler.authorization_code:
    print(f"\n[SUCCESS] Received authorization code: {CallbackHandler.authorization_code[:20]}...")
else:
    print("\n[TIMEOUT] No authorization code received")

server.shutdown()
