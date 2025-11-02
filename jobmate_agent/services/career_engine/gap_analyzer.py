from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .config import config
from .schemas import (
    AnalysisContext,
    GapAnalysisResult,
    MatchedSkill,
    MissingSkill,
    ResumeSkill,
    compute_metrics,
    matched_skill_from_legacy,
    missing_skill_from_legacy,
    resume_skill_from_legacy,
)

logger = logging.getLogger(__name__)


@dataclass
class GapAnalyzerOutput:
    """Structured comparison payload produced by :class:`GapAnalyzer`."""

    score: float
    matched_skills: List[MatchedSkill]
    missing_skills: List[MissingSkill]
    resume_skills: List[ResumeSkill]
    raw_matched: List[Dict[str, Any]]
    raw_missing: List[Dict[str, Any]]
    raw_resume: List[Dict[str, Any]]
    diagnostics: Dict[str, Any]

    def as_analysis(
        self,
        *,
        context: Optional[Dict[str, Any]] = None,
        analysis_id: Optional[int] = None,
        extras: Optional[Dict[str, Any]] = None,
    ) -> GapAnalysisResult:
        """Convert the comparison into a versioned `GapAnalysisResult`."""

        ctx = AnalysisContext(**(context or {}))
        metrics = compute_metrics(
            overall_score=self.score,
            matched=self.matched_skills,
            missing=self.missing_skills,
            resume=self.resume_skills,
        )
        return GapAnalysisResult(
            analysis_id=analysis_id,
            context=ctx,
            metrics=metrics,
            matched_skills=self.matched_skills,
            missing_skills=self.missing_skills,
            resume_skills=self.resume_skills,
            diagnostics=self.diagnostics,
            extras=extras or {},
        )

    def legacy_payload(self) -> Dict[str, Any]:
        """Return the legacy dict structure for backwards compatibility."""

        return {
            "overall_match": self.score,
            "matched_skills": self.raw_matched,
            "missing_skills": self.raw_missing,
            "resume_skills": self.raw_resume,
        }


class GapAnalyzer:
    def __init__(self, llm: Any):
        self.llm = llm

    def compare(
        self, resume_map: List[Dict[str, Any]], job_map: List[Dict[str, Any]]
    ) -> GapAnalyzerOutput:
        logger.info(
            f"Comparing resume ({len(resume_map)} items) vs job ({len(job_map)} items)"
        )

        # Filter to skills-only for coverage calculation (exclude tasks)
        resume_skills = [m for m in resume_map if self._is_skill(m)]
        job_skills = [m for m in job_map if self._is_skill(m)]

        logger.info(
            f"Skills-only: resume ({len(resume_skills)} skills) vs job ({len(job_skills)} skills)"
        )

        # Build fast lookup of resume skills by id
        r_by_id: Dict[str, Dict[str, Any]] = {}
        for m in resume_skills:
            mid = (m.get("match") or {}).get("skill_id")
            if mid:
                r_by_id[mid] = m

        matched, missing = [], []

        # Partition JD skills by presence in resume
        for jm in job_skills:
            sid = (jm.get("match") or {}).get("skill_id")
            if not sid:
                continue
            if sid in r_by_id:
                # augment with level deltas
                rm = r_by_id[sid]
                jm_lvl = jm.get("required_level") or {}
                rm_lvl = rm.get("candidate_level") or {}
                delta = self._level_delta(rm_lvl, jm_lvl)
                out = {
                    **jm,
                    "candidate_level": rm_lvl or None,
                    "required_level": jm_lvl or None,
                    "level_delta": delta,  # positive => underqualified by that many points
                    "resume_score": rm.get("score"),
                }
                matched.append(out)
                logger.debug(
                    f"MATCHED: {out.get('match', {}).get('name')} - "
                    f"JD score: {jm.get('score')}, Resume score: {rm.get('score')}"
                )
            else:
                # Add flags for hot tech and in-demand status
                match_obj = jm.get("match") or {}
                jm["is_hot_tech"] = bool(match_obj.get("hot_tech"))
                jm["is_in_demand"] = bool(match_obj.get("in_demand"))
                missing.append(jm)
                logger.debug(
                    f"MISSING: {jm.get('match', {}).get('name')} - JD score: {jm.get('score')}"
                )

        logger.info(
            f"Skills gap analysis: {len(matched)} matched, {len(missing)} missing"
        )

        # Log some missing skills for debugging
        if missing:
            logger.debug("Sample missing skills:")
            for m in missing[:5]:
                match = m.get("match", {})
                logger.debug(f"  - {match.get('name')}: score={m.get('score')}")

        # Calculate score (no rationale needed)
        score = self._score(matched, missing)

        # Add status field to matched skills based on level qualification
        level_grace = config.score_weights.level_grace
        for m in matched:
            level_delta = m.get("level_delta") or 0
            if level_delta > level_grace:
                m["status"] = "underqualified"
            else:
                m["status"] = "meets_or_exceeds"

        resume_skill_rows = [
            skill
            for skill in resume_map
            if (skill.get("match") or {}).get("skill_type") == "skill"
        ]

        canonical_matched = [matched_skill_from_legacy(m) for m in matched]
        canonical_missing = [missing_skill_from_legacy(m) for m in missing]
        canonical_resume = [resume_skill_from_legacy(s) for s in resume_skill_rows]

        diagnostics = {
            "resume_items": len(resume_map),
            "job_items": len(job_map),
            "resume_skills": len(resume_skill_rows),
            "matched_count": len(matched),
            "missing_count": len(missing),
        }

        return GapAnalyzerOutput(
            score=score,
            matched_skills=canonical_matched,
            missing_skills=canonical_missing,
            resume_skills=canonical_resume,
            raw_matched=matched,
            raw_missing=missing,
            raw_resume=resume_skill_rows,
            diagnostics=diagnostics,
        )

    def _level_delta(self, cand: Dict[str, Any], req: Dict[str, Any]) -> float:
        """Positive value means candidate is under required level."""
        c = float(cand.get("score", 2.0))  # assume 'working' if unknown
        r = float(req.get("score", 2.0))  # assume 'working' if unspecified
        return max(0.0, r - c)

    def _score(
        self,
        matched: List[Dict[str, Any]],
        missing: List[Dict[str, Any]],
    ) -> float:
        # Use configuration weights
        weights = config.score_weights

        # Base coverage score 0..10
        total = max(1, len(matched) + len(missing))
        coverage = (len(matched) / total) * 10.0

        # Penalty for missing skills TODO: need to research this method
        # pen_missing = (
        #     weights.miss * len(missing)
        #     + weights.hot * len(hot_missing)
        #     + weights.ind * len(ind_missing)
        # )
        pen_missing = 0.0

        # Penalty for underqualification by level (weighted; hot/in-demand cost more)
        # TODO: need to research this method
        level_pen = 0.0
        # for m in matched:
        #     d = float(m.get("level_delta") or 0.0)
        #     if d <= weights.level_grace:
        #         continue
        #     meta = m.get("match") or {}
        #     w = (
        #         weights.level
        #         * (1.5 if meta.get("hot_tech") else 1.0)
        #         * (1.25 if meta.get("in_demand") else 1.0)
        #     )
        #     level_pen += w * d

        raw = coverage - pen_missing - level_pen
        return round(max(0.0, min(10.0, raw)), 2)

    def _is_skill(self, m: Dict[str, Any]) -> bool:
        """Check if a mapped item is a skill (not a task)."""
        return (m.get("match") or {}).get("skill_type") == "skill"
