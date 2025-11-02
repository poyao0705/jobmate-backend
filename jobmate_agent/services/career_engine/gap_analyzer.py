from __future__ import annotations

import logging
from typing import Any, Dict, List

from .config import config

logger = logging.getLogger(__name__)


class GapAnalyzer:
    def __init__(self, llm: Any):
        self.llm = llm

    def compare(
        self, resume_map: List[Dict[str, Any]], job_map: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
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

        return {
            "overall_match": score,
            "matched_skills": matched,  # Skills only (used for scoring)
            "missing_skills": missing,  # Skills only (used for scoring)
        }

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

