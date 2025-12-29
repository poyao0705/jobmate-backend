"""FastAPI router for job collection endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Tuple, Dict, Any
from datetime import datetime

from jobmate_agent.extensions_fastapi import get_db
from jobmate_agent.jwt_auth_fastapi import get_current_user_with_profile
from jobmate_agent.models_fastapi import JobCollection, JobListing

router = APIRouter()


@router.get("/job-collections")
async def get_job_collections(
    include_details: bool = False,
    user_data: Tuple[Dict[str, Any], Any] = Depends(get_current_user_with_profile),
    db: Session = Depends(get_db),
):
    """Get all saved jobs for the current user.
    
    Args:
        include_details: If True, includes full job listing details via JOIN.
                        If False (default), returns only IDs and timestamps.
    """
    jwt_payload, user_profile = user_data
    user_id = jwt_payload.get("sub")
    
    if include_details:
        # JOIN with job_listings to include full job details
        results = (
            db.query(JobCollection, JobListing)
            .join(JobListing, JobCollection.job_listing_id == JobListing.id)
            .filter(JobCollection.user_id == user_id)
            .all()
        )
        
        return {
            "collections": [
                {
                    "id": col.id,
                    "job_id": col.job_listing_id,
                    "job_listing_id": col.job_listing_id,
                    "added_at": col.added_at.isoformat() if col.added_at else None,
                    "job": {
                        "id": job.id,
                        "title": job.title,
                        "company": job.company,
                        "location": job.location,
                        "job_type": job.job_type,
                        "description": job.description,
                        "requirements": job.requirements,
                        "salary_min": job.salary_min,
                        "salary_max": job.salary_max,
                        "salary_currency": job.salary_currency,
                        "external_url": job.external_url,
                        "company_logo_url": job.company_logo_url,
                        "company_website": job.company_website,
                        "required_skills": job.required_skills,
                        "preferred_skills": job.preferred_skills,
                        "is_remote": job.is_remote,
                        "date_posted": job.date_posted.isoformat() if job.date_posted else None,
                        "date_expires": job.date_expires.isoformat() if job.date_expires else None,
                    },
                }
                for col, job in results
            ]
        }
    else:
        # Simple query without JOIN (current behavior)
        collections = db.query(JobCollection).filter_by(user_id=user_id).all()
        
        return {
            "collections": [
                {
                    "id": col.id,
                    "job_id": col.job_listing_id,
                    "job_listing_id": col.job_listing_id,
                    "added_at": col.added_at.isoformat() if col.added_at else None,
                }
                for col in collections
            ]
        }


@router.get("/job-collections/{job_listing_id}/status")
async def get_job_collection_status(
    job_listing_id: int,
    user_data: Tuple[Dict[str, Any], Any] = Depends(get_current_user_with_profile),
    db: Session = Depends(get_db),
):
    """Check if a specific job is saved by the current user."""
    jwt_payload, user_profile = user_data
    user_id = jwt_payload.get("sub")
    
    collection = db.query(JobCollection).filter_by(
        user_id=user_id,
        job_listing_id=job_listing_id
    ).first()
    
    if not collection:
        return {"saved": False, "saved_at": None}
    
    return {
        "saved": True,
        "saved_at": collection.added_at.isoformat() if collection.added_at else None,
    }


@router.post("/job-collections/{job_listing_id}")
async def save_job(
    job_listing_id: int,
    user_data: Tuple[Dict[str, Any], Any] = Depends(get_current_user_with_profile),
    db: Session = Depends(get_db),
):
    """Save a job to the user's collection."""
    jwt_payload, user_profile = user_data
    user_id = jwt_payload.get("sub")
    
    # Check if already saved
    existing = db.query(JobCollection).filter_by(
        user_id=user_id,
        job_listing_id=job_listing_id
    ).first()
    
    if existing:
        return {
            "success": True,
            "message": "Job already saved",
            "job_id": job_listing_id,
            "saved_at": existing.added_at.isoformat() if existing.added_at else None,
        }
    
    # Create new collection entry
    new_collection = JobCollection(
        user_id=user_id,
        job_listing_id=job_listing_id,
        added_at=datetime.utcnow()
    )
    
    db.add(new_collection)
    db.commit()
    db.refresh(new_collection)
    
    return {
        "success": True,
        "message": "Job saved successfully",
        "job_id": job_listing_id,
        "saved_at": new_collection.added_at.isoformat(),
    }


@router.delete("/job-collections/{job_listing_id}")
async def unsave_job(
    job_listing_id: int,
    user_data: Tuple[Dict[str, Any], Any] = Depends(get_current_user_with_profile),
    db: Session = Depends(get_db),
):
    """Remove a job from the user's collection."""
    jwt_payload, user_profile = user_data
    user_id = jwt_payload.get("sub")
    
    collection = db.query(JobCollection).filter_by(
        user_id=user_id,
        job_listing_id=job_listing_id
    ).first()
    
    if not collection:
        raise HTTPException(status_code=404, detail="Job not in collection")
    
    db.delete(collection)
    db.commit()
    
    return {
        "success": True,
        "message": "Job removed from collection",
        "job_id": job_listing_id,
    }

