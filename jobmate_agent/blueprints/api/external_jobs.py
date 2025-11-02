"""
External Job API endpoints
Provides REST API endpoints to trigger external job fetching
"""

from flask import request, jsonify, current_app
from datetime import datetime
import threading
import time
import logging

from jobmate_agent.blueprints.api import api_bp
from jobmate_agent.jwt_auth import require_jwt
from jobmate_agent.services.external_apis.external_job_fetcher import (
    fetchJobFromExternal,
)

# Store running job fetch tasks
active_fetch_tasks = {}

logger = logging.getLogger(__name__)


def run_job_fetch_background(task_id: str, parameters: dict):
    """Run job fetching in background thread"""
    try:
        logger.info(f"Starting background job fetch task: {task_id}")

        # Extract parameters
        keywords = parameters.get("keywords", ["Python developer", "Data engineer"])
        locations = parameters.get("locations", ["Australia", "Sydney"])
        job_types = parameters.get("job_types", ["fullTime"])
        max_jobs_per_search = parameters.get("max_jobs_per_search", 20)

        # Update task status
        active_fetch_tasks[task_id]["status"] = "running"
        active_fetch_tasks[task_id]["started_at"] = datetime.utcnow().isoformat()

        # Run the fetching
        result = fetchJobFromExternal(
            keywords=keywords,
            locations=locations,
            job_types=job_types,
            max_jobs_per_search=max_jobs_per_search,
        )

        # Update task with results
        active_fetch_tasks[task_id].update(
            {
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat(),
                "result": result,
            }
        )

        logger.info(f"Background job fetch task completed: {task_id}")

    except Exception as e:
        logger.error(f"Background job fetch task failed: {task_id} - {e}")
        active_fetch_tasks[task_id].update(
            {
                "status": "failed",
                "completed_at": datetime.utcnow().isoformat(),
                "error": str(e),
            }
        )


@api_bp.route("/jobs/fetch-external", methods=["POST"])
@require_jwt(hydrate=True)
def trigger_external_job_fetch():
    """
    Trigger external job fetching from LinkedIn API

    POST /api/jobs/fetch-external
    {
        "keywords": ["Python developer", "Data engineer"],
        "locations": ["Australia", "Sydney"],
        "job_types": ["fullTime", "contract"],
        "max_jobs_per_search": 20,
        "run_async": true
    }
    """
    try:
        data = request.get_json() or {}

        # Extract parameters with defaults
        keywords = data.get(
            "keywords", ["Python developer", "Data engineer", "Software engineer"]
        )
        locations = data.get("locations", ["Australia", "Sydney", "Melbourne"])
        job_types = data.get("job_types", ["fullTime"])
        max_jobs_per_search = data.get("max_jobs_per_search", 20)
        run_async = data.get("run_async", True)

        # Validate parameters
        if not isinstance(keywords, list) or len(keywords) == 0:
            return jsonify({"error": "keywords must be a non-empty list"}), 400

        if not isinstance(locations, list) or len(locations) == 0:
            return jsonify({"error": "locations must be a non-empty list"}), 400

        if max_jobs_per_search > 100:
            return jsonify({"error": "max_jobs_per_search cannot exceed 100"}), 400

        if run_async:
            # Run in background
            task_id = f"fetch_{int(time.time())}"

            # Store task info
            active_fetch_tasks[task_id] = {
                "task_id": task_id,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
                "parameters": {
                    "keywords": keywords,
                    "locations": locations,
                    "job_types": job_types,
                    "max_jobs_per_search": max_jobs_per_search,
                },
            }

            # Start background thread
            thread = threading.Thread(
                target=run_job_fetch_background,
                args=(task_id, active_fetch_tasks[task_id]["parameters"]),
            )
            thread.daemon = True
            thread.start()

            return (
                jsonify(
                    {
                        "message": "Job fetching started in background",
                        "task_id": task_id,
                        "status": "pending",
                        "estimated_duration": f"{len(keywords) * len(locations) * len(job_types) * 2} seconds",
                        "check_status_url": f"/api/jobs/fetch-status/{task_id}",
                    }
                ),
                202,
            )

        else:
            # Run synchronously
            result = fetchJobFromExternal(
                keywords=keywords,
                locations=locations,
                job_types=job_types,
                max_jobs_per_search=max_jobs_per_search,
            )

            return jsonify({"message": "Job fetching completed", "result": result}), 200

    except Exception as e:
        current_app.logger.error(f"Error in external job fetch: {e}")
        return (
            jsonify({"error": "Failed to fetch external jobs", "detail": str(e)}),
            500,
        )


@api_bp.route("/jobs/fetch-status/<task_id>", methods=["GET"])
@require_jwt(hydrate=True)
def get_fetch_status(task_id: str):
    """
    Get status of a background job fetching task

    GET /api/jobs/fetch-status/{task_id}
    """
    try:
        if task_id not in active_fetch_tasks:
            return jsonify({"error": "Task not found"}), 404

        task_info = active_fetch_tasks[task_id]

        return jsonify(task_info), 200

    except Exception as e:
        current_app.logger.error(f"Error getting fetch status: {e}")
        return jsonify({"error": "Failed to get task status"}), 500


@api_bp.route("/jobs/fetch-tasks", methods=["GET"])
@require_jwt(hydrate=True)
def list_fetch_tasks():
    """
    List all job fetching tasks (recent ones)

    GET /api/jobs/fetch-tasks
    """
    try:
        # Return only recent tasks (last 24 hours)
        now = datetime.utcnow()
        recent_tasks = {}

        for task_id, task_info in active_fetch_tasks.items():
            created_at = datetime.fromisoformat(task_info["created_at"])
            hours_ago = (now - created_at).total_seconds() / 3600

            if hours_ago < 24:  # Last 24 hours
                recent_tasks[task_id] = task_info

        return jsonify({"tasks": recent_tasks, "count": len(recent_tasks)}), 200

    except Exception as e:
        current_app.logger.error(f"Error listing fetch tasks: {e}")
        return jsonify({"error": "Failed to list tasks"}), 500


@api_bp.route("/jobs/fetch-external/test", methods=["POST"])
@require_jwt(hydrate=True)
def test_external_api():
    """
    Test external API connection without saving to database

    POST /api/jobs/fetch-external/test
    {
        "keywords": "Python developer",
        "location": "Sydney",
        "limit": 3
    }
    """
    try:
        data = request.get_json() or {}

        keywords = data.get("keywords", "Python developer")
        location = data.get("location", "Sydney")
        limit = min(data.get("limit", 3), 5)  # Max 5 for testing

        from jobmate_agent.services.external_apis.external_job_fetcher import (
            LinkedInJobFetcher,
        )

        fetcher = LinkedInJobFetcher()
        jobs = fetcher.search_jobs(
            keywords=keywords, location=location, limit=limit, jobType="fullTime"
        )

        return (
            jsonify(
                {
                    "message": "API test successful",
                    "jobs_found": len(jobs),
                    "sample_jobs": (
                        jobs[:2] if jobs else []
                    ),  # Return first 2 jobs as sample
                    "api_status": "connected" if jobs else "no_results",
                }
            ),
            200,
        )

    except ValueError as e:
        return (
            jsonify(
                {
                    "error": "Configuration error",
                    "detail": str(e),
                    "solution": "Please check your RAPIDAPI_KEY in environment variables",
                }
            ),
            400,
        )
    except Exception as e:
        current_app.logger.error(f"Error testing external API: {e}")
        return jsonify({"error": "Failed to test external API", "detail": str(e)}), 500
