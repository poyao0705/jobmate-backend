"""
Job Collections API endpoints
Provides REST API endpoints to manage saved jobs
"""

from flask import request, jsonify, g
from datetime import datetime, timezone
import logging
import threading
from jobmate_agent.blueprints.api import api_bp
from jobmate_agent.jwt_auth import require_jwt
from jobmate_agent.models import (
    JobCollection,
    JobListing,
    UserProfile,
    Resume,
    SkillGapReport,
    SkillGapStatus,
)
from jobmate_agent.extensions import db
from jobmate_agent.agents.gap_agent import run_gap_agent
from .gap import _notify_frontend_gap_ready

logger = logging.getLogger(__name__)


def _trigger_gap_analysis_background(user_id: str, job_id: int, app):
    """Run gap analysis in a background thread with Flask app context."""

    def _run_with_context():
        with app.app_context():
            try:
                logger.info(
                    f"[GAP] Starting background gap analysis for user_id={user_id}, job_id={job_id}"
                )
                result = run_gap_agent(user_id, job_id)

                # Update status based on result
                try:
                    if result.get("analysis_id"):
                        SkillGapStatus.set_status(user_id, job_id, "ready")
                        logger.info(
                            f"[GAP] Background gap analysis completed successfully for user_id={user_id}, job_id={job_id}"
                        )
                        # Notify frontend that gap report is ready
                        try:
                            _notify_frontend_gap_ready(job_id)
                        except Exception:
                            logger.exception(
                                f"Gap report frontend notification failed for job_id={job_id}"
                            )
                    else:
                        SkillGapStatus.clear_status(user_id, job_id)
                        logger.warning(
                            f"[GAP] Background gap analysis completed without analysis_id for user_id={user_id}, job_id={job_id}"
                        )
                except Exception:
                    logger.exception(
                        f"Failed to update gap status after background run for user_id={user_id}, job_id={job_id}"
                    )

            except Exception as e:
                logger.exception(
                    f"Failed to run background gap analysis for user_id={user_id}, job_id={job_id}"
                )
                try:
                    SkillGapStatus.clear_status(user_id, job_id)
                except Exception:
                    logger.exception(
                        f"Failed to clear gap status after background error for user_id={user_id}, job_id={job_id}"
                    )

    thread = threading.Thread(target=_run_with_context, daemon=True)
    thread.start()
    logger.info(
        f"[GAP] Started background thread for gap analysis user_id={user_id}, job_id={job_id}"
    )


@api_bp.route("/job-collections", methods=["GET"])
@require_jwt(hydrate=True)
def get_saved_jobs():
    """Get all saved jobs for the current user"""
    try:
        # Get user from hydrated profile (set by @require_jwt(hydrate=True))
        user_profile = g.user_profile
        if not user_profile:
            return jsonify({"error": "User profile not found"}), 404

        # Get saved jobs with job details
        saved_jobs = (
            db.session.query(JobCollection, JobListing)
            .join(JobListing, JobCollection.job_listing_id == JobListing.id)
            .filter(JobCollection.user_id == user_profile.id)
            .filter(JobListing.is_active == True)
            .order_by(JobCollection.added_at.desc())
            .all()
        )

        job_ids = [job_listing.id for _, job_listing in saved_jobs]

        # Prefetch gap statuses and reports to avoid N+1 queries
        status_map: dict[int, str] = {}
        if job_ids:
            status_rows = (
                SkillGapStatus.query.filter_by(user_id=user_profile.id)
                .filter(SkillGapStatus.job_listing_id.in_(job_ids))
                .all()
            )
            status_map = {row.job_listing_id: row.status for row in status_rows}

        default_resume = Resume.get_default_resume(user_profile.id) if job_ids else None
        ready_job_ids: set[int] = set()
        if default_resume and job_ids:
            ready_job_ids = {
                job_id
                for (job_id,) in db.session.query(SkillGapReport.job_listing_id)
                .filter_by(resume_id=default_resume.id)
                .filter(SkillGapReport.job_listing_id.in_(job_ids))
                .distinct()
            }

        # Format response with gap state metadata
        result = []
        for job_collection, job_listing in saved_jobs:
            job_id = job_listing.id
            job_data = job_listing.to_dict()
            job_data["saved_at"] = job_collection.added_at.isoformat()
            job_data["bookmarked"] = True  # Mark as saved

            if job_id in ready_job_ids:
                gap_state = "ready"
            elif status_map.get(job_id) == "generating":
                gap_state = "generating"
            else:
                gap_state = "none"

            job_data["gap_state"] = gap_state
            job_data["has_gap"] = gap_state == "ready"

            result.append(job_data)

        return jsonify({"jobs": result, "total_count": len(result)})

    except Exception as e:
        logger.error(f"Error getting saved jobs: {e}")
        return (
            jsonify({"error": "Failed to retrieve saved jobs", "detail": str(e)}),
            500,
        )


@api_bp.route("/job-collections/<int:job_id>", methods=["POST"])
@require_jwt(hydrate=True)
def save_job(job_id):
    """Save a job to user's collection."""
    try:
        # Get user from hydrated profile (set by @require_jwt(hydrate=True))
        user_profile = g.user_profile
        if not user_profile:
            return jsonify({"error": "User profile not found"}), 404

        # Check if job exists
        job = JobListing.query.get(job_id)
        if not job:
            return jsonify({"error": "Job not found"}), 404

        # Check if job is already saved
        existing = JobCollection.query.filter_by(
            user_id=user_profile.id, job_listing_id=job_id
        ).first()

        if existing:
            return jsonify({"message": "Job already saved", "saved": True}), 200

        # Save job to collection
        job_collection = JobCollection(
            user_id=user_profile.id,
            job_listing_id=job_id,
            added_at=datetime.now(timezone.utc),
        )

        db.session.add(job_collection)
        db.session.commit()

        # Set status to "generating" and trigger gap analysis in background
        try:
            SkillGapStatus.set_status(user_profile.id, job_id, "generating")
            # Get the Flask app instance before spawning thread
            from flask import current_app

            app = current_app._get_current_object()
            # Trigger gap report generation automatically in background
            _trigger_gap_analysis_background(user_profile.id, job_id, app)
        except Exception:
            logger.exception(
                "Failed to record gap status or trigger analysis for user_id=%s job_id=%s",
                user_profile.id,
                job_id,
            )

        return (
            jsonify(
                {
                    "message": "Job saved successfully",
                    "saved": True,
                    "saved_at": job_collection.added_at.isoformat(),
                }
            ),
            201,
        )

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving job {job_id}: {e}")
        return jsonify({"error": "Failed to save job", "detail": str(e)}), 500


@api_bp.route("/job-collections/<int:job_id>", methods=["DELETE"])
@require_jwt(hydrate=True)
def unsave_job(job_id):
    """Remove a job from user's collection and delete related gap reports."""
    try:
        # Get user from hydrated profile (set by @require_jwt(hydrate=True))
        user_profile = g.user_profile
        if not user_profile:
            return jsonify({"error": "User profile not found"}), 404

        # Find saved job
        job_collection = JobCollection.query.filter_by(
            user_id=user_profile.id, job_listing_id=job_id
        ).first()

        if not job_collection:
            return (
                jsonify({"message": "Job not found in collection", "saved": False}),
                404,
            )

        # Remove from collection
        db.session.delete(job_collection)
        db.session.commit()

        # Delete gap reports for this job + default resume
        try:
            default_resume = Resume.get_default_resume(user_profile.id)
            if default_resume:
                SkillGapReport.query.filter_by(
                    resume_id=default_resume.id, job_listing_id=job_id
                ).delete(synchronize_session=False)
                db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception(f"Failed to delete gap reports for job_id={job_id}")

        try:
            SkillGapStatus.clear_status(user_profile.id, job_id)
        except Exception:
            logger.exception(
                "Failed to clear gap status after unsave for user_id=%s job_id=%s",
                user_profile.id,
                job_id,
            )

        return jsonify({"message": "Job removed from collection", "saved": False}), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error removing job {job_id}: {e}")
        return jsonify({"error": "Failed to remove job", "detail": str(e)}), 500


@api_bp.route("/job-collections/<int:job_id>/status", methods=["GET"])
@require_jwt(hydrate=True)
def check_job_saved_status(job_id):
    """Check if a job is saved by the current user"""
    try:
        # Get user from hydrated profile (set by @require_jwt(hydrate=True))
        user_profile = g.user_profile
        if not user_profile:
            return jsonify({"error": "User profile not found"}), 404

        # Check if job is saved
        job_collection = JobCollection.query.filter_by(
            user_id=user_profile.id, job_listing_id=job_id
        ).first()

        return jsonify(
            {
                "job_id": job_id,
                "saved": job_collection is not None,
                "saved_at": (
                    job_collection.added_at.isoformat() if job_collection else None
                ),
            }
        )

    except Exception as e:
        logger.error(f"Error checking job {job_id} status: {e}")
        return jsonify({"error": "Failed to check job status", "detail": str(e)}), 500
