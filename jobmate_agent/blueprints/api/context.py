
from flask import Blueprint, jsonify, g
from jobmate_agent.models import User, Resume, JobListing, SkillGapReport
from jobmate_agent.blueprints.api.gap import _get_default_resume_for_user
from jobmate_agent.jwt_auth import require_jwt

context_bp = Blueprint('context', __name__, url_prefix='/api/context')

@context_bp.route('/api/context/by-job/<int:job_id>', methods=['GET'])
@require_jwt(hydrate=True)
def get_context_by_job(job_id):
    user_id = g.user_sub
    if not user_id:
        return jsonify({'error': 'User not authenticated'}), 401

    # Fetch user info
    user = User.query.filter_by(id=user_id).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    # Fetch default resume
    resume = _get_default_resume_for_user(user_id)
    if not resume:
        return jsonify({'error': 'No default resume found for user'}), 404

    # Fetch job info
    job = JobListing.query.filter_by(id=job_id).first()
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    # Fetch skill gap report
    report = SkillGapReport.query.filter_by(resume_id=resume.id, job_listing_id=job_id).order_by(SkillGapReport.created_at.desc()).first()
    gap = None
    if report:
        gap = {
            'id': report.id,
            'score': report.score,
            'matched_skills': report.matched_skills_json,
            'missing_skills': report.missing_skills_json,
            'weak_skills': report.weak_skills_json,
            'created_at': report.created_at.isoformat()
        }

    return jsonify({
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email
        },
        'resume': {
            'id': resume.id,
            'name': getattr(resume, 'name', None),
            'summary': getattr(resume, 'summary', None)
        },
        'job': {
            'id': job.id,
            'title': getattr(job, 'title', None),
            'company': getattr(job, 'company', None)
        },
        'gap_report': gap
    })
