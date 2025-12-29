# 403 Error Troubleshooting Guide

## Changes Made to Fix 403 Errors

### 1. Enhanced CORS Configuration
**File:** `jobmate_agent/app_fastapi.py`

- Added support for environment variable `CORS_ALLOWED_ORIGINS`
- Added explicit OPTIONS method support for preflight requests
- Added `expose_headers` configuration
- Added logging to show which origins are allowed

### 2. Fixed Auth0 Domain Handling
**File:** `jobmate_agent/jwt_auth_fastapi.py`

- Fixed handling of AUTH0_DOMAIN with `https://` prefix
- Made domain parsing more robust across all authentication functions
- Prevents errors when domain includes protocol

### 3. Added CORS Configuration to .env
**File:** `.env`

- Added `CORS_ALLOWED_ORIGINS` variable
- Set default development origins

## How to Configure

### Step 1: Add Your Frontend URL to .env

Edit your `.env` file and update the `CORS_ALLOWED_ORIGINS` variable:

```env
# For local development
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# For production (add your deployed frontend URL)
CORS_ALLOWED_ORIGINS=https://your-frontend-domain.com,http://localhost:3000

# For multiple environments
CORS_ALLOWED_ORIGINS=https://your-frontend-domain.com,https://staging.your-domain.com,http://localhost:3000
```

### Step 2: Restart the FastAPI Server

```powershell
# Stop the current server (Ctrl+C)

# Restart with:
python run_fastapi.py
```

### Step 3: Run Diagnostic Test

```powershell
python test_cors_auth.py
```

## Common 403 Error Causes & Solutions

### 1. CORS Origin Not Allowed
**Symptom:** Browser console shows CORS error, 403 on preflight

**Solution:**
- Add your frontend URL to `CORS_ALLOWED_ORIGINS` in `.env`
- Make sure there are no trailing slashes
- Include the protocol (http:// or https://)

### 2. Missing or Invalid Authorization Header
**Symptom:** 403 error, no CORS errors in console

**Solution:**
- Verify frontend is sending `Authorization: Bearer <token>` header
- Check that Auth0 token is being retrieved correctly
- Verify token hasn't expired

### 3. Auth0 Configuration Mismatch
**Symptom:** 403 or 401 even with valid-looking token

**Solution:**
- Verify `AUTH0_DOMAIN` matches your Auth0 tenant
- Verify `AUTH0_AUDIENCE` matches your API identifier in Auth0
- Check that API permissions are configured in Auth0 dashboard

### 4. Token Validation Failure
**Symptom:** Returns 401/403 with valid token from Auth0

**Solution:**
- Check that `AUTH0_AUDIENCE` exactly matches the audience in the JWT
- Verify issuer in JWT matches your AUTH0_DOMAIN
- Check that signing algorithm is RS256

## Testing Steps

### Test 1: Check Server is Running
```bash
curl http://localhost:8000/api/ping
```
Expected: `{"ok": true, "message": "pong"}`

### Test 2: Check CORS Preflight
```bash
curl -X OPTIONS http://localhost:8000/api/user-profile \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: authorization"
```
Expected: Status 200 with CORS headers

### Test 3: Test Protected Endpoint (Should Fail)
```bash
curl http://localhost:8000/api/user-profile \
  -H "Origin: http://localhost:3000"
```
Expected: Status 403 or 401 (Unauthorized)

### Test 4: Test with Valid Token
```bash
# Get token from Auth0
# Then:
curl http://localhost:8000/api/user-profile \
  -H "Origin: http://localhost:3000" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```
Expected: Status 200 with user profile

## Debugging in Browser

### Check Network Tab
1. Open Developer Tools (F12)
2. Go to Network tab
3. Try the failing request
4. Look for:
   - Preflight OPTIONS request (should be 200)
   - Actual request (check response code and headers)

### Check Console
Look for CORS-related errors:
- "CORS policy: No 'Access-Control-Allow-Origin' header"
- "CORS policy: Response to preflight request doesn't pass"

### Check Request Headers
Verify these headers are being sent:
- `Origin: http://localhost:3000` (or your frontend URL)
- `Authorization: Bearer <token>`

### Check Response Headers
Should include:
- `Access-Control-Allow-Origin: http://localhost:3000`
- `Access-Control-Allow-Credentials: true`

## Auth0 Configuration Checklist

1. **API Configuration in Auth0:**
   - Go to Auth0 Dashboard > Applications > APIs
   - Find your API (identifier should match `AUTH0_AUDIENCE`)
   - Check "Allow Offline Access" if needed
   - Verify signing algorithm is RS256

2. **Application Configuration:**
   - Go to Auth0 Dashboard > Applications
   - Find your frontend application
   - Under "Allowed Callback URLs", add your frontend URL
   - Under "Allowed Web Origins", add your frontend URL
   - Under "Allowed Origins (CORS)", add your frontend URL

3. **Token Settings:**
   - Verify token expiration settings
   - Check that access token format is JWT (not opaque)

## FastAPI-Specific Notes

### Differences from Flask
- FastAPI requires explicit CORS middleware configuration
- OPTIONS requests must be explicitly handled for CORS preflight
- Authentication uses dependency injection instead of decorators

### Logging
Check FastAPI logs for:
```
INFO: CORS allowed origins: ['http://localhost:3000', ...]
```

If you don't see your frontend URL in the logs, the CORS configuration isn't being applied.

## Quick Fixes

### If Nothing Else Works:

**Option 1: Temporarily Allow All Origins (Development Only)**
```python
# In app_fastapi.py (DEVELOPMENT ONLY - NOT FOR PRODUCTION)
allow_origins=["*"]
```

**Option 2: Add Browser Extension**
- Install "CORS Unblock" extension (Chrome/Edge)
- Enable it temporarily to verify the issue is CORS

**Option 3: Use API Proxy**
- Configure Next.js to proxy API requests
- Add to `next.config.js`:
```javascript
module.exports = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
    ]
  },
}
```

## Contact Points for Further Investigation

If the issue persists, provide:
1. Browser console errors (screenshot)
2. Network tab showing failed request (headers & response)
3. FastAPI server logs
4. Output from `test_cors_auth.py`
5. Your frontend URL
6. How you're calling the API from frontend (code snippet)
