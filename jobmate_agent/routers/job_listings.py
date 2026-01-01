"""FastAPI router for job listing endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session, select, func
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
        logger.info(f"Fetching jobs: page={page}, limit={limit}")
        
        # Build query with filters using SQLModel syntax
        statement = select(JobListing).where(JobListing.is_active == True)
        
        # Apply filters if provided
        if job_type:
            statement = statement.where(JobListing.job_type == job_type)
        if location:
            statement = statement.where(JobListing.location.ilike(f"%{location}%"))
        if company:
            statement = statement.where(JobListing.company.ilike(f"%{company}%"))
        
        # Get total count (faster query)
        count_statement = select(func.count()).select_from(JobListing).where(JobListing.is_active == True)
        if job_type:
            count_statement = count_statement.where(JobListing.job_type == job_type)
        if location:
            count_statement = count_statement.where(JobListing.location.ilike(f"%{location}%"))
        if company:
            count_statement = count_statement.where(JobListing.company.ilike(f"%{company}%"))
        
        total = db.exec(count_statement).one()
        logger.info(f"Total jobs found: {total}")
        
        # Calculate pagination
        total_pages = (total + limit - 1) // limit if total > 0 else 1
        offset = (page - 1) * limit
        
        # Get paginated results with ordering
        statement = statement.order_by(JobListing.created_at.desc()).offset(offset).limit(limit)
        jobs = db.exec(statement).all()
        
        logger.info(f"Retrieved {len(jobs)} jobs")
        
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
