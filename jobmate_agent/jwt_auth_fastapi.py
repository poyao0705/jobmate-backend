# jwt_auth_fastapi.py
"""
JWT authentication for FastAPI using Auth0.
"""
import os
import time
from typing import Dict, Any, Optional, List, Callable
from functools import wraps

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient
import requests

from jobmate_agent.extensions_fastapi import SessionLocal
from jobmate_agent.models_fastapi import UserProfile


# Security scheme
security = HTTPBearer()

# in-process cache for the Management API token
_MGMT_TOKEN: Dict[str, Any] = {"token": None, "exp": 0}


def _get_mgmt_token() -> str:
    """Get a Management API token using Client Credentials.

    Raises:
        RuntimeError: If the AUTH0_DOMAIN is not configured.
        RuntimeError: If the Management API credentials are not configured.

    Returns:
        str: The Management API token.
    """
    # Validation
    domain = os.getenv("AUTH0_DOMAIN")
    if not domain:
        raise RuntimeError("AUTH0_DOMAIN must be configured")
    
    # Handle domain with or without https:// prefix
    domain_hostname = domain.replace("https://", "").replace("http://", "")
    
    mgmt_token_url = f"https://{domain_hostname}/oauth/token"
    mgmt_client_id = os.getenv("AUTH0_MGMT_CLIENT_ID")
    mgmt_client_secret = os.getenv("AUTH0_MGMT_CLIENT_SECRET")
    if not mgmt_client_id or not mgmt_client_secret:
        raise RuntimeError("Management API credentials are not configured")

    now = int(time.time())
    token = _MGMT_TOKEN.get("token")
    exp = int(_MGMT_TOKEN.get("exp") or 0)
    if token and exp - 60 > now:
        return token

    payload = {
        "grant_type": "client_credentials",
        "client_id": mgmt_client_id,
        "client_secret": mgmt_client_secret,
        "audience": f"https://{domain_hostname}/api/v2/",
    }
    resp = requests.post(mgmt_token_url, json=payload, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    _MGMT_TOKEN["token"] = data["access_token"]
    _MGMT_TOKEN["exp"] = now + int(data.get("expires_in", 1200))
    return _MGMT_TOKEN["token"]


def _fetch_user_profile(sub: str) -> Optional[dict]:
    """Fetch a user profile from the Management API.

    Args:
        sub (str): The user sub to fetch.

    Raises:
        RuntimeError: If the AUTH0_DOMAIN is not configured.

    Returns:
        Optional[dict]: The user profile.
    """
    # Validation
    domain = os.getenv("AUTH0_DOMAIN")
    if not domain:
        raise RuntimeError("AUTH0_DOMAIN must be configured")
    
    # Handle domain with or without https:// prefix
    domain_hostname = domain.replace("https://", "").replace("http://", "")
    
    mgmt_users_url = f"https://{domain_hostname}/api/v2/users"

    token = _get_mgmt_token()
    url = f"{mgmt_users_url}/{sub}"
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=5)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    u = r.json()
    identities = u.get("identities") or []
    provider = identities[0].get("provider") if identities else None
    return {
        "sub": u.get("user_id"),
        "email": u.get("email"),
        "email_verified": bool(u.get("email_verified")),
        "name": u.get("name"),
        "picture": u.get("picture"),
        "provider": provider,
    }


def _upsert_user_profile(profile: dict) -> UserProfile:
    """Upsert a user profile.

    Args:
        profile (dict): The profile data.

    Returns:
        UserProfile: The upserted user profile.
    """
    db = SessionLocal()
    try:
        user = db.query(UserProfile).filter_by(id=profile["sub"]).first()
        if not user:
            user = UserProfile(
                id=profile["sub"],
                email=profile.get("email"),
                email_verified=profile.get("email_verified", False),
                name=profile.get("name"),
                picture=profile.get("picture"),
            )
            db.add(user)
        else:
            # Update existing user
            user.email = profile.get("email")
            user.email_verified = profile.get("email_verified", False)
            user.name = profile.get("name")
            user.picture = profile.get("picture")
        
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def verify_jwt_token(token: str) -> Dict[str, Any]:
    """
    Verify JWT token from Auth0.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded JWT payload
        
    Raises:
        HTTPException: If token is invalid
    """
    domain = os.getenv("AUTH0_DOMAIN")
    audience = os.getenv("AUTH0_AUDIENCE")
    
    if not domain or not audience:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth0 configuration missing"
        )
    
    # Handle domain with or without https:// prefix
    domain_hostname = domain.replace("https://", "").replace("http://", "")
    jwks_url = f"https://{domain_hostname}/.well-known/jwks.json"
    
    try:
        jwks_client = PyJWKClient(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=audience,
            issuer=f"https://{domain_hostname}/"
        )
        
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {str(e)}"
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    FastAPI dependency to get current user from JWT token.
    Returns the JWT payload including 'sub' claim.
    """
    token = credentials.credentials
    payload = verify_jwt_token(token)
    return payload


async def get_current_user_with_profile(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> tuple[Dict[str, Any], Optional[UserProfile]]:
    """
    FastAPI dependency to get current user with hydrated profile.
    Returns tuple of (jwt_payload, user_profile).
    """
    token = credentials.credentials
    payload = verify_jwt_token(token)
    
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing 'sub' claim"
        )
    
    # Try to get user profile from database
    db = SessionLocal()
    try:
        user_profile = db.query(UserProfile).filter_by(id=sub).first()
        
        # If not found, fetch from Auth0 and create
        if not user_profile:
            profile_data = _fetch_user_profile(sub)
            if profile_data:
                user_profile = _upsert_user_profile(profile_data)
        
        return payload, user_profile
    finally:
        db.close()


def require_jwt(hydrate: bool = False):
    """
    Decorator factory for route protection.
    
    Args:
        hydrate: If True, fetch and upsert user profile from Auth0
        
    Returns:
        Dependency function for FastAPI
    """
    if hydrate:
        return Depends(get_current_user_with_profile)
    else:
        return Depends(get_current_user)


# Helper to get just the user_id (sub claim)
async def get_user_sub(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Get the user's sub claim from JWT token."""
    payload = await get_current_user(credentials)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing 'sub' claim"
        )
    return sub
