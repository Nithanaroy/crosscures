# Epic FHIR Token Management

## Overview

This project now supports **refresh token persistence**, which means:
- **First time only**: Browser login required to get initial tokens
- **All subsequent times**: Direct token refresh (no browser!) via shell command or Python

## How It Works

### OAuth Token Types

1. **Authorization Code** (10 min, single-use)
   - Gets exchanged for tokens
   - Requires browser login

2. **Access Token** (1 hour, expires)
   - Used for API calls
   - Short-lived for security

3. **Refresh Token** (1+ year, persistent)
   - Used to get new access tokens
   - **Saved to `.epic_tokens.json`**
   - Can be used repeatedly

4. **Client Secret** (permanent)
   - Stored in `.env`
   - Proves app identity

## Usage

### First Time Setup (Browser Required)

Run the main test script to get initial tokens:

```bash
python test_epic_connection.py
```

This will:
1. Open browser for Epic login
2. Exchange auth code for tokens
3. **Save refresh token to `.epic_tokens.json`**
4. Fetch patient data

After this completes, you'll have a saved refresh token for reuse.

### Subsequent Runs (No Browser!)

#### Option 1: Use the main script (automatic)

```bash
python test_epic_connection.py
```

It will automatically:
- Check for saved refresh token
- Refresh access token directly (no browser!)
- Fetch patient data

#### Option 2: Refresh token only (Shell script)

```bash
./refresh_epic_token.sh
```

This bash script:
- Loads refresh token from `.epic_tokens.json`
- Calls Epic API directly with `curl`
- Updates saved tokens
- No Python required!

#### Option 3: Refresh token only (Python script)

```bash
python refresh_token_direct.py
```

This Python script:
- Loads refresh token from `.epic_tokens.json`
- Calls Epic API directly with `httpx`
- Updates saved tokens
- Cleaner than bash for developers

## Direct API Call Example (curl)

Once you have tokens, you can refresh directly:

```bash
# Load environment
source .env

# Extract refresh token
REFRESH_TOKEN=$(python3 -c "import json; print(json.load(open('.epic_tokens.json'))['refresh_token'])")

# Call Epic token endpoint directly
curl -X POST "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token" \
  -u "$EPIC_CLIENT_ID_SANDBOX:$EPIC_CLIENT_SECRET" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=refresh_token&refresh_token=$REFRESH_TOKEN"
```

This returns a new access token immediately - **no browser needed!**

## Files

| File | Purpose |
|------|---------|
| `test_epic_connection.py` | Main test script with auto-refresh |
| `.epic_tokens.json` | Saved tokens (refresh + access) |
| `refresh_epic_token.sh` | Shell script for direct refresh |
| `refresh_token_direct.py` | Python script for direct refresh |
| `.env` | Client credentials (SECRET!) |

## Security Notes

- `.epic_tokens.json` should be in `.gitignore` (contains sensitive tokens)
- Refresh tokens last ~1 year, then you need browser login again
- Access tokens expire after 1 hour
- Client secret must never be committed to git

## Workflow Comparison

### Old Way (Every Session)
```
1. Open browser
2. Login to Epic
3. Authorize app
4. Get auth code
5. Exchange for access token
6. Use access token
```

### New Way (After First Time)
```
1. Load refresh token from file
2. Call Epic API directly (curl or Python)
3. Get new access token
4. Use access token
```

**Result**: Skip steps 1-4 entirely! One API call instead of browser flow.

## When Browser Login is Required

You'll need browser login again when:
- First time setup (no saved tokens)
- Refresh token expires (~1 year)
- Refresh token is invalid/revoked
- `.epic_tokens.json` is deleted

## Example Output

### First Run (Browser Login)
```
[INFO] No saved refresh token found - browser login required
[INFO] Starting callback server on localhost:8080...
[INFO] Opening browser for authorization...
[OK] Received authorization code
[OK] Token exchange successful!
[OK] Tokens saved to .epic_tokens.json
[OK] Refresh token available - no browser login needed next time!
```

### Subsequent Runs (Direct Refresh)
```
[INFO] Found saved refresh token!
[INFO] Attempting to refresh access token (no browser needed)...
[OK] Successfully refreshed access token!
[OK] Using refreshed access token - skipping browser login!
```

## Troubleshooting

### "No refresh token found"
- Run `python test_epic_connection.py` first to get initial tokens

### "Refresh token invalid"
- Refresh token expired (~1 year)
- Run browser login again to get new refresh token

### "Client secret not set"
- Check `.env` file has `EPIC_CLIENT_SECRET`
