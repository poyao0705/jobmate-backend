from __future__ import annotations

import json
import logging
from typing import List

from jobmate_agent.extensions import db
from jobmate_agent.models import (
    PreloadedContext,
    UserProfile,
    Resume,
    JobListing,
    SkillGapReport,
)

logger = logging.getLogger(__name__)


def _truncate(s: str, limit: int = 4000) -> str:
    if not s:
        return ""
    if len(s) <= limit:
        return s
    return s[:limit]


def build_snippets_for_user_job(user_id: str, job_id: int) -> List[dict]:
    """Build a list of context snippets (dicts with doc_type and content) for the given user+job.

    This reads the canonical source tables (user_profiles, resumes, job_listings,
    skill_gap_reports) and returns a small set of textual snippets suitable for
    inserting into `preloaded_contexts` or sending directly to a chat flow.
    """
    snippets: List[dict] = []
    try:
        user = UserProfile.query.filter_by(id=user_id).first() if user_id else None
        job = JobListing.query.get(int(job_id)) if job_id is not None else None

        # Job snippet
        if job:
            company = getattr(job, "company", "")
            title = getattr(job, "title", "")
            desc = getattr(job, "description", "") or ""
            reqs = getattr(job, "requirements", "") or ""
            job_text = f"Job: {title} at {company}\n\n{desc}\n\nRequirements:\n{reqs}"
            snippets.append({"doc_type": "job", "content": _truncate(job_text)})

        # Resume snippet (default resume)
        resume = None
        try:
            resume = Resume.get_default_resume(user_id) if user_id else None
        except Exception:
            resume = None

        if resume:
            # If parsed_json contains a text field, prefer it
            parsed = getattr(resume, "parsed_json", None)
            resume_text = ""
            if parsed and isinstance(parsed, dict):
                # Try common fields
                resume_text = parsed.get("text") or parsed.get("content") or json.dumps(parsed)
            else:
                resume_text = getattr(resume, "file_url", "") or ""
            if resume_text:
                snippets.append({"doc_type": "resume", "content": _truncate(str(resume_text))})

        # User profile snippet
        if user:
            parts = [f"Name: {user.name}" if user.name else None]
            if user.email:
                parts.append(f"Email: {user.email}")
            if user.contact_location:
                parts.append(f"Location: {user.contact_location}")
            profile_text = "\n".join([p for p in parts if p])
            if profile_text:
                snippets.append({"doc_type": "profile", "content": _truncate(profile_text)})

        # Skill gap snippet (if present)
        try:
            gap = (
                SkillGapReport.query.filter_by(user_id=user_id, job_listing_id=job_id)
                .order_by(SkillGapReport.created_at.desc())
                .first()
            )
        except Exception:
            gap = None

        if gap:
            missing = gap.missing_skills_json or []
            matched = gap.matched_skills_json or []
            weak = gap.weak_skills_json or []
            
            # Build detailed missing skills section (most important for chat context)
            gap_parts = [f"Skill Gap Analysis Score: {gap.score}\n"]
            
            if missing:
                gap_parts.append(f"\n🔴 MISSING SKILLS ({len(missing)} total) - YOU NEED TO LEARN THESE:")
                for i, skill in enumerate(missing, 1):  # Include ALL missing skills
                    token = skill.get("token", "Unknown")
                    match_info = skill.get("match", {})
                    soc_code = match_info.get("soc_code", "N/A") if isinstance(match_info, dict) else "N/A"
                    occupation = match_info.get("occupation", "") if isinstance(match_info, dict) else ""
                    skill_type = match_info.get("skill_type", "") if isinstance(match_info, dict) else ""
                    
                    # Format: number. SkillName (type, SOC: code, occupation)
                    details = []
                    if skill_type:
                        details.append(skill_type)
                    if soc_code != "N/A":
                        details.append(f"SOC: {soc_code}")
                    if occupation:
                        details.append(occupation)
                    
                    detail_str = f" ({', '.join(details)})" if details else ""
                    gap_parts.append(f"  {i}. {token}{detail_str}")
            
            if matched:
                matched_tokens = [str(m.get("token", "?")) for m in matched[:20]]
                gap_parts.append(f"\n✓ MATCHED SKILLS ({len(matched)} total): {', '.join(matched_tokens)}")
                if len(matched) > 20:
                    gap_parts.append(f" ... and {len(matched) - 20} more")
            
            if weak:
                weak_tokens = [str(w.get("token", "?")) for w in weak[:15]]
                gap_parts.append(f"\n⚠ WEAK SKILLS ({len(weak)} total): {', '.join(weak_tokens)}")
                if len(weak) > 15:
                    gap_parts.append(f" ... and {len(weak) - 15} more")
            
            gap_text = "\n".join(gap_parts)
            # Use larger limit for gap report since missing skills is most critical
            snippets.append({"doc_type": "gap", "content": _truncate(gap_text, limit=6000)})

    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Error building snippets for user=%s job=%s: %s", user_id, job_id, exc)

    return snippets


def ensure_preloaded_contexts(user_id: str, job_id: int) -> List[PreloadedContext]:
    """Ensure there is at least one PreloadedContext for the given user+job.

    If none exist, this will build snippets from source tables and insert them.
    Returns the list of PreloadedContext rows for the user+job (most recent first).
    """
    try:
        existing = PreloadedContext.query.filter_by(user_id=user_id, job_listing_id=job_id).all()
        if existing:
            return existing

        snippets = build_snippets_for_user_job(user_id, job_id)
        rows: List[PreloadedContext] = []
        for s in snippets:
            try:
                pc = PreloadedContext(user_id=user_id, job_listing_id=job_id, doc_type=s.get("doc_type", "unknown"), content=s.get("content", ""))
                db.session.add(pc)
                rows.append(pc)
            except Exception:
                logger.exception("Failed to add PreloadedContext row for user=%s job=%s", user_id, job_id)
        if rows:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                logger.exception("Failed to commit preloaded contexts for user=%s job=%s", user_id, job_id)

        # Return whatever exists now
        return PreloadedContext.query.filter_by(user_id=user_id, job_listing_id=job_id).order_by(PreloadedContext.created_at.desc()).all()
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("ensure_preloaded_contexts failed for %s/%s: %s", user_id, job_id, exc)
        return []
