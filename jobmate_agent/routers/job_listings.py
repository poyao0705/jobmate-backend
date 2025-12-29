"""FastAPI router for job listing endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Tuple, Dict, Any, Optional

from jobmate_agent.extensions_fastapi import get_db
from jobmate_agent.models_fastapi import JobListing
from jobmate_agent.jwt_auth_fastapi import get_current_user_with_profile
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/jobs")
async def get_job_listings(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    job_type: Optional[str] = None,
    location: Optional[str] = None,
    company: Optional[str] = None,
    user_data: Tuple[Dict[str, Any], Any] = Depends(get_current_user_with_profile),
    db: Session = Depends(get_db),
):
    """Get all active job listings with pagination and filtering"""
    try:
        # Build query with filters
        query = db.query(JobListing)
        
        # Apply filters if provided
        if job_type:
            query = query.filter(JobListing.job_type == job_type)
        if location:
            query = query.filter(JobListing.location.ilike(f"%{location}%"))
        if company:
            query = query.filter(JobListing.company.ilike(f"%{company}%"))
        
        # Get total count
        total = query.count()
        
        # Calculate pagination
        total_pages = (total + limit - 1) // limit
        offset = (page - 1) * limit
        
        # Get paginated results
        jobs = query.offset(offset).limit(limit).all()
        
        # Convert to dict format
        job_list = []
        for job in jobs:
            job_dict = {
                "id": job.id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "description": job.description,
                "url": job.url,
                "posted_date": job.posted_date.isoformat() if job.posted_date else None,
                "source": job.source,
                "external_id": job.external_id,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "required_skills": job.required_skills,
                "preferred_skills": job.preferred_skills,
                "experience_level": job.experience_level,
                "salary_min": job.salary_min,
                "salary_max": job.salary_max,
            }
            job_list.append(job_dict)
        
        # Return with pagination info
        return {
            "jobs": job_list,
            "pagination": {
                "total": total,
                "current_page": page,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
                "per_page": limit,
            }
        }
    
    except Exception as e:
        logger.error(f"Error in get_job_listings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/jobs/{job_id}")
async def get_job_by_id(
    job_id: int,
    user_data: Tuple[Dict[str, Any], Any] = Depends(get_current_user_with_profile),
    db: Session = Depends(get_db),
):
    """Get specific job listing by ID"""
    try:
        job = db.query(JobListing).filter(JobListing.id == job_id).first()
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        
        return {
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "description": job.description,
            "url": job.url,
            "posted_date": job.posted_date.isoformat() if job.posted_date else None,
            "source": job.source,
            "external_id": job.external_id,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "required_skills": job.required_skills,
            "preferred_skills": job.preferred_skills,
            "experience_level": job.experience_level,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve job: {str(e)}"
        )
