from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Union
import logging

from .schemas import (
    ANALYSIS_SCHEMA_VERSION,
    GapAnalysisResult,
    MatchedSkill,
    MissingSkill,
    ResumeSkill,
    LevelSnapshot,
    build_analysis_from_legacy,
)

logger = logging.getLogger(__name__)


class ReportRenderer:
    def render(self, result: Union[GapAnalysisResult, Dict[str, Any]]) -> str:
        analysis = self._ensure_analysis(result)
        lines: List[str] = []
        lines.append("# Career Gap Analysis")
        lines.append("")

        overall_match = analysis.metrics.overall_score or 0.0
        score_percentage = overall_match / 10.0
        lines.append(f"Overall Match: {score_percentage:.2f}")
        lines.append("")

        def _section(
            title: str,
            items: Sequence[Union[MatchedSkill, MissingSkill, ResumeSkill]],
            *,
            show_levels: bool = False,
        ) -> None:
            lines.append(f"## {title}")
            if not items:
                lines.append("- None")
                lines.append("")
                return

            for item in items:
                lines.extend(self._format_skill_lines(item, show_levels=show_levels))
            lines.append("")

        missing_skills = analysis.missing_skills
        matched_skills = analysis.matched_skills

        required_missing = [s for s in missing_skills if s.is_required is not False]
        nice_to_have_missing = [s for s in missing_skills if s.is_required is False]

        required_matched = [s for s in matched_skills if s.is_required is not False]
        nice_to_have_matched = [s for s in matched_skills if s.is_required is False]

        if required_missing:
            _section("Missing Skills (Required)", required_missing)

        hot_missing = [s for s in required_missing if self._is_hot(s)]
        if hot_missing:
            _section("Hot Tech Missing (Required)", hot_missing)

        indemand_missing = [s for s in required_missing if self._is_in_demand(s)]
        if indemand_missing:
            _section("In-demand Missing (Required)", indemand_missing)

        required_underqualified = [
            s
            for s in required_matched
            if getattr(s, "status", None) == "underqualified"
        ]
        required_meets_or_exceeds = [
            s
            for s in required_matched
            if getattr(s, "status", None) == "meets_or_exceeds"
        ]

        if required_underqualified:
            _section(
                "Underqualified Skills (Required - Present but Below Required Level)",
                required_underqualified,
                show_levels=True,
            )

        if required_meets_or_exceeds:
            _section(
                "Skills Meeting Requirements (Required)",
                required_meets_or_exceeds,
                show_levels=True,
            )

        if (
            required_matched
            and not required_underqualified
            and not required_meets_or_exceeds
        ):
            _section("Matched Skills (Required)", required_matched, show_levels=True)

        if nice_to_have_missing:
            _section("Nice to Have - Missing Skills", nice_to_have_missing)

        if nice_to_have_matched:
            nice_to_have_underqualified = [
                s
                for s in nice_to_have_matched
                if getattr(s, "status", None) == "underqualified"
            ]
            nice_to_have_meets = [
                s
                for s in nice_to_have_matched
                if getattr(s, "status", None) == "meets_or_exceeds"
            ]

            if nice_to_have_underqualified:
                _section(
                    "Nice to Have - Underqualified Skills",
                    nice_to_have_underqualified,
                    show_levels=True,
                )
            if nice_to_have_meets:
                _section(
                    "Nice to Have - Skills Meeting Requirements",
                    nice_to_have_meets,
                    show_levels=True,
                )
            if not nice_to_have_underqualified and not nice_to_have_meets:
                _section(
                    "Nice to Have - Matched Skills",
                    nice_to_have_matched,
                    show_levels=True,
                )

        resume_skills = self._dedupe_resume_skills(analysis.resume_skills)
        if resume_skills:
            _section(
                "Resume Skills (All Detected Skills)",
                resume_skills,
                show_levels=True,
            )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_analysis(
        self, payload: Union[GapAnalysisResult, Dict[str, Any]]
    ) -> GapAnalysisResult:
        if isinstance(payload, GapAnalysisResult):
            return payload

        if isinstance(payload, dict):
            analysis_dict: Dict[str, Any] | None = None

            candidate = payload.get("analysis")
            if isinstance(candidate, dict):
                analysis_dict = candidate
            elif (
                payload.get("version") == ANALYSIS_SCHEMA_VERSION
                or "context" in payload
            ):
                analysis_dict = payload

            if analysis_dict is not None:
                try:
                    return GapAnalysisResult(**analysis_dict)
                except Exception:
                    logger.debug(
                        "[REPORT] Failed to parse canonical analysis payload; falling back to legacy conversion",
                        exc_info=True,
                    )

            matched = payload.get("matched_skills") or []
            missing = payload.get("missing_skills") or []
            resume = payload.get("resume_skills") or []
            context = payload.get("context")
            context_dict = context if isinstance(context, dict) else {}

            return build_analysis_from_legacy(
                overall_score=payload.get("overall_match", payload.get("score", 0.0)),
                matched_skills=matched,
                missing_skills=missing,
                resume_skills=resume,
                context_overrides=context_dict,
            )

        raise TypeError(
            f"Unsupported payload type for report rendering: {type(payload)!r}"
        )

    def _format_skill_lines(
        self,
        skill: Union[MatchedSkill, MissingSkill, ResumeSkill],
        *,
        show_levels: bool = False,
    ) -> List[str]:
        descriptor = skill.descriptor
        label = (
            descriptor.name
            or descriptor.skill_id
            or getattr(skill, "source_token", None)
            or "?"
        )

        line = f"- {label}"

        skill_type = descriptor.skill_type or "skill"
        if skill_type != "skill":
            line += f" [{skill_type}]"

        if skill.is_required is False:
            line += " (optional)"

        if self._is_hot(skill):
            line += " 🔥"
        if self._is_in_demand(skill):
            line += " 📈"

        lines = [line]

        if show_levels:
            candidate_level = self._as_level(getattr(skill, "candidate_level", None))
            required_level = self._as_level(getattr(skill, "required_level", None))
            level_delta = getattr(skill, "level_delta", None)

            if candidate_level:
                lines.append(self._format_level_row("Candidate Level", candidate_level))
            if required_level:
                lines.append(self._format_level_row("Required Level", required_level))
            if level_delta is not None and level_delta > 0.25:
                lines.append(f"  ⚠️  Level Gap: {level_delta:.1f} points below required")

        return lines

    def _format_level_row(self, prefix: str, level: LevelSnapshot) -> str:
        label = level.label or "unknown"
        score = level.score if level.score is not None else 0.0
        parts = [f"  {prefix}: {label} ({float(score):.1f}/4.0)"]
        if level.years is not None:
            parts.append(f" - {level.years}+ years")
        return "".join(parts)

    def _as_level(
        self, level: Union[LevelSnapshot, Dict[str, Any], None]
    ) -> Optional[LevelSnapshot]:
        if not level:
            return None
        if isinstance(level, LevelSnapshot):
            return level
        return LevelSnapshot(**level)

    def _is_hot(self, skill: Union[MatchedSkill, MissingSkill, ResumeSkill]) -> bool:
        return bool(getattr(skill, "tags", {}).get("hot_tech"))

    def _is_in_demand(
        self, skill: Union[MatchedSkill, MissingSkill, ResumeSkill]
    ) -> bool:
        return bool(getattr(skill, "tags", {}).get("in_demand"))

    def _dedupe_resume_skills(self, skills: Iterable[ResumeSkill]) -> List[ResumeSkill]:
        seen: set[str] = set()
        deduped: List[ResumeSkill] = []
        for skill in skills:
            skill_id = skill.descriptor.skill_id
            if skill_id and skill_id in seen:
                continue
            if skill_id:
                seen.add(skill_id)
            deduped.append(skill)
        return deduped
