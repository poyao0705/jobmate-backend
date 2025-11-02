from __future__ import annotations

import threading
import os
import logging
from typing import Optional, List, Dict

from jobmate_agent.services.career_engine.chroma_client import ChromaClient
from jobmate_agent.models import db, PreloadedContext, JobListing, Resume, SkillGapReport

logger = logging.getLogger(__name__)


def _build_summary_for_resume(resume: Resume) -> str:
    # Prefer text_preview if available in parsed_json, fallback to truncated raw_text
    parsed = resume.parsed_json or {}
    preview = parsed.get("text_preview") or parsed.get("preview")
    if isinstance(preview, str) and preview.strip():
        return preview.strip()[:2000]
    # fallback to debug-friendly short string
    return f"Resume id={resume.id} (no preview available)"


def _build_summary_for_job(job: JobListing) -> str:
    parts: List[str] = []
    parts.append(f"Job: {job.title} at {job.company}")
    if job.required_skills:
        try:
            skills = job.required_skills if isinstance(job.required_skills, list) else []
            parts.append("Required skills: " + ", ".join(skills[:8]))
        except Exception:
            pass
    if job.description:
        parts.append((job.description or "")[:1200])
    return "\n\n".join(parts)[:3000]


def _build_summary_for_gap(report: Optional[SkillGapReport]) -> str:
    if not report:
        return "No gap report available"
    matched = (report.matched_skills_json or [])[:6]
    missing = (report.missing_skills_json or [])[:6]
    parts = [f"Gap report id={report.id} score={report.score}"]
    if matched:
        parts.append("Matched: " + ", ".join([str(s.get("skill_id") or s.get("name") or str(s)) for s in matched]))
    if missing:
        parts.append("Missing: " + ", ".join([str(s.get("skill_id") or s.get("name") or str(s)) for s in missing]))
    return " -- ".join(parts)[:2000]


def _save_preloaded_snippet(user_id: str, job_id: Optional[int], doc_type: str, content: str) -> None:
    # Overwrite existing same-type snippet for (user,job)
    try:
        existing = (
            PreloadedContext.query.filter_by(user_id=user_id, job_listing_id=job_id, doc_type=doc_type).first()
        )
        if existing:
            existing.content = content
        else:
            db.session.add(PreloadedContext(user_id=user_id, job_listing_id=job_id, doc_type=doc_type, content=content))
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Failed to save preloaded snippet to DB")


def _try_upsert_to_chroma(collection_name: str, docs: List[Dict]) -> bool:
    """Try to upsert docs to Chroma. Returns True on success, False otherwise."""
    try:
        client = ChromaClient(collection_name=collection_name)
        # try to access underlying collection object; LangChain wrapper differs, so be defensive
        coll = getattr(client.store, "_collection", None) or getattr(client.store, "collection", None)
        if coll is None:
            logger.info("Chroma collection handle not available; skipping chroma upsert")
            return False
        # Many langchain-chroma wrappers expose a 'add_texts' or 'add_documents' API
        # We'll attempt a few common method names defensively.
        if hasattr(client.store, "add_texts"):
            texts = [d.get("text") or d.get("content") for d in docs]
            metadatas = [d.get("metadata") or {} for d in docs]
            client.store.add_texts(texts=texts, metadatas=metadatas)
            return True
        if hasattr(coll, "add"):
            # try raw collection add
            for d in docs:
                coll.add(d.get("id"), d.get("embeddings"), d.get("content"), d.get("metadata", {}))
            return True
        logger.info("No supported add/upsert method found on Chroma wrapper")
        return False
    except Exception:
        logger.exception("Chroma upsert failed")
        return False


def preload_context_for_user_job(user_id: str, job_id: Optional[int] = None, collection_name: Optional[str] = None) -> None:
    """Build summaries and save them to DB and try to upsert to Chroma.

    This function is safe to run in a background thread.
    """
    try:
        # Fetch DB models
        resume = None
        try:
            resume = Resume.get_default_resume(user_id)
        except Exception:
            pass

        job = None
        if job_id is not None:
            job = JobListing.query.get(job_id)

        gap = None
        if resume and job:
            gap = (
                SkillGapReport.query.filter_by(resume_id=resume.id, job_listing_id=job.id)
                .order_by(SkillGapReport.created_at.desc())
                .first()
            )

        # Build snippets
        if resume:
            s = _build_summary_for_resume(resume)
            _save_preloaded_snippet(user_id, job_id, "resume", s)

        if job:
            s = _build_summary_for_job(job)
            _save_preloaded_snippet(user_id, job_id, "job", s)

        s = _build_summary_for_gap(gap)
        _save_preloaded_snippet(user_id, job_id, "gap", s)

        # Try Chroma upsert: create minimal docs
        docs: List[Dict] = []
        if resume:
            docs.append({"id": f"resume-{resume.id}", "content": _build_summary_for_resume(resume), "metadata": {"user_id": user_id, "job_id": job_id, "doc_type": "resume"}})
        if job:
            docs.append({"id": f"job-{job.id}", "content": _build_summary_for_job(job), "metadata": {"job_id": job.id, "doc_type": "job"}})
        docs.append({"id": f"gap-{job_id or 'none'}", "content": _build_summary_for_gap(gap), "metadata": {"user_id": user_id, "job_id": job_id, "doc_type": "gap"}})

        # Always sanitize collection_name for Chroma compatibility
        if collection_name is None:
            # Sanitize user_id for Chroma: only alphanumeric, underscores, and hyphens allowed
            # Replace pipes and other special chars with underscores
            sanitized_user_id = user_id.replace("|", "_").replace("@", "_at_").replace(".", "_")
            # Ensure it starts with alphanumeric and is 3-63 chars
            sanitized_user_id = sanitized_user_id[:60]  # Leave room for "user_" prefix
            collection_name = f"user_{sanitized_user_id}"
        else:
            # Sanitize provided collection_name as well
            collection_name = collection_name.replace("|", "_").replace("@", "_at_").replace(".", "_")
            # Ensure valid length
            if len(collection_name) < 3:
                collection_name = f"user_{collection_name}"
            collection_name = collection_name[:63]

        _try_upsert_to_chroma(collection_name, docs)

    except Exception:
        logger.exception("Preload failed")


def preload_context_async(user_id: str, job_id: Optional[int] = None, collection_name: Optional[str] = None) -> threading.Thread:
    """Run preload in a background thread while preserving Flask app context.

    The preloader performs DB queries and needs an application context; capture
    the current_app and run the worker inside its app_context.
    """
    try:
        from flask import current_app

        app = current_app._get_current_object()
    except Exception:
        app = None

    def _target():
        if app is not None:
            with app.app_context():
                preload_context_for_user_job(user_id, job_id, collection_name)
        else:
            # Fallback: try running without explicit app context (may fail)
            preload_context_for_user_job(user_id, job_id, collection_name)

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    return t
