# jwt_auth.py
import os
import time
from typing import Dict, Any
from functools import wraps
from typing import Callable, List, Optional, Set

from flask import jsonify, request, g
import jwt
from jwt import PyJWKClient
import requests

from jobmate_agent.extensions import db
from jobmate_agent.models import UserProfile


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
    domain_hostname = os.getenv("AUTH0_DOMAIN").split("://")[1]
    if not domain_hostname:
        raise RuntimeError("AUTH0_DOMAIN must be configured")
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
    domain_hostname = os.getenv("AUTH0_DOMAIN").split("://")[1]
    if not domain_hostname:
        raise RuntimeError("AUTH0_DOMAIN must be configured")
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
        profile (dict): The profile to upsert.

    Raises:
        ValueError: If the profile is not provided or does not include a 'sub'.

    Returns:
        UserProfile: The upserted user profile.
    """
    # Validation
    if not profile or not profile.get("sub"):
        raise ValueError("profile must include 'sub'")
    existing: UserProfile = db.session.get(UserProfile, profile["sub"])  # type: ignore
    is_new = existing is None
    if is_new:
        existing = UserProfile(id=profile["sub"])  # type: ignore[arg-type]
    existing.email = profile.get("email")
    existing.email_verified = bool(profile.get("email_verified", False))
    existing.name = profile.get("name")
    existing.picture = profile.get("picture")

    # For new profiles, duplicate name and email to contact fields
    if is_new:
        existing.contact_name = profile.get("name")
        existing.contact_email = profile.get("email")
        existing.contact_phone_number = None
        existing.contact_location = None

    db.session.add(existing)
    db.session.commit()
    return existing


def _has_required_scopes(payload: dict, required: List[str]) -> List[str]:
    """Check if the payload has the required scopes.

    Args:
        payload (dict): The payload to check.
        required (List[str]): The required scopes.

    Returns:
        List[str]: The missing scopes.
    """
    # Validation
    if not required:
        return []
    # Accept either 'permissions' (array) or 'scope' (space-delimited)
    perms: Set[str] = set(payload.get("permissions", []) or [])
    scopes = (
        set(str(payload.get("scope", "")).split()) if payload.get("scope") else set()
    )
    available = perms or scopes
    return [s for s in required if s not in available]


def _handle_user_profile_hydration(user_sub: str) -> UserProfile:
    """Handle user profile hydration.

    Args:
        user_sub (str): The user sub to fetch and upsert.

    Raises:
        ValueError: If user_sub is not provided.
        HTTPError: If the Management API returns an error.
        Exception: If an unexpected error occurs.

    Returns:
        UserProfile: The user profile.
    """
    # Validation
    if not user_sub:
        raise ValueError("user_sub must be provided")
    try:
        prof = db.session.get(UserProfile, user_sub)
        if prof is None:
            normalized = _fetch_user_profile(user_sub)
            if normalized is None:
                return (
                    jsonify({"error": "user_not_found_in_auth0"}),
                    404,
                )
            prof = _upsert_user_profile(normalized)
        g.user_profile = prof
    except requests.HTTPError as e:
        return (
            jsonify({"error": "mgmt_api_error", "detail": str(e)}),
            502,
        )
    except Exception as e:
        return (
            jsonify({"error": "hydrate_failure", "detail": str(e)}),
            500,
        )


def require_jwt(
    required_scopes: Optional[List[str]] = None,
    hydrate: bool = False,
) -> Callable:
    """Require a JWT Bearer token and validate the scopes.

    Args:
        required_scopes (Optional[List[str]], optional): The required scopes. Defaults to None.
        hydrate (bool, optional): Whether to hydrate the user profile. Defaults to False.

    Returns:
        Callable: The decorator.
    """
    # Validation
    domain = os.getenv("AUTH0_DOMAIN")
    aud = os.getenv("AUTH0_AUDIENCE")
    if not domain or not aud:
        raise RuntimeError("AUTH0_DOMAIN and AUTH0_AUDIENCE must be configured")

    algs = ["RS256"]

    # Derive issuer and JWKS URL from domain
    domain_hostname = domain.split("://")[
        1
    ]  # e.g. https://jobmate.agent.com.au -> jobmate.agent.com.au
    iss = f"{domain}/"  # e.g. https://jobmate.agent.com.au/
    jwks_url = f"https://{domain_hostname}/.well-known/jwks.json"

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapped(*args, **kwargs):

            auth_header = request.headers.get("Authorization", "")

            if not auth_header.startswith("Bearer "):
                return jsonify({"error": "missing_or_invalid_authorization"}), 401

            token = auth_header.split(" ", 1)[1]
            try:
                # Validation
                header = jwt.get_unverified_header(token)

                if header.get("alg") not in algs:
                    return jsonify({"error": "unexpected_alg"}), 401
                typ = (header.get("typ") or "").lower()
                if typ and typ not in ("jwt", "at+jwt"):
                    return jsonify({"error": "unexpected_token_type"}), 401

                signing_key = PyJWKClient(jwks_url).get_signing_key_from_jwt(token).key

                payload = jwt.decode(
                    token,
                    signing_key,
                    algorithms=algs,
                    audience=aud,
                    issuer=iss,
                    options={"verify_aud": bool(aud)},
                    leeway=60,
                )

                missing = _has_required_scopes(payload, required_scopes or [])
                if missing:
                    return (
                        jsonify({"error": "insufficient_scope", "missing": missing}),
                        403,
                    )

                g.jwt_payload = payload
                g.user_sub = payload.get("sub")

                # Lazy hydration: fetch and upsert UserProfile on first sight
                if hydrate and g.user_sub:
                    _handle_user_profile_hydration(g.user_sub)

            except jwt.ExpiredSignatureError:
                return jsonify({"error": "token_expired"}), 401
            except jwt.InvalidTokenError as e:
                return jsonify({"error": "invalid_token", "detail": str(e)}), 401
            except Exception as e:
                return jsonify({"error": "auth_failure", "detail": str(e)}), 401

            return fn(*args, **kwargs)

        return wrapped

    return decorator
