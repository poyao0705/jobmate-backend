from __future__ import annotations

from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class ReportRenderer:
    def render(self, result: Dict[str, Any]) -> str:
        lines: List[str] = []
        lines.append(f"# Career Gap Analysis")
        lines.append("")
        # Convert score from 0-10 scale to 0-1 scale (percentage)
        overall_match = result.get("overall_match", 0)
        score_percentage = overall_match / 10.0
        lines.append(f"Overall Match: {score_percentage:.2f}")
        lines.append("")

        def _format_level_info(level_info: Dict[str, Any]) -> str:
            """Format level information for display."""
            if not level_info:
                return ""

            label = level_info.get("label", "unknown")
            score = level_info.get("score", 0)
            years = level_info.get("years")
            evidence = level_info.get("evidence", [])

            parts = [f"{label} ({score:.1f}/4.0)"]
            if years is not None:
                parts.append(f"{years}+ years")
            if evidence:
                parts.append(
                    f"Evidence: {', '.join(evidence[:2])}"
                )  # Limit to 2 evidence items

            return " - " + " | ".join(parts)

        def _section(
            title: str, items: List[Dict[str, Any]], show_levels: bool = False
        ):
            lines.append(f"## {title}")
            if not items:
                lines.append("- None")
                lines.append("")
                return

            for it in items:
                m = it.get("match", {})
                name = m.get("name") or m.get("skill_id") or "?"

                # Just show the skill name without confidence scores
                skill_line = f"- {name}"

                # Add level information if available
                if show_levels:
                    candidate_level = it.get("candidate_level")
                    required_level = it.get("required_level")
                    level_delta = it.get("level_delta", 0)

                    if candidate_level:
                        skill_line += f"\n  Candidate Level: {candidate_level.get('label', 'unknown')} ({candidate_level.get('score', 0):.1f}/4.0)"
                        if candidate_level.get("years"):
                            skill_line += f" - {candidate_level['years']}+ years"

                    if required_level:
                        skill_line += f"\n  Required Level: {required_level.get('label', 'unknown')} ({required_level.get('score', 0):.1f}/4.0)"
                        if required_level.get("years"):
                            skill_line += f" - {required_level['years']}+ years"

                    if level_delta > 0.25:  # Only show if significantly underqualified
                        skill_line += (
                            f"\n  ⚠️  Level Gap: {level_delta:.1f} points below required"
                        )

                # Add skill type indicator
                skill_type = m.get("skill_type", "skill")
                if skill_type != "skill":
                    skill_line += f" [{skill_type}]"

                # Add hot tech / in-demand indicators
                if m.get("hot_tech"):
                    skill_line += " 🔥"
                if m.get("in_demand"):
                    skill_line += " 📈"

                # Add required/optional indicator for job skills
                if it.get("is_required") is False:
                    skill_line += " (optional)"

                lines.append(skill_line)
            lines.append("")

        # Get missing and matched skills
        missing_skills = result.get("missing_skills", [])
        matched_skills = result.get("matched_skills", [])

        # Separate required vs nice-to-have skills
        required_missing = [
            s for s in missing_skills if s.get("is_required") is not False
        ]
        nice_to_have_missing = [
            s for s in missing_skills if s.get("is_required") is False
        ]

        required_matched = [
            s for s in matched_skills if s.get("is_required") is not False
        ]
        nice_to_have_matched = [
            s for s in matched_skills if s.get("is_required") is False
        ]

        # Show required missing skills first (most critical)
        if required_missing:
            _section("Missing Skills (Required)", required_missing)

        # Filter and show hot tech missing (from required only)
        hot_missing = [s for s in required_missing if s.get("is_hot_tech")]
        if hot_missing:
            _section("Hot Tech Missing (Required)", hot_missing)

        # Filter and show in-demand missing (from required only)
        indemand_missing = [s for s in required_missing if s.get("is_in_demand")]
        if indemand_missing:
            _section("In-demand Missing (Required)", indemand_missing)

        # Filter required matched skills by status
        required_underqualified = [
            s for s in required_matched if s.get("status") == "underqualified"
        ]
        required_meets_or_exceeds = [
            s for s in required_matched if s.get("status") == "meets_or_exceeds"
        ]

        # Show required underqualified skills (present but below required level)
        if required_underqualified:
            _section(
                "Underqualified Skills (Required - Present but Below Required Level)",
                required_underqualified,
                show_levels=True,
            )

        # Show required skills that meet or exceed requirements
        if required_meets_or_exceeds:
            _section(
                "Skills Meeting Requirements (Required)",
                required_meets_or_exceeds,
                show_levels=True,
            )

        # Show all required matched skills for completeness (only if status fields not set)
        if (
            required_matched
            and not required_underqualified
            and not required_meets_or_exceeds
        ):
            _section("Matched Skills (Required)", required_matched, show_levels=True)

        # Show nice-to-have missing skills
        if nice_to_have_missing:
            _section("Nice to Have - Missing Skills", nice_to_have_missing)

        # Show nice-to-have matched skills
        if nice_to_have_matched:
            nice_to_have_underqualified = [
                s for s in nice_to_have_matched if s.get("status") == "underqualified"
            ]
            nice_to_have_meets = [
                s for s in nice_to_have_matched if s.get("status") == "meets_or_exceeds"
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
            # Fallback if no status
            if not nice_to_have_underqualified and not nice_to_have_meets:
                _section(
                    "Nice to Have - Matched Skills",
                    nice_to_have_matched,
                    show_levels=True,
                )

        # Show all resume skills
        resume_skills = result.get("resume_skills", [])
        if resume_skills:
            # Deduplicate skills by skill_id to avoid showing the same skill multiple times
            seen_skill_ids = set()
            unique_resume_skills = []
            for skill in resume_skills:
                skill_id = (skill.get("match") or {}).get("skill_id")
                if skill_id and skill_id not in seen_skill_ids:
                    seen_skill_ids.add(skill_id)
                    unique_resume_skills.append(skill)
                elif not skill_id:  # Include skills without IDs
                    unique_resume_skills.append(skill)

            _section(
                "Resume Skills (All Detected Skills)",
                unique_resume_skills,
                show_levels=True,
            )

        return "\n".join(lines)
