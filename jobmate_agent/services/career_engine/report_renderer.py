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

        # Show missing skills first (most critical)
        _section("Missing Skills", missing_skills)

        # Filter and show hot tech missing
        hot_missing = [s for s in missing_skills if s.get("is_hot_tech")]
        if hot_missing:
            _section("Hot Tech Missing", hot_missing)

        # Filter and show in-demand missing
        indemand_missing = [s for s in missing_skills if s.get("is_in_demand")]
        if indemand_missing:
            _section("In-demand Missing", indemand_missing)

        # Filter matched skills by status
        underqualified = [
            s for s in matched_skills if s.get("status") == "underqualified"
        ]
        meets_or_exceeds = [
            s for s in matched_skills if s.get("status") == "meets_or_exceeds"
        ]

        # Show underqualified skills (present but below required level)
        if underqualified:
            _section(
                "Underqualified Skills (Present but Below Required Level)",
                underqualified,
                show_levels=True,
            )

        # Show skills that meet or exceed requirements
        if meets_or_exceeds:
            _section("Skills Meeting Requirements", meets_or_exceeds, show_levels=True)

        # Show all matched skills for completeness (only if status fields not set)
        if matched_skills and not underqualified and not meets_or_exceeds:
            _section("Matched Skills", matched_skills, show_levels=True)

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
