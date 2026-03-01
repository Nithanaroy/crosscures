# Issue Report for Epic Developer Support

## Summary
Using Non-Production Client ID for OAuth redirects to production MyChart login instead of sandbox test patient login

## Environment
- **Epic App ID**: 51512
- **App Name**: CrossCures CKD Summarizer v2
- **App Status**: Draft (attempting to activate for sandbox)
- **Non-Production Client ID**: dfe21367-2dfe-46de-86f1-0bbbc4ccce9f
- **OAuth Endpoint**: https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize

## Expected Behavior
When using the Non-Production Client ID with Epic's sandbox OAuth endpoint, the login page should:
- Show Epic sandbox/test environment login
- Accept test patient credentials (e.g., fhircamila / epicepic1)
- Documented at: https://fhir.epic.com/Documentation?docId=testpatients

## Actual Behavior
The login page shows:
- Production MyChart login portal (HSWeb_uscdi)
- Does NOT accept sandbox test credentials
- Appears to be routing to customer production environment

## Steps to Reproduce
1. Use the Non-Production Client ID in OAuth authorization URL
2. Navigate to: https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize with params:
   - response_type=code
   - client_id=dfe21367-2dfe-46de-86f1-0bbbc4ccce9f
   - redirect_uri=http://localhost:8080/callback
   - scope=openid fhirUser patient/Patient.read
   - aud=https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4
3. Observe which login page appears

## Minimal Reproduction
See attached: `epic_url_test.py` (just opens the URL in browser)
Or: `minimal_oauth_test.py` (includes callback server)

## Configuration Checked
- ✓ Using Non-Production Client ID (not Production)
- ✓ Using https://fhir.epic.com/interconnect-fhir-oauth endpoints
- ✓ App configured as Confidential Client
- ✓ App has "Requires Persistent Access" enabled
- ✓ 20 FHIR R4 APIs selected
- ✓ Sandbox Client Secret generated
- ✓ Redirect URI: http://localhost:8080/callback

## Questions
1. Does the app need to be in a specific status (not "Draft") before sandbox OAuth works?
2. Is there a sync delay after generating Sandbox Client Secret?
3. How can we verify the app is properly activated in the sandbox environment?
4. Is there a diagnostic URL or tool to check app sandbox status?

## Documentation Referenced
- OAuth 2.0: https://fhir.epic.com/Documentation?docId=oauth2
- Test Patients: https://fhir.epic.com/Documentation?docId=testpatients
- FAQ "How do I use the sandbox?": https://fhir.epic.com/FAQ