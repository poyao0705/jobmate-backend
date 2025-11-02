from __future__ import annotations

import logging
import os
from flask import jsonify, request, g

import requests

from . import api_bp
from jobmate_agent.jwt_auth import require_jwt
from jobmate_agent.models import db, Resume, SkillGapReport, JobListing, SkillGapStatus
from jobmate_agent.services.career_engine.report_renderer import ReportRenderer
from jobmate_agent.agents.gap_agent import run_gap_agent
from jobmate_agent.services.career_engine.schemas import (
    analysis_to_transport_payload,
    load_analysis_from_storage,
)


def _notify_frontend_gap_ready(job_id: int) -> None:
    frontend_origin = os.getenv("FRONTEND_ORIGIN")
    if not frontend_origin:
        logger.info(
            "FRONTEND_ORIGIN not set; skipping gap report revalidation callback"
        )
        return

    url = frontend_origin.rstrip("/") + "/api/revalidate-gap"
    headers = {"Content-Type": "application/json"}

    revalidate_token = os.getenv("REVALIDATE_TOKEN")
    if revalidate_token:
        headers["Authorization"] = f"Bearer {revalidate_token}"

    try:
        response = requests.post(
            url, json={"jobId": job_id}, headers=headers, timeout=5
        )
        if response.status_code >= 400:
            logger.warning(
                "Gap report revalidation callback returned %s: %s",
                response.status_code,
                response.text,
            )
    except Exception:
        logger.exception("Failed to notify frontend about gap report completion")


logger = logging.getLogger(__name__)


def _get_default_resume_for_user(user_id: str) -> Resume | None:
    return Resume.get_default_resume(user_id)


@api_bp.route("/gap/run", methods=["POST"])
@require_jwt(hydrate=True)
def run_gap_analysis():
    """Run skill gap analysis for the given job using user's default resume.

    Request JSON: { "job_id": number }
    Response: { "gap_report_id": number, "score": number, "report_md": string }
    """
    try:
        payload = request.get_json(silent=True) or {}
        job_id = payload.get("job_id")
        if not isinstance(job_id, int):
            return jsonify({"error": "job_id must be an integer"}), 400

        user_id = g.user_sub
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401

        resume = _get_default_resume_for_user(user_id)
        if not resume:
            return jsonify({"error": "No default resume found for user"}), 404

        # Use LangGraph agent wrapper
        logger.info(
            f"[GAP] Starting gap analysis via API for user_id={user_id}, job_id={job_id}"
        )
        try:
            SkillGapStatus.set_status(user_id, job_id, "generating")
        except Exception:
            logger.exception(
                "Failed to mark gap status as generating for user_id=%s job_id=%s",
                user_id,
                job_id,
            )
        result = run_gap_agent(user_id, job_id)
        try:
            _notify_frontend_gap_ready(job_id)
        except Exception:
            logger.exception("Gap report frontend notification failed")

        # Update status based on run result
        try:
            if result.get("analysis_id"):
                SkillGapStatus.set_status(user_id, job_id, "ready")
            else:
                SkillGapStatus.clear_status(user_id, job_id)
        except Exception:
            logger.exception(
                "Failed to update gap status after run for user_id=%s job_id=%s",
                user_id,
                job_id,
            )

        logger.info(
            f"[GAP] Gap analysis completed for user_id={user_id}, job_id={job_id}, "
            f"overall_match={result.get('overall_match')}, analysis_id={result.get('analysis_id')}"
        )

        analysis_payload = result.get("analysis") or {}
        response_body = {
            "gap_report_id": result.get("analysis_id"),
            "analysis": analysis_payload or None,
        }
        return jsonify(response_body), 200
    except Exception as e:
        logger.exception("Failed to run gap analysis")
        if "user_id" in locals() and isinstance(job_id, int):
            try:
                SkillGapStatus.clear_status(user_id, job_id)
            except Exception:
                logger.exception(
                    "Failed to clear gap status after exception for user_id=%s job_id=%s",
                    user_id,
                    job_id,
                )
        return jsonify({"error": f"Failed to run gap analysis: {str(e)}"}), 500


@api_bp.route("/gap/by-job/<int:job_id>", methods=["GET"])
@require_jwt(hydrate=True)
def get_gap_report_by_job(job_id: int):
    """Fetch the most recent gap report for the user's default resume and job.
    Response: { id, score, matched_skills, missing_skills, weak_skills, report_md? }
    """
    try:
        user_id = g.user_sub
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401

        resume = _get_default_resume_for_user(user_id)
        if not resume:
            return jsonify({"error": "No default resume found for user"}), 404

        rec: SkillGapReport | None = (
            SkillGapReport.query.filter_by(resume_id=resume.id, job_listing_id=job_id)
            .order_by(SkillGapReport.created_at.desc())
            .first()
        )
        if not rec:
            logger.info(
                f"[GAP] get_gap_report_by_job: no report for user_id={user_id}, resume_id={resume.id}, job_id={job_id}"
            )
            return jsonify({"exists": False}), 200

        analysis = load_analysis_from_storage(
            analysis_json=rec.analysis_json,
            analysis_version=rec.analysis_version,
            score=rec.score,
            matched_skills=rec.matched_skills_json,
            missing_skills=rec.missing_skills_json,
            resume_skills=rec.resume_skills_json,
            context={
                "resume_id": rec.resume_id,
                "job_id": rec.job_listing_id,
                "processing_run_id": rec.processing_run_id,
            },
            analysis_id=rec.id,
        )

        if not analysis.report_markdown:
            renderer = ReportRenderer()
            analysis.report_markdown = renderer.render(analysis)

        payload = analysis_to_transport_payload(analysis)

        if rec.analysis_json is None:
            try:
                rec.analysis_version = analysis.version
                rec.analysis_json = payload
                db.session.commit()
            except Exception:
                db.session.rollback()

        resp = {
            "exists": True,
            "analysis": payload,
            "id": rec.id,
        }

        metrics = payload.get("metrics", {})
        matched = payload.get("matched_skills", [])
        missing = payload.get("missing_skills", [])
        resume_skills = payload.get("resume_skills", [])
        logger.info(
            f"[GAP] get_gap_report_by_job: returning report id={rec.id} score={metrics.get('overall_score', rec.score)} matched={len(matched)} missing={len(missing)} resume_skills={len(resume_skills)}"
        )
        return jsonify(resp), 200
    except Exception as e:
        logger.exception("Failed to fetch gap report")
        return jsonify({"error": f"Failed to fetch gap report: {str(e)}"}), 500


@api_bp.route("/gap/by-job/<int:job_id>", methods=["DELETE"])
@require_jwt(hydrate=True)
def delete_gap_report_by_job(job_id: int):
    """Delete all gap reports for the user's default resume and given job."""
    try:
        user_id = g.user_sub
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401

        resume = _get_default_resume_for_user(user_id)
        if not resume:
            return jsonify({"error": "No default resume found for user"}), 404

        deleted = SkillGapReport.query.filter_by(
            resume_id=resume.id, job_listing_id=job_id
        ).delete(synchronize_session=False)
        db.session.commit()
        try:
            SkillGapStatus.clear_status(user_id, job_id)
        except Exception:
            logger.exception(
                "Failed to clear gap status after delete for user_id=%s job_id=%s",
                user_id,
                job_id,
            )
        return jsonify({"deleted": int(deleted)}), 200
    except Exception as e:
        db.session.rollback()
        logger.exception("Failed to delete gap report")
        return jsonify({"error": f"Failed to delete gap report: {str(e)}"}), 500
