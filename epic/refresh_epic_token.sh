#!/bin/bash
# Direct Epic Token Refresh Script
# This script refreshes the Epic access token using the saved refresh token
# NO BROWSER REQUIRED - direct API call only

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================"
echo "Epic FHIR Token Refresh (Direct)"
echo "======================================"
echo ""

# Load environment variables
if [ -f .env ]; then
    source .env
else
    echo -e "${RED}[ERROR]${NC} .env file not found"
    exit 1
fi

# Check required variables
if [ -z "$EPIC_CLIENT_ID_SANDBOX" ] || [ -z "$EPIC_CLIENT_SECRET" ]; then
    echo -e "${RED}[ERROR]${NC} Missing EPIC_CLIENT_ID_SANDBOX or EPIC_CLIENT_SECRET in .env"
    exit 1
fi

# Load saved tokens
TOKEN_FILE=".epic_tokens.json"
if [ ! -f "$TOKEN_FILE" ]; then
    echo -e "${RED}[ERROR]${NC} No saved tokens found at $TOKEN_FILE"
    echo "Run test_epic_connection.py first to get initial tokens via browser"
    exit 1
fi

# Extract refresh token using jq (or python if jq not available)
if command -v jq &> /dev/null; then
    REFRESH_TOKEN=$(jq -r '.refresh_token' "$TOKEN_FILE")
else
    REFRESH_TOKEN=$(python3 -c "import json; print(json.load(open('$TOKEN_FILE'))['refresh_token'])")
fi

if [ -z "$REFRESH_TOKEN" ] || [ "$REFRESH_TOKEN" = "null" ]; then
    echo -e "${RED}[ERROR]${NC} No refresh token found in $TOKEN_FILE"
    exit 1
fi

echo -e "${GREEN}[OK]${NC} Found refresh token"
echo "[INFO] Refreshing access token via direct API call..."
echo ""

# Epic token endpoint
TOKEN_ENDPOINT="https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token"

# Make the token refresh request using curl
# Uses Basic Auth (client_id:client_secret) for confidential client
RESPONSE=$(curl -s -X POST "$TOKEN_ENDPOINT" \
    -u "$EPIC_CLIENT_ID_SANDBOX:$EPIC_CLIENT_SECRET" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "grant_type=refresh_token&refresh_token=$REFRESH_TOKEN")

# Check if response contains access_token
if echo "$RESPONSE" | grep -q '"access_token"'; then
    echo -e "${GREEN}[OK]${NC} Successfully refreshed access token!"
    echo ""
    
    # Parse response using jq or python
    if command -v jq &> /dev/null; then
        ACCESS_TOKEN=$(echo "$RESPONSE" | jq -r '.access_token')
        EXPIRES_IN=$(echo "$RESPONSE" | jq -r '.expires_in')
        TOKEN_TYPE=$(echo "$RESPONSE" | jq -r '.token_type')
        PATIENT_ID=$(echo "$RESPONSE" | jq -r '.patient // empty')
    else
        ACCESS_TOKEN=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['access_token'])")
        EXPIRES_IN=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('expires_in', 'N/A'))")
        TOKEN_TYPE=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('token_type', 'N/A'))")
        PATIENT_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('patient', ''))")
    fi
    
    echo "Token Details:"
    echo "  - Type: $TOKEN_TYPE"
    echo "  - Expires in: $EXPIRES_IN seconds"
    echo "  - Access Token (first 20 chars): ${ACCESS_TOKEN:0:20}..."
    if [ -n "$PATIENT_ID" ]; then
        echo "  - Patient ID: $PATIENT_ID"
    fi
    echo ""
    
    # Update the saved token file
    python3 -c "
import json
from datetime import datetime

# Load existing tokens
with open('$TOKEN_FILE', 'r') as f:
    tokens = json.load(f)

# Parse new response
new_tokens = json.loads('''$RESPONSE''')

# Update tokens
tokens['access_token'] = new_tokens['access_token']
tokens['expires_in'] = new_tokens.get('expires_in')
tokens['token_type'] = new_tokens.get('token_type')
tokens['saved_at'] = datetime.now().isoformat()

# Keep refresh token if not provided in response
if 'refresh_token' in new_tokens:
    tokens['refresh_token'] = new_tokens['refresh_token']

# Keep patient ID if not provided in response
if 'patient' in new_tokens:
    tokens['patient'] = new_tokens['patient']

# Save updated tokens
with open('$TOKEN_FILE', 'w') as f:
    json.dump(tokens, f, indent=2)

print('[OK] Updated tokens saved to $TOKEN_FILE')
print('[OK] You can now use this access token for Epic FHIR API calls')
"
    
else
    echo -e "${RED}[ERROR]${NC} Failed to refresh token"
    echo "Response:"
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
    exit 1
fi

echo ""
echo "======================================"
echo "Example API Call:"
echo "======================================"
echo "curl -H \"Authorization: Bearer \$ACCESS_TOKEN\" \\"
echo "     -H \"Accept: application/fhir+json\" \\"
echo "     \"https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/Patient/\${PATIENT_ID}\""
echo ""
