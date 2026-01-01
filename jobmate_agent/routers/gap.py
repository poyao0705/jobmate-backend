"""FastAPI router for skill gap analysis endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from typing import Tuple, Dict, Any, Optional
import logging

from jobmate_agent.extensions_fastapi import get_db
from jobmate_agent.jwt_auth_fastapi import get_current_user_with_profile
from jobmate_agent.models_fastapi import Resume, SkillGapReport, JobListing

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/gap/run")
async def run_gap_analysis(
    request_data: Dict[str, Any],
    user_data: Tuple[Dict[str, Any], Any] = Depends(get_current_user_with_profile),
    db: Session = Depends(get_db),
):
    """Run skill gap analysis for a job using user's default resume.
    
    Request: { "job_id": number }
    Response: { "gap_report_id": number, "analysis": {...} }
    """
    jwt_payload, user_profile = user_data
    user_id = jwt_payload.get("sub")
    
    job_id = request_data.get("job_id")
    if not job_id or not isinstance(job_id, int):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="job_id must be an integer"
        )
    
    # Get user's default resume
    default_resume = db.query(Resume).filter_by(
        user_id=user_id,
        is_default=True
    ).first()
    
    if not default_resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No default resume found for user"
        )
    
    # TODO: Implement actual gap analysis using agents/gap_agent
    # For now, return stub
    logger.info(f"Gap analysis requested for user_id={user_id}, job_id={job_id}")
    
    return {
        "message": "Gap analysis to be implemented",
        "gap_report_id": None,
        "analysis": None
    }


@router.get("/gap/by-job/{job_id}")
async def get_gap_report_by_job(
    job_id: int,
    user_data: Tuple[Dict[str, Any], Any] = Depends(get_current_user_with_profile),
    db: Session = Depends(get_db),
):
    """Fetch the most recent gap report for user's default resume and job.
    
    Response: { exists, id, analysis: {...} }
    """
    jwt_payload, user_profile = user_data
    user_id = jwt_payload.get("sub")
    
    # Get user's default resume
    default_resume = db.query(Resume).filter_by(
        user_id=user_id,
        is_default=True
    ).first()
    
    if not default_resume:
        logger.info(f"No default resume for user_id={user_id}")
        return {"exists": False}
    
    # Get most recent gap report for this resume and job
    report = (
        db.query(SkillGapReport)
        .filter_by(resume_id=default_resume.id, job_listing_id=job_id)
        .order_by(SkillGapReport.created_at.desc())
        .first()
    )
    
    if not report:
        logger.info(f"No gap report found for user_id={user_id}, job_id={job_id}")
        return {"exists": False}
    
    # Use stored analysis_json if available, otherwise build from database fields
    if report.analysis_json:
        analysis = report.analysis_json
    else:
        # Build analysis payload from database fields
        matched_count = len(report.matched_skills_json) if report.matched_skills_json else 0
        missing_count = len(report.missing_skills_json) if report.missing_skills_json else 0
        resume_count = len(report.resume_skills_json) if report.resume_skills_json else 0
        weak_count = len(report.weak_skills_json) if report.weak_skills_json else 0
        
        analysis = {
            "version": report.analysis_version or "1.0",
            "analysis_id": report.id,
            "context": {
                "resume_id": report.resume_id,
                "job_id": report.job_listing_id,
                "processing_run_id": report.processing_run_id,
            },
            "metrics": {
                "overall_score": round(report.score, 2),
                "overall_percent": round(report.score * 100, 0),
                "matched_skill_count": matched_count,
                "missing_skill_count": missing_count,
                "underqualified_skill_count": weak_count,
                "resume_skill_count": resume_count,
                "job_skill_count": matched_count + missing_count,
            },
            "matched_skills": report.matched_skills_json or [],
            "missing_skills": report.missing_skills_json or [],
            "resume_skills": report.resume_skills_json or [],
            "report_markdown": "# Gap Analysis\n...",  # TODO: Generate from data
            "diagnostics": {},
            "extras": {},
        }
    
    logger.info(
        f"Returning gap report id={report.id} for user_id={user_id}, job_id={job_id}, "
        f"score={report.score}"
    )
    
    return {
        "exists": True,
        "id": report.id,
        "analysis": analysis,
    }
