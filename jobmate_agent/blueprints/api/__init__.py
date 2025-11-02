from __future__ import annotations

import logging
from flask import Blueprint, jsonify, current_app, g
from jobmate_agent.services.vector_store import init_collections
from jobmate_agent.jwt_auth import require_jwt

logger = logging.getLogger(__name__)

# Create the blueprint
api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.record_once
def on_load(state):
    """Startup hook for ensuring Chroma collections exist."""
    import os

    if os.getenv("SKIP_CHROMA_INIT"):
        return  # Skip ChromaDB initialization

    try:
        init_collections()
    except Exception as exc:
        app = state.app
        app.config["CHROMA_INIT_ERROR"] = str(exc)


# Health check / ping endpoint
@api_bp.route("/ping-protected", methods=["GET"])
@require_jwt(hydrate=True)
def ping_protected():
    """Protected endpoint for testing authentication"""
    logger.debug(f"JWT payload: {g.jwt_payload}")
    return jsonify({"ok": True, "message": "pong"})


# Import API routes to register them on blueprint after blueprint creation
from .chat import *
from .jobListings import *
from .external_jobs import *
from .resumes import *
from .job_collections import *
from .user_profile import *
from .gap import *
from .langgraph import *
from .langgraph_dev import *
from .tasks import *
