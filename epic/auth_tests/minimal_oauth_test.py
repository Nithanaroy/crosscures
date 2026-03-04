#!/usr/bin/env python3
"""
Minimal OAuth test for Epic FHIR Sandbox
Test credentials: FHIRTWO / EpicFhir11!
"""

import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs
import threading
import time

# Epic Sandbox Configuration
CLIENT_ID = "dfe21367-2dfe-46de-86f1-0bbbc4ccce9f"  # Non-Production Client ID
REDIRECT_URI = "http://localhost:8080/callback"
AUTH_URL = "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize"

# Event to signal when callback is received
callback_received = threading.Event()

# Callback handler
class CallbackHandler(BaseHTTPRequestHandler):
    authorization_code = None
    
    def do_GET(self):
        print(f"\n[CALLBACK] Received: {self.path}")
        query = parse_qs(urlparse(self.path).query)
        
        if 'code' in query:
            CallbackHandler.authorization_code = query['code'][0]
            print(f"[SUCCESS] Authorization code received!")
            print(f"[CODE] {CallbackHandler.authorization_code[:50]}...")
            
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"""
                <html>
                <body style="font-family: Arial; padding: 50px; text-align: center;">
                    <h1 style="color: green;">Success!</h1>
                    <p>Authorization code received. You can close this window.</p>
                </body>
                </html>
            """)
            callback_received.set()  # Signal that we got the code
        else:
            print(f"[ERROR] No code in callback: {self.path}")
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"""
                <html>
                <body style="font-family: Arial; padding: 50px; text-align: center;">
                    <h1 style="color: red;">Error</h1>
                    <p>No authorization code received.</p>
                </body>
                </html>
            """)
    
    def log_message(self, format, *args):
        pass  # Suppress default server logs

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
print("EPIC OAUTH TEST - SANDBOX")
print("=" * 70)
print(f"\nClient ID: {CLIENT_ID}")
print(f"Redirect URI: {REDIRECT_URI}")
print(f"\nTest Credentials: FHIRTWO / EpicFhir11!")
print("=" * 70)

# Start local server
print("\n[SERVER] Starting callback server on localhost:8080...")
server = HTTPServer(('localhost', 8080), CallbackHandler)
server_thread = threading.Thread(target=server.serve_forever, daemon=True)
server_thread.start()
print("[SERVER] Server running. Waiting for callback...")

# Open browser
print(f"\n[BROWSER] Opening authorization URL...")
print(f"\nURL:\n{auth_url}\n")
time.sleep(1)
webbrowser.open(auth_url)

print("[WAITING] Please log in with Epic sandbox credentials...")
print("[WAITING] After login, you'll be redirected back here...")

# Wait for callback with timeout
if callback_received.wait(timeout=120):  # 2 minute timeout
    print(f"\n{'='*70}")
    print("[SUCCESS] OAuth flow completed!")
    print(f"[CODE] Full authorization code:")
    print(f"       {CallbackHandler.authorization_code}")
    print(f"{'='*70}")
else:
    print(f"\n{'='*70}")
    print("[TIMEOUT] No callback received within 120 seconds")
    print("[INFO] If you completed login but saw 'connection refused',")
    print("[INFO] the server might have stopped too early. Try running again.")
    print(f"{'='*70}")

server.shutdown()
print("\n[SERVER] Callback server stopped.")
