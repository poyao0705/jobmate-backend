from __future__ import annotations

import os
import requests
from flask import request, jsonify
from . import api_bp
from jobmate_agent.extensions import db
from jobmate_agent.models import PreloadedContext

@api_bp.route("/_dev/langgraph/run", methods=["POST"])
def run_flow_dev():
    """Development-only endpoint to trigger a LangGraph flow without JWT.

    This endpoint is intentionally unprotected. To reduce accidental exposure,
    it will only run if the environment variable ENABLE_DEV_LANGGRAPH is set to
    a truthy value (e.g. '1' or 'true').
    """
    if not os.environ.get("ENABLE_DEV_LANGGRAPH"):
        return jsonify({"error": "dev_langgraph_disabled"}), 403

    data = request.get_json() or {}
    job_id = data.get("job_id")
    flow_name = data.get("flow_name") or "preload-and-seed-chat"
    # allow passing an auth token in the body for calling protected backend endpoints
    auth_token = data.get("auth_token")

    if not job_id:
        return jsonify({"error": "job_id is required"}), 400

    langgraph_url = os.environ.get("LANGGRAPH_URL")
    langgraph_key = os.environ.get("LANGGRAPH_API_KEY")
    if not langgraph_url or not langgraph_key:
        return (
            jsonify({"error": "LANGGRAPH_URL and LANGGRAPH_API_KEY must be set in env"}),
            500,
        )

    # Build inputs for LangGraph. If caller provided auth_token, forward it so the
    # flow can call protected backend endpoints. Otherwise, fetch preloaded snippets
    # from the database and pass them directly to the flow so no user token is needed.
    inputs = {
        "user_id": data.get("user_id"),
        "job_id": job_id,
    }

    if auth_token:
        inputs["auth_token"] = auth_token
    else:
        try:
            # Query PreloadedContext rows for this user/job (most recent first)
            q = db.session.query(PreloadedContext).filter(
                PreloadedContext.job_listing_id == int(job_id)
            )
            if data.get("user_id"):
                q = q.filter(PreloadedContext.user_id == data.get("user_id"))
            rows = q.order_by(PreloadedContext.created_at.desc()).limit(50).all()
            snippets = [
                {"doc_type": r.doc_type, "content": r.content} for r in rows
            ]
            inputs["snippets"] = snippets
        except Exception as e:
            # If anything goes wrong reading the DB, continue without snippets
            inputs["snippets_error"] = str(e)

    payload = {"flow_name": flow_name, "inputs": inputs}

    run_endpoint = langgraph_url.rstrip("/") + "/api/flows/run"
    headers = {"Authorization": f"Bearer {langgraph_key}", "Content-Type": "application/json"}

    try:
        resp = requests.post(run_endpoint, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "langgraph_request_failed", "detail": str(exc)}), 502

    return jsonify({"ok": True, "langgraph_response": resp.json()}), 200
