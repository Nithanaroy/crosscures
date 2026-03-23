# Epic FHIR Sandbox Integration

Concise guide for working with Epic's FHIR sandbox for testing.

## Quick Start

### 1. Epic App Configuration

**App ID:** 51512 - "CrossCures CKD Summarizer v2"

**Essential Settings:**
- Application Audience: Clinicians or Administrative Users
- OAuth: Confidential Client with Persistent Access
- FHIR Version: R4
- SMART Version: v2
- Redirect URI: `http://localhost:8080/callback` (HTTP is fine for sandbox)

**Client IDs:**
- Production: `bb890c52-ac1b-40fd-bb24-c78e182ab5a3`
- Sandbox (Non-Production): `dfe21367-2dfe-46de-86f1-0bbbc4ccce9f`

### 2. App Activation for Sandbox

1. On Epic app edit page, generate **Sandbox Client Secret**
2. Check "I accept the terms of use"
3. Click "Save & Ready for Sandbox"
4. **Wait up to 1 hour** for sync to sandbox
5. App status shows "Draft" - this is normal and correct

**Key Insight:** There is no separate "Ready for Sandbox" status. Draft apps are immediately testable after the sync period.

### 3. Sandbox Test Credentials

**Login:** `FHIRTWO`  
**Password:** `EpicFhir11!`

As described at https://fhir.epic.com/Documentation?docId=testpatients

**Endpoint:** `https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4`

## OAuth Flow

### Environment Variables (.env)

```bash
EPIC_CLIENT_ID_SANDBOX=dfe21367-2dfe-46de-86f1-0bbbc4ccce9f
EPIC_CLIENT_SECRET=vK7mSl1EVSgWAbzgj908iWyDQ9v3WgfWe0fiHWbANiuR0EG2N2PEJu2Fby8pEFreIykrNNzKE7IRWqIveCJRhg==
EPIC_REDIRECT_URI=http://localhost:8080/callback
EPIC_FHIR_BASE_URL=https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4
```

### Testing OAuth

```bash
# Quick test - just opens browser
python3 epic/auth_tests/epic_url_test.py

# Full flow test with token capture
python3 epic/auth_tests/minimal_oauth_test.py

# Main test with refresh token persistence
python3 epic/auth_tests/test_epic_connection.py
```

### How Localhost Callbacks Work

1. Script starts local server on `localhost:8080`
2. Browser opens Epic's OAuth page
3. User logs in with test credentials
4. Epic sends HTTP 302 redirect to browser: `http://localhost:8080/callback?code=...`
5. Browser (same machine) navigates to localhost
6. Local script receives authorization code
7. Script exchanges code for access + refresh tokens via HTTPS

**Epic's server never calls localhost** - only the browser does (via redirect).

## Token Management

### First-Time Login

```python
python3 epic/test_epic_connection.py
```

1. Opens browser to Epic login
2. Login with FHIRTWO / EpicFhir11!
3. Authorize the app
4. Tokens saved to `.epic_tokens.json`

### Subsequent Access (No Browser)

Once you have a refresh token:

```bash
# Python script
python3 epic/refresh_token_direct.py

# Or bash script
./epic/refresh_epic_token.sh
```

Refresh tokens are valid for extended periods and can be used to get new access tokens without re-authenticating.

## Token Storage

**File:** `.epic_tokens.json` (gitignored)

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "expires_in": 3600,
  "token_type": "Bearer",
  "scope": "...",
  "patient": "...",
  "saved_at": "2026-03-03T10:00:00"
}
```

## Common Issues

### "Draft" Status Won't Change
- **This is normal** - Draft status doesn't block sandbox testing
- Wait 1 hour after saving for sync to complete

### Wrong Login Page Appears
- Verify using **Non-Production Client ID** (dfe21367...)
- Check OAuth endpoint: `https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize`

### Test Credentials Rejected
- Use `FHIRTWO` / `EpicFhir11!` (not MyChart credentials)
- Ensure 1-hour sync period has elapsed after app changes

### Callback Not Received
- Check no other process is using port 8080
- Script must be running when browser redirects
- HTTP localhost callbacks are supported for sandbox

## Resources

- **Test Patients:** https://fhir.epic.com/Documentation?docId=testpatients
- **OAuth Guide:** https://fhir.epic.com/Documentation?docId=oauth2
- **Troubleshooting:** https://fhir.epic.com/Documentation?docId=troubleshooting_eof
- **Epic Support:** https://open.epic.com/Home/Contact
