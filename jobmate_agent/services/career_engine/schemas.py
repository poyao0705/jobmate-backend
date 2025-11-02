"""Canonical schema definitions for gap-analysis data.

This module defines the typed, versioned payload used to pass gap-analysis
results across the career engine, persistence layer, LangGraph state, and the
frontend API.  It also provides helpers for adapting legacy dict structures to
the canonical schema and for computing common metrics.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, Iterable, List, Literal, Optional

from pydantic import BaseModel, Field


ANALYSIS_SCHEMA_VERSION = "1.0.0"
logger = logging.getLogger(__name__)


class LevelSnapshot(BaseModel):
    """Normalised representation of a skill level requirement or observation."""

    label: Optional[str] = None
    score: Optional[float] = None
    years: Optional[float] = None
    confidence: Optional[float] = None
    evidence: List[str] = Field(default_factory=list)
    signals: List[Any] = Field(default_factory=list)

    class Config:
        extra = "allow"


class SkillDescriptor(BaseModel):
    """Lightweight descriptor for an ontology skill with preserved metadata."""

    skill_id: Optional[str] = None
    name: Optional[str] = None
    skill_type: Optional[str] = None
    framework: Optional[str] = None
    hot_tech: Optional[bool] = None
    in_demand: Optional[bool] = None
    external_id: Optional[str] = None
    soc_code: Optional[str] = None
    occupation: Optional[str] = None
    commodity_title: Optional[str] = None
    text_preview: Optional[str] = None
    raw: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "allow"


class SkillSnapshot(BaseModel):
    """Base fields shared by all skill collections in the analysis payload."""

    descriptor: SkillDescriptor
    source_token: Optional[str] = None
    source_text: Optional[str] = None
    origin: Literal["resume", "job", "task", "derived"] = "derived"
    job_score: Optional[float] = None
    resume_score: Optional[float] = None
    is_required: Optional[bool] = None
    rank: Optional[int] = None
    tags: Dict[str, bool] = Field(default_factory=dict)

    class Config:
        extra = "allow"


class MatchedSkill(SkillSnapshot):
    status: Literal["meets_or_exceeds", "underqualified"] = "meets_or_exceeds"
    candidate_level: Optional[LevelSnapshot] = None
    required_level: Optional[LevelSnapshot] = None
    level_delta: Optional[float] = None


class MissingSkill(SkillSnapshot):
    status: Literal["missing"] = "missing"


class ResumeSkill(SkillSnapshot):
    origin: Literal["resume"] = "resume"
    status: Literal["resume_only"] = "resume_only"
    candidate_level: Optional[LevelSnapshot] = None


class GapMetrics(BaseModel):
    overall_score: float = 0.0
    overall_percent: Optional[float] = None
    matched_skill_count: int = 0
    missing_skill_count: int = 0
    underqualified_skill_count: int = 0
    resume_skill_count: int = 0
    job_skill_count: Optional[int] = None

    class Config:
        extra = "allow"


class AnalysisContext(BaseModel):
    resume_id: Optional[int] = None
    job_id: Optional[int] = None
    processing_run_id: Optional[int] = None
    job_title: Optional[str] = None
    company: Optional[str] = None
    job_location: Optional[str] = None
    job_url: Optional[str] = None
    job_source: Optional[str] = None
    extractor_mode: Optional[str] = None
    extractor_version: Optional[str] = None
    analyzer_version: Optional[str] = None
    mapper_version: Optional[str] = None
    schema_version: str = ANALYSIS_SCHEMA_VERSION
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    extras: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "allow"


class GapAnalysisResult(BaseModel):
    """Canonical, versioned representation of a gap analysis."""

    version: str = ANALYSIS_SCHEMA_VERSION
    analysis_id: Optional[int] = None
    context: AnalysisContext = Field(default_factory=AnalysisContext)
    metrics: GapMetrics = Field(default_factory=GapMetrics)
    matched_skills: List[MatchedSkill] = Field(default_factory=list)
    missing_skills: List[MissingSkill] = Field(default_factory=list)
    resume_skills: List[ResumeSkill] = Field(default_factory=list)
    report_markdown: Optional[str] = None
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    extras: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "allow"


# ---------------------------------------------------------------------------
# Helper functions for adapting legacy payloads
# ---------------------------------------------------------------------------


def _optional_level(payload: Optional[Dict[str, Any]]) -> Optional[LevelSnapshot]:
    if not payload:
        return None
    if isinstance(payload, LevelSnapshot):
        return payload
    return LevelSnapshot(**payload)


def _descriptor_from_match(match: Optional[Dict[str, Any]]) -> SkillDescriptor:
    raw: Dict[str, Any] = match or {}
    return SkillDescriptor(
        skill_id=raw.get("skill_id"),
        name=raw.get("name"),
        skill_type=raw.get("skill_type"),
        framework=raw.get("framework"),
        hot_tech=raw.get("hot_tech"),
        in_demand=raw.get("in_demand"),
        external_id=raw.get("external_id"),
        soc_code=raw.get("soc_code"),
        occupation=raw.get("occupation"),
        commodity_title=raw.get("commodity_title"),
        text_preview=raw.get("text_preview"),
        raw=raw,
    )


def _base_snapshot(
    entry: Dict[str, Any],
    origin: Literal["resume", "job", "task", "derived"],
    default_tags: Optional[Dict[str, bool]] = None,
) -> SkillSnapshot:
    match = entry.get("match") if origin != "task" else entry.get("match")
    descriptor = _descriptor_from_match(match)
    token = entry.get("token") or entry.get("query") or entry.get("name")
    source_text = entry.get("text") if origin == "task" else entry.get("source_text")

    # Prioritize the extracted skill name (token) over O*NET normalized name for display
    if token:
        descriptor.name = token

    tags = default_tags.copy() if default_tags else {}
    if descriptor.hot_tech is True:
        tags.setdefault("hot_tech", True)
    if descriptor.in_demand is True:
        tags.setdefault("in_demand", True)

    snapshot = SkillSnapshot(
        descriptor=descriptor,
        source_token=token,
        source_text=source_text,
        origin=origin,
        job_score=entry.get("score"),
        resume_score=entry.get("resume_score"),
        is_required=entry.get("is_required"),
        rank=entry.get("rank"),
        tags=tags,
    )
    return snapshot


def matched_skill_from_legacy(entry: Dict[str, Any]) -> MatchedSkill:
    snapshot = _base_snapshot(entry, origin="job")
    status = entry.get("status")
    level_delta = entry.get("level_delta")
    if status not in ("meets_or_exceeds", "underqualified"):
        try:
            delta_val = float(level_delta or 0.0)
        except (TypeError, ValueError):
            delta_val = 0.0
        status = "underqualified" if delta_val > 0 else "meets_or_exceeds"
    return MatchedSkill(
        **snapshot.dict(),
        status=status,
        candidate_level=_optional_level(entry.get("candidate_level")),
        required_level=_optional_level(entry.get("required_level")),
        level_delta=level_delta,
    )


def missing_skill_from_legacy(entry: Dict[str, Any]) -> MissingSkill:
    tags = {
        "hot_tech": bool(entry.get("is_hot_tech")),
        "in_demand": bool(entry.get("is_in_demand")),
    }
    snapshot = _base_snapshot(entry, origin="job", default_tags=tags)
    return MissingSkill(**snapshot.dict())


def resume_skill_from_legacy(entry: Dict[str, Any]) -> ResumeSkill:
    snapshot = _base_snapshot(entry, origin="resume")
    return ResumeSkill(
        **snapshot.dict(),
        candidate_level=_optional_level(entry.get("candidate_level")),
    )


def compute_metrics(
    *,
    overall_score: float,
    matched: Iterable[MatchedSkill] | Iterable[Dict[str, Any]],
    missing: Iterable[MissingSkill] | Iterable[Dict[str, Any]],
    resume: Iterable[ResumeSkill] | Iterable[Dict[str, Any]],
) -> GapMetrics:
    matched_list = list(matched)
    missing_list = list(missing)
    resume_list = list(resume)
    underqualified = sum(
        1
        for skill in matched_list
        if (isinstance(skill, MatchedSkill) and skill.status == "underqualified")
        or (isinstance(skill, dict) and skill.get("status") == "underqualified")
    )
    percent = None
    try:
        percent = round(overall_score / 10.0, 4)
    except (TypeError, ZeroDivisionError):
        percent = None
    return GapMetrics(
        overall_score=float(overall_score or 0.0),
        overall_percent=percent,
        matched_skill_count=len(matched_list),
        missing_skill_count=len(missing_list),
        underqualified_skill_count=underqualified,
        resume_skill_count=len(resume_list),
    )


def build_analysis_from_legacy(
    *,
    overall_score: float,
    matched_skills: List[Dict[str, Any]],
    missing_skills: List[Dict[str, Any]],
    resume_skills: List[Dict[str, Any]],
    context_overrides: Optional[Dict[str, Any]] = None,
    analysis_id: Optional[int] = None,
    diagnostics: Optional[Dict[str, Any]] = None,
    extras: Optional[Dict[str, Any]] = None,
) -> GapAnalysisResult:
    """Assemble a versioned analysis from existing dictionary payloads."""

    matched_objs = [matched_skill_from_legacy(item) for item in matched_skills]
    missing_objs = [missing_skill_from_legacy(item) for item in missing_skills]
    resume_objs = [resume_skill_from_legacy(item) for item in resume_skills]

    metrics = compute_metrics(
        overall_score=overall_score,
        matched=matched_objs,
        missing=missing_objs,
        resume=resume_objs,
    )

    context = AnalysisContext(**(context_overrides or {}))

    return GapAnalysisResult(
        analysis_id=analysis_id,
        context=context,
        metrics=metrics,
        matched_skills=matched_objs,
        missing_skills=missing_objs,
        resume_skills=resume_objs,
        diagnostics=diagnostics or {},
        extras=extras or {},
    )


def analysis_to_transport_payload(analysis: GapAnalysisResult) -> Dict[str, Any]:
    """Return a JSON-serialisable dict with canonical field naming."""

    return json.loads(analysis.json(exclude_none=True))


def load_analysis_from_storage(
    *,
    analysis_json: Optional[Dict[str, Any]],
    analysis_version: Optional[str],
    score: Optional[float],
    matched_skills: Optional[List[Dict[str, Any]]],
    missing_skills: Optional[List[Dict[str, Any]]],
    resume_skills: Optional[List[Dict[str, Any]]],
    context: Optional[Dict[str, Any]] = None,
    analysis_id: Optional[int] = None,
    extras: Optional[Dict[str, Any]] = None,
) -> GapAnalysisResult:
    """Hydrate a `GapAnalysisResult` from stored columns.

    Falls back to legacy JSON columns when versioned payload is unavailable.
    """

    if analysis_json:
        try:
            analysis = GapAnalysisResult(**analysis_json)
            if analysis_id is not None:
                analysis.analysis_id = analysis_id
            if extras:
                analysis.extras.update(extras)
            return analysis
        except Exception:
            logger.warning(
                "Failed to parse stored analysis_json; rebuilding from legacy columns",
                exc_info=True,
            )

    analysis = build_analysis_from_legacy(
        overall_score=score or 0.0,
        matched_skills=matched_skills or [],
        missing_skills=missing_skills or [],
        resume_skills=resume_skills or [],
        context_overrides=context or {},
        analysis_id=analysis_id,
        extras=extras,
    )

    if analysis_version:
        analysis.version = analysis_version

    return analysis


__all__ = [
    "ANALYSIS_SCHEMA_VERSION",
    "LevelSnapshot",
    "SkillDescriptor",
    "SkillSnapshot",
    "MatchedSkill",
    "MissingSkill",
    "ResumeSkill",
    "GapMetrics",
    "AnalysisContext",
    "GapAnalysisResult",
    "matched_skill_from_legacy",
    "missing_skill_from_legacy",
    "resume_skill_from_legacy",
    "compute_metrics",
    "build_analysis_from_legacy",
    "analysis_to_transport_payload",
    "load_analysis_from_storage",
]
