"""
FastAPI router for resume-related endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Tuple, Dict, Any

from jobmate_agent.extensions_fastapi import get_db
from jobmate_agent.models_fastapi import Resume, SkillGapReport
from jobmate_agent.schemas import (
    ResumeUploadResponse,
    ResumeResponse,
    ResumeListResponse,
    DownloadURLResponse,
    SuccessResponse,
)
from jobmate_agent.jwt_auth_fastapi import get_user_sub, get_current_user_with_profile
from jobmate_agent.services.resume_management import ResumeStorageService, ResumePipeline
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/resume/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    resume_file: UploadFile = File(...),
    user_data: Tuple[Dict[str, Any], Any] = Depends(get_current_user_with_profile),
    db: Session = Depends(get_db),
):
    """Complete resume upload with vectorization (used by frontend)"""
    try:
        jwt_payload, user_profile = user_data
        user_id = jwt_payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not authenticated"
            )

        if not resume_file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file selected"
            )

        # Use the complete pipeline for processing
        pipeline = ResumePipeline()
        result = pipeline.process_uploaded_file(resume_file.file, user_id, extract_sections=False)

        if result.get("success"):
            return ResumeUploadResponse(
                resume_id=result.get("resume_id"),
                message="Resume uploaded and processed successfully",
                chunks_created=result.get("chunks_created", 0),
                text_length=result.get("text_length", 0),
                s3_key=result.get("s3_key"),
                bucket=result.get("bucket"),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Upload failed")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resume upload failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload resume: {str(e)}"
        )


@router.get("/resume/{resume_id}/download-url", response_model=DownloadURLResponse)
async def get_download_url(
    resume_id: int,
    user_data: Tuple[Dict[str, Any], Any] = Depends(get_current_user_with_profile),
    db: Session = Depends(get_db),
):
    """Generate a presigned URL for downloading/viewing a resume file"""
    try:
        jwt_payload, user_profile = user_data
        user_id = jwt_payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not authenticated"
            )

        # Get the resume record
        resume = db.query(Resume).filter(
            Resume.id == resume_id,
            Resume.user_id == user_id
        ).first()
        
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found"
            )

        # Use the service to generate download URL
        processor = ResumeStorageService()
        result = processor.generate_download_url(resume)

        return DownloadURLResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate download URL: {str(e)}"
        )


@router.get("/resumes")
async def get_user_resumes(
    user_data: Tuple[Dict[str, Any], Any] = Depends(get_current_user_with_profile),
    db: Session = Depends(get_db),
):
    """Get all resumes for the current user"""
    try:
        jwt_payload, user_profile = user_data
        user_id = jwt_payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not authenticated"
            )

        resumes = db.query(Resume).filter(
            Resume.user_id == user_id
        ).order_by(Resume.created_at.desc()).all()

        resume_list = []
        for resume in resumes:
            resume_list.append({
                "id": resume.id,
                "file_url": resume.file_url or resume.s3_key,
                "original_filename": resume.original_filename or resume.filename,
                "is_default": resume.is_default,
                "created_at": resume.created_at.isoformat() if resume.created_at else None,
                "parsed_json": resume.parsed_json,
            })

        return {"resumes": resume_list}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch resumes: {str(e)}"
        )


@router.post("/resumes/{resume_id}/set-default", response_model=SuccessResponse)
async def set_default_resume(
    resume_id: int,
    user_data: Tuple[Dict[str, Any], Any] = Depends(get_current_user_with_profile),
    db: Session = Depends(get_db),
):
    """Set a resume as default for the current user"""
    try:
        jwt_payload, user_profile = user_data
        user_id = jwt_payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not authenticated"
            )

        # Check if resume exists and belongs to user
        resume = db.query(Resume).filter(
            Resume.id == resume_id,
            Resume.user_id == user_id
        ).first()
        
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found or not owned by user"
            )

        # Unset all other resumes as default
        db.query(Resume).filter(
            Resume.user_id == user_id
        ).update({"is_default": False})
        
        # Set this resume as default
        resume.is_default = True
        db.commit()

        return SuccessResponse(message="Resume set as default successfully")

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set default resume: {str(e)}"
        )


@router.get("/resumes/default", response_model=ResumeResponse)
async def get_default_resume(
    user_data: Tuple[Dict[str, Any], Any] = Depends(get_current_user_with_profile),
    db: Session = Depends(get_db),
):
    """Get the default resume for the current user"""
    try:
        jwt_payload, user_profile = user_data
        user_id = jwt_payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not authenticated"
            )

        default_resume = db.query(Resume).filter(
            Resume.user_id == user_id,
            Resume.is_default == True
        ).first()

        if not default_resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No default resume found"
            )

        return default_resume

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get default resume: {str(e)}"
        )


@router.delete("/resumes/{resume_id}", response_model=SuccessResponse)
async def delete_resume(
    resume_id: int,
    user_data: Tuple[Dict[str, Any], Any] = Depends(get_current_user_with_profile),
    db: Session = Depends(get_db),
):
    """Delete a resume (only if not default) and remove from S3"""
    try:
        jwt_payload, user_profile = user_data
        user_id = jwt_payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not authenticated"
            )

        resume = db.query(Resume).filter(
            Resume.id == resume_id,
            Resume.user_id == user_id
        ).first()

        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found or not owned by user"
            )

        if resume.is_default:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete default resume. Set another resume as default first."
            )

        # Store S3 info before deleting from database
        s3_bucket = resume.bucket
        s3_key = resume.s3_key

        # Delete the associated skill gap reports
        db.query(SkillGapReport).filter(
            SkillGapReport.resume_id == resume.id
        ).delete(synchronize_session=False)
        db.commit()

        # Delete from database
        db.delete(resume)
        db.commit()

        # Delete from S3 if S3 info exists
        if s3_bucket and s3_key:
            processor = ResumeStorageService()
            processor.delete_resume_from_s3(s3_bucket, s3_key)

        return SuccessResponse(message="Resume deleted successfully")

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete resume: {str(e)}"
        )


@router.get("/resumes/search")
async def search_resumes(
    query: str,
    k: int = 10,
    user_data: Tuple[Dict[str, Any], Any] = Depends(get_current_user_with_profile),
    db: Session = Depends(get_db),
):
    """Search resumes using semantic search"""
    try:
        jwt_payload, user_profile = user_data
        user_id = jwt_payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not authenticated"
            )

        if not query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query parameter is required"
            )

        # Simple text search in raw_text
        from sqlalchemy import text
        
        resumes = db.query(Resume).filter(
            Resume.user_id == user_id,
            Resume.raw_text.ilike(f"%{query}%")
        ).all()

        # Format results for API response
        search_results = []
        for resume in resumes:
            if resume.raw_text and query.lower() in resume.raw_text.lower():
                search_results.append({
                    "resume_id": resume.id,
                    "content": resume.raw_text,
                    "relevance_score": 1.0,
                    "metadata": {
                        "resume_id": resume.id,
                        "filename": resume.filename,
                        "created_at": resume.created_at.isoformat() if resume.created_at else None,
                    },
                })

        return {
            "query": query,
            "results": search_results,
            "total_found": len(search_results),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )
