from flask import request, Response, stream_with_context, jsonify, g
import os
import logging
from datetime import datetime
from jobmate_agent.models import JobListing
from jobmate_agent.extensions import db
from jobmate_agent.jwt_auth import require_jwt

logger = logging.getLogger(__name__)

# Import the blueprint (this should happen after blueprint creation in __init__.py)
from jobmate_agent.blueprints.api import api_bp


@api_bp.route("/jobs", methods=["GET"])
@require_jwt(hydrate=True)
def get_job_listings():
    """Get all active job listings with pagination and filtering"""
    try:
        # Query parameters
        page = request.args.get("page", 1, type=int)
        limit = request.args.get("limit", 10, type=int)
        job_type = request.args.get("job_type")  # FULL_TIME, CONTRACT, etc.
        location = request.args.get("location")
        company = request.args.get("company")

        # Build query with filters
        query = JobListing.query.filter_by(is_active=True)

        if job_type:
            query = query.filter(JobListing.job_type == job_type)
        if location:
            query = query.filter(JobListing.location.ilike(f"%{location}%"))
        if company:
            query = query.filter(JobListing.company.ilike(f"%{company}%"))

        # Apply pagination
        jobs = query.paginate(page=page, per_page=limit, error_out=False)

        # Use the to_dict() method from the model
        # Return structure to match frontend expectations
        return jsonify(
            {
                "jobs": [job.to_dict() for job in jobs.items],
                "pagination": {
                    "total": jobs.total,
                    "current_page": jobs.page,
                    "total_pages": jobs.pages,
                    "has_next": jobs.has_next,
                    "has_prev": jobs.has_prev,
                    "per_page": limit,
                },
            }
        )

    except Exception as e:
        # Log the error for debugging
        logger.error(f"Error in get_job_listings: {str(e)}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/jobs/<int:job_id>", methods=["GET"])
@require_jwt(hydrate=True)
def get_job_by_id(job_id):
    """Get specific job listing by ID"""
    try:
        job = JobListing.query.get(job_id)

        if not job:
            return jsonify({"error": "Job not found"}), 404

        if not job.is_active:
            return jsonify({"error": "Job is no longer active"}), 404

        return jsonify(job.to_dict())

    except Exception as e:
        return jsonify({"error": "Failed to retrieve job", "detail": str(e)}), 500


@api_bp.route("/jobs", methods=["POST"])
@require_jwt(hydrate=True)
def create_job_listing():
    """Create a new job listing"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Validate required fields
        required_fields = ["title", "company"]
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Create new job listing object
        job = JobListing(
            title=data.get("title"),
            company=data.get("company"),
            location=data.get("location"),
            job_type=data.get("job_type", "FULL_TIME"),
            description=data.get("description"),
            requirements=data.get("requirements"),
            salary_min=data.get("salary_min"),
            salary_max=data.get("salary_max"),
            salary_currency=data.get("salary_currency", "USD"),
            external_url=data.get("external_url"),
            external_id=data.get("external_id"),
            source=data.get("source", "Manual"),
            company_logo_url=data.get("company_logo_url"),
            company_website=data.get("company_website"),
            required_skills=data.get("required_skills", []),
            preferred_skills=data.get("preferred_skills", []),
            is_active=data.get("is_active", True),
            is_remote=data.get("is_remote", False),
            date_posted=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.session.add(job)  # Stage the job for insertion
        db.session.commit()  # Actually save to database

        # Return the created job with 201 status
        return jsonify(job.to_dict()), 201

    except Exception as e:
        db.session.rollback()  # Rollback if error occurs
        return jsonify({"error": "Failed to create job listing", "detail": str(e)}), 500


@api_bp.route("/jobs/<int:job_id>", methods=["PUT"])
@require_jwt(hydrate=True)
def update_job_listing(job_id):
    """Update an existing job listing"""
    try:
        job = JobListing.query.get(job_id)

        if not job:
            return jsonify({"error": "Job not found"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Update fields if provided
        if "title" in data:
            job.title = data["title"]
        if "company" in data:
            job.company = data["company"]
        if "location" in data:
            job.location = data["location"]
        if "job_type" in data:
            job.job_type = data["job_type"]
        if "description" in data:
            job.description = data["description"]
        if "requirements" in data:
            job.requirements = data["requirements"]
        if "salary_min" in data:
            job.salary_min = data["salary_min"]
        if "salary_max" in data:
            job.salary_max = data["salary_max"]
        if "salary_currency" in data:
            job.salary_currency = data["salary_currency"]
        if "required_skills" in data:
            job.required_skills = data["required_skills"]
        if "preferred_skills" in data:
            job.preferred_skills = data["preferred_skills"]
        if "is_active" in data:
            job.is_active = data["is_active"]
        if "is_remote" in data:
            job.is_remote = data["is_remote"]

        # Always update the timestamp
        job.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify(job.to_dict())

    except Exception as e:
        db.session.rollback()  # Rollback if error occurs
        return jsonify({"error": "Failed to update job listing", "detail": str(e)}), 500


@api_bp.route("/jobs/<int:job_id>", methods=["DELETE"])
@require_jwt(hydrate=True)
def delete_job_listing(job_id):
    """Delete a job listing (soft delete by setting is_active=False)"""
    try:
        job = JobListing.query.get(job_id)

        if not job:
            return jsonify({"error": "Job not found"}), 404

        # Soft delete - just mark as inactive
        job.is_active = False
        job.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({"message": "Job listing deleted successfully"}), 200

    except Exception as e:
        db.session.rollback()  # Rollback if error occurs
        return jsonify({"error": "Failed to delete job listing", "detail": str(e)}), 500


@api_bp.route("/jobs/search", methods=["GET"])
@require_jwt(hydrate=True)
def search_jobs():
    """Search jobs by keywords in title, description, or skills"""
    try:
        query_param = request.args.get("q", "").strip()
        page = request.args.get("page", 1, type=int)
        limit = request.args.get("limit", 10, type=int)

        if not query_param:
            return jsonify({"error": "Search query required"}), 400

        # Search in title, description, and skills
        search_filter = f"%{query_param}%"
        jobs_query = JobListing.query.filter_by(is_active=True).filter(
            (JobListing.title.ilike(search_filter))
            | (JobListing.description.ilike(search_filter))
            | (JobListing.company.ilike(search_filter))
        )

        jobs = jobs_query.paginate(page=page, per_page=limit, error_out=False)

        return jsonify(
            {
                "jobs": [job.to_dict() for job in jobs.items],
                "total": jobs.total,
                "page": jobs.page,
                "pages": jobs.pages,
                "query": query_param,
            }
        )

    except Exception as e:
        return jsonify({"error": "Search failed", "detail": str(e)}), 500
