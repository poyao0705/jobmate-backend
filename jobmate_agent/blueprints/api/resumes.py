from flask import Blueprint, request, jsonify
from jobmate_agent.models import db, Resume, UserProfile, SkillGapReport
from jobmate_agent.jwt_auth import require_jwt
from jobmate_agent.blueprints.api import api_bp
from flask import g
from jobmate_agent.services.resume_management import ResumeStorageService
import logging

logger = logging.getLogger(__name__)


# Create blueprint for resume-related endpoints
@api_bp.route("/resume/upload", methods=["POST"])
@require_jwt(hydrate=True)
def upload_resume():
    """Complete resume upload with vectorization (used by frontend)"""
    try:
        user_id = g.user_sub
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401

        # Check if file is present in request
        if "resume_file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["resume_file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        # Avoid pre-reading the stream here; downstream pipeline will read once safely

        # Use the complete pipeline for processing
        from jobmate_agent.services.resume_management import ResumePipeline

        pipeline = ResumePipeline()
        result = pipeline.process_uploaded_file(file, user_id, extract_sections=False)

        if result.get("success"):
            return jsonify(
                {
                    "resume_id": result.get("resume_id"),
                    "message": "Resume uploaded and processed successfully",
                    "chunks_created": result.get("chunks_created", 0),
                    "text_length": result.get("text_length", 0),
                    "s3_key": result.get("s3_key"),
                    "bucket": result.get("bucket"),
                }
            )
        else:
            return jsonify({"error": result.get("error", "Upload failed")}), 500

    except Exception as e:
        logger.error(f"Resume upload failed: {str(e)}")
        return jsonify({"error": f"Failed to upload resume: {str(e)}"}), 500


## Removed unused presigned upload completion endpoint


@api_bp.route("/resume/<int:resume_id>/download-url", methods=["GET"])
@require_jwt(hydrate=True)
def get_download_url(resume_id):
    """Generate a presigned URL for downloading/viewing a resume file"""
    try:
        user_id = g.user_sub
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401

        # Get the resume record
        resume = Resume.query.filter_by(id=resume_id, user_id=user_id).first()
        if not resume:
            return jsonify({"error": "Resume not found"}), 404

        # Use the service to generate download URL
        processor = ResumeStorageService()
        result = processor.generate_download_url(resume)

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": f"Failed to generate download URL: {str(e)}"}), 500


@api_bp.route("/resumes", methods=["GET"])
@require_jwt(hydrate=True)
def get_user_resumes():
    """Get all resumes for the current user"""
    try:
        user_id = g.user_sub
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401

        resumes = (
            Resume.query.filter_by(user_id=user_id)
            .order_by(Resume.created_at.desc())
            .all()
        )

        resume_list = []
        for resume in resumes:
            resume_list.append(
                {
                    "id": resume.id,
                    "file_url": resume.file_url,
                    "original_filename": resume.original_filename,
                    "is_default": resume.is_default,
                    "created_at": (
                        resume.created_at.isoformat() if resume.created_at else None
                    ),
                    "parsed_json": resume.parsed_json,
                }
            )

        return jsonify({"resumes": resume_list})

    except Exception as e:
        return jsonify({"error": f"Failed to fetch resumes: {str(e)}"}), 500


@api_bp.route("/resumes/<int:resume_id>/set-default", methods=["POST"])
@require_jwt(hydrate=True)
def set_default_resume(resume_id):
    """Set a resume as default for the current user"""
    try:
        user_id = g.user_sub
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401

        # Use the static method from the Resume model
        success = Resume.set_default_resume(user_id, resume_id)

        if success:
            return jsonify({"message": "Resume set as default successfully"})
        else:
            return jsonify({"error": "Resume not found or not owned by user"}), 404

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to set default resume: {str(e)}"}), 500


@api_bp.route("/resumes/default", methods=["GET"])
@require_jwt(hydrate=True)
def get_default_resume():
    """Get the default resume for the current user"""
    try:
        user_id = g.user_sub
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401

        default_resume = Resume.get_default_resume(user_id)

        if default_resume:
            return jsonify(
                {
                    "id": default_resume.id,
                    "file_url": default_resume.file_url,
                    "original_filename": default_resume.original_filename,
                    "is_default": default_resume.is_default,
                    "created_at": (
                        default_resume.created_at.isoformat()
                        if default_resume.created_at
                        else None
                    ),
                    "parsed_json": default_resume.parsed_json,
                }
            )
        else:
            return jsonify({"error": "No default resume found"}), 404

    except Exception as e:
        return jsonify({"error": f"Failed to get default resume: {str(e)}"}), 500


@api_bp.route("/resumes/<int:resume_id>", methods=["DELETE"])
@require_jwt(hydrate=True)
def delete_resume(resume_id):
    """Delete a resume (only if not default) and remove from S3"""
    try:
        user_id = g.user_sub
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401

        resume = Resume.query.filter_by(id=resume_id, user_id=user_id).first()

        if not resume:
            return jsonify({"error": "Resume not found or not owned by user"}), 404

        if resume.is_default:
            return (
                jsonify(
                    {
                        "error": "Cannot delete default resume. Set another resume as default first."
                    }
                ),
                400,
            )

        # Store S3 info before deleting from database
        s3_bucket = resume.s3_bucket
        s3_key = resume.s3_key

        # Delete the associated skill gap reports
        SkillGapReport.query.filter_by(resume_id=resume.id).delete(
            synchronize_session=False
        )
        db.session.commit()

        # Delete from database first
        db.session.delete(resume)
        db.session.commit()

        # Delete from S3 if S3 info exists
        if s3_bucket and s3_key:
            processor = ResumeStorageService()
            processor.delete_resume_from_s3(s3_bucket, s3_key)

        # Note: Vector store deletion removed in skill-only mode

        return jsonify({"message": "Resume deleted successfully"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to delete resume: {str(e)}"}), 500


@api_bp.route("/resumes/search", methods=["GET"])
@require_jwt(hydrate=True)
def search_resumes():
    """Search resumes using semantic search"""
    try:
        user_id = g.user_sub
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401

        query = request.args.get("query")
        if not query:
            return jsonify({"error": "Query parameter is required"}), 400

        k = int(request.args.get("k", 10))  # Number of results to return

        # Simple text search in raw_text (no vectorization in skill-only mode)
        from jobmate_agent.models import Resume
        from sqlalchemy import text

        resumes = Resume.query.filter(
            Resume.user_id == user_id,
            text("parsed_json->>'raw_text' ILIKE :query").params(query=f"%{query}%"),
        ).all()

        # Format results for API response
        search_results = []
        for resume in resumes:
            raw_text = (
                resume.parsed_json.get("raw_text", "") if resume.parsed_json else ""
            )
            if query.lower() in raw_text.lower():
                search_results.append(
                    {
                        "resume_id": resume.id,
                        "content": raw_text,
                        "relevance_score": 1.0,  # Simple match
                        "metadata": {
                            "resume_id": resume.id,
                            "filename": resume.original_filename,
                            "created_at": (
                                resume.created_at.isoformat()
                                if resume.created_at
                                else None
                            ),
                        },
                    }
                )

        return jsonify(
            {
                "query": query,
                "results": search_results,
                "total_found": len(search_results),
            }
        )

    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        return jsonify({"error": f"Search failed: {str(e)}"}), 500
