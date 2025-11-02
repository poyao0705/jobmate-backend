from __future__ import annotations

import os
import requests
from flask import request, jsonify, g
from . import api_bp

from jobmate_agent.jwt_auth import PyJWKClient, jwt
from jobmate_agent.jwt_auth import _fetch_user_profile, _upsert_user_profile
from jobmate_agent.extensions import db
from jobmate_agent.models import PreloadedContext


@api_bp.route("/langgraph/run", methods=["POST"])
def run_flow():
    """Trigger a LangGraph flow run.

    Accepts either:
      - Authorization: Bearer <user_jwt>  (standard user flow), or
      - X-Internal-API-Key: <internal_key> (server-to-server, trusted caller)

    The endpoint will call the configured LANGGRAPH_URL with LANGGRAPH_API_KEY.
    For user JWT, the user's token is forwarded into the flow as `auth_token`.
    For internal-key calls, the server will fetch `PreloadedContext` snippets and
    pass them into the flow so no user token is needed.
    """
    data = request.get_json() or {}
    job_id = data.get("job_id")
    flow_name = data.get("flow_name") or "preload-and-seed-chat"

    if not job_id:
        return jsonify({"error": "job_id is required"}), 400

    langgraph_url = os.environ.get("LANGGRAPH_URL")
    langgraph_key = os.environ.get("LANGGRAPH_API_KEY")
    if not langgraph_url or not langgraph_key:
        return jsonify({"error": "LANGGRAPH_URL and LANGGRAPH_API_KEY must be set"}), 500

    # Auth: either user JWT or internal API key
    auth_header = request.headers.get("Authorization", "")
    internal_key_header = request.headers.get("X-Internal-API-Key")
    internal_api_key = os.environ.get("INTERNAL_API_KEY")

    inputs = {"job_id": job_id}

    # If Authorization header present, validate JWT similarly to require_jwt
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        # Validate token using JWKS from Auth0
        domain = os.environ.get("AUTH0_DOMAIN")
        aud = os.environ.get("AUTH0_AUDIENCE")
        if not domain or not aud:
            return jsonify({"error": "AUTH0_DOMAIN and AUTH0_AUDIENCE must be configured"}), 500
        try:
            algs = ["RS256"]
            domain_hostname = domain.split("://")[1]
            iss = f"{domain}/"
            jwks_url = f"https://{domain_hostname}/.well-known/jwks.json"

            header = jwt.get_unverified_header(token)
            if header.get("alg") not in algs:
                return jsonify({"error": "unexpected_alg"}), 401

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

            # set user context
            g.jwt_payload = payload
            g.user_sub = payload.get("sub")
            inputs["user_id"] = g.user_sub
            inputs["auth_token"] = token
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "token_expired"}), 401
        except jwt.InvalidTokenError as e:
            return jsonify({"error": "invalid_token", "detail": str(e)}), 401
        except Exception as e:
            return jsonify({"error": "auth_failure", "detail": str(e)}), 401

    # Else if internal API key provided and valid, accept and fetch snippets server-side
    elif internal_key_header and internal_api_key and internal_key_header == internal_api_key:
        user_id = data.get("user_id")
        inputs["user_id"] = user_id
        try:
            q = db.session.query(PreloadedContext).filter(PreloadedContext.job_listing_id == int(job_id))
            if user_id:
                q = q.filter(PreloadedContext.user_id == user_id)
            rows = q.order_by(PreloadedContext.created_at.desc()).limit(50).all()
            snippets = [{"doc_type": r.doc_type, "content": r.content} for r in rows]
            inputs["snippets"] = snippets
            # Optionally hydrate user profile using Auth0 Management API if user_id provided
            if user_id:
                try:
                    profile = _fetch_user_profile(user_id)
                    if profile:
                        _upsert_user_profile(profile)
                except Exception:
                    # ignore hydration errors for internal-key path
                    pass
        except Exception as e:
            inputs["snippets_error"] = str(e)

    else:
        return jsonify({"error": "missing_or_invalid_authorization"}), 401

    payload = {"flow_name": flow_name, "inputs": inputs}

    run_endpoint = langgraph_url.rstrip("/") + "/api/flows/run"
    headers = {"Authorization": f"Bearer {langgraph_key}", "Content-Type": "application/json"}

    try:
        resp = requests.post(run_endpoint, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "langgraph_request_failed", "detail": str(exc)}), 502

    return jsonify({"ok": True, "langgraph_response": resp.json()}), 200
