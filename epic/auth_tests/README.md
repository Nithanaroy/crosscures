# Minimal Epic OAuth Test Examples

Simple scripts to demonstrate Epic FHIR sandbox OAuth test to verify connection.

## Files

1. **epic_url_test.py** - Ultra-minimal (11 lines)
   - Just builds and opens the OAuth URL
   - No dependencies beyond standard library
   - Run and observe which login page appears

2. **minimal_oauth_test.py** - Minimal with callback (50 lines)
   - Includes local server to receive callback
   - Still very simple, no error handling or extra features
   - Shows if authorization completes

3. **EPIC_SUPPORT_ISSUE.md** - Issue report
   - Formatted report for Epic developer support
   - Includes all relevant details
   - Ready to copy/paste or attach

## Usage

### Option 1: Ultra-minimal (just see the URL)
```bash
python3 epic_url_test.py
```

This opens your browser to the Epic OAuth URL. Observe:
- Can you use test patient credentials (FHIRTWO / EpicFhir11!)?

### Option 2: Full flow test
```bash
python3 minimal_oauth_test.py
```

This runs a local callback server and completes the OAuth flow.
Try logging in and see if the callback succeeds.