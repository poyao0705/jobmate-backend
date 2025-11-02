"""
O*NET Profile Synthesizer

This module provides functionality to synthesize coherent job profile text
from O*NET occupation data, task statements, and technology skills for embedding.

Key Features:
- Combines occupation info + tasks + tech skills into coherent text
- Handles text truncation and formatting for embedding optimization
- Supports different synthesis strategies (concatenation, LLM-based)
- Generates metadata for embedding pipeline

Usage:
    from jobmate_agent.services.data_import.onet_profile_synthesizer import ONetProfileSynthesizer
    from jobmate_agent.services.data_import.onet_excel_loader import ONetOccupationContext

    synthesizer = ONetProfileSynthesizer()
    profile_text = synthesizer.synthesize_job_profile(occupation_context)
"""

import logging
from typing import List, Dict, Any, Optional
from jobmate_agent.services.data_import.onet_excel_loader import (
    ONetOccupationContext,
    ONetTechnologySkill,
)

logger = logging.getLogger(__name__)


class ONetProfileSynthesizer:
    """Synthesizes job profile text from O*NET occupation context data."""

    def __init__(self, max_tasks: int = 5, max_tech_skills: int = 10):
        """
        Initialize the profile synthesizer.

        Args:
            max_tasks: Maximum number of task statements to include
            max_tech_skills: Maximum number of technology skills to include
        """
        self.max_tasks = max_tasks
        self.max_tech_skills = max_tech_skills

    def synthesize_job_profile(self, occupation: ONetOccupationContext) -> str:
        """
        Synthesize a coherent job profile text from occupation context.

        Args:
            occupation: ONetOccupationContext with all related data

        Returns:
            Synthesized job profile text suitable for embedding
        """
        try:
            # Start with occupation title and SOC code
            profile_parts = [f"{occupation.occupation_title} ({occupation.soc_code})"]

            # Add description if available
            if (
                occupation.occupation_description
                and occupation.occupation_description.strip()
            ):
                profile_parts.append(
                    f"Description: {occupation.occupation_description.strip()}"
                )

            # Add key responsibilities (top tasks)
            if occupation.task_statements:
                top_tasks = occupation.task_statements[: self.max_tasks]
                tasks_text = ", ".join(top_tasks)
                profile_parts.append(f"Key responsibilities: {tasks_text}")

            # Add common technologies
            if occupation.technology_skills:
                tech_skills = self._select_tech_skills(occupation.technology_skills)
                tech_names = [tech.name for tech in tech_skills]
                tech_text = ", ".join(tech_names)
                profile_parts.append(f"Common technologies: {tech_text}")

            # Join all parts
            profile_text = ". ".join(profile_parts) + "."

            # Truncate if too long (keep under reasonable limit for embedding)
            if len(profile_text) > 2000:
                profile_text = profile_text[:2000].rsplit(" ", 1)[0] + "..."

            logger.debug(
                f"Synthesized profile for {occupation.soc_code}: {len(profile_text)} chars"
            )
            return profile_text

        except Exception as e:
            logger.error(f"Failed to synthesize profile for {occupation.soc_code}: {e}")
            # Return minimal fallback
            return f"{occupation.occupation_title} ({occupation.soc_code})"

    def _select_tech_skills(
        self, tech_skills: List[ONetTechnologySkill]
    ) -> List[ONetTechnologySkill]:
        """
        Select the most relevant technology skills for inclusion.

        Priority order:
        1. Hot technologies
        2. In-demand skills
        3. Skills with commodity titles
        4. All others

        Args:
            tech_skills: List of technology skills to select from

        Returns:
            Selected technology skills (up to max_tech_skills)
        """
        if not tech_skills:
            return []

        # Sort by priority
        def priority_key(tech: ONetTechnologySkill) -> tuple:
            return (
                not tech.hot_tech,  # Hot tech first (False sorts before True)
                not tech.in_demand,  # In-demand second
                not bool(tech.commodity_title),  # Has commodity title third
                tech.name,  # Alphabetical for tie-breaking
            )

        sorted_skills = sorted(tech_skills, key=priority_key)
        return sorted_skills[: self.max_tech_skills]

    def synthesize_task_statement(
        self, task: str, occupation_title: str, soc_code: str
    ) -> str:
        """
        Synthesize a single task statement for embedding.

        Args:
            task: Task statement text
            occupation_title: Occupation title for context
            soc_code: SOC code for context

        Returns:
            Synthesized task text
        """
        # For individual tasks, we can add context or keep as-is
        # For now, return the task as-is since it's already descriptive
        return task.strip()

    def synthesize_technology_skill(
        self, tech_skill: ONetTechnologySkill, occupation_title: str
    ) -> str:
        """
        Synthesize a single technology skill for embedding.

        Args:
            tech_skill: Technology skill object
            occupation_title: Occupation title for context

        Returns:
            Synthesized technology skill text
        """
        parts = [tech_skill.name]

        # Add commodity title if available
        if tech_skill.commodity_title:
            parts.append(f"({tech_skill.commodity_title})")

        # Add flags
        flags = []
        if tech_skill.hot_tech:
            flags.append("hot technology")
        if tech_skill.in_demand:
            flags.append("in demand")

        if flags:
            parts.append(f"- {', '.join(flags)}")

        return " ".join(parts)

    def get_profile_metadata(self, occupation: ONetOccupationContext) -> Dict[str, Any]:
        """
        Get metadata for the synthesized job profile.

        Args:
            occupation: ONetOccupationContext

        Returns:
            Metadata dictionary for embedding pipeline
        """
        return {
            "soc_code": occupation.soc_code,
            "occupation_title": occupation.occupation_title,
            "task_count": len(occupation.task_statements),
            "tech_skill_count": len(occupation.technology_skills),
            "hot_tech_count": sum(
                1 for tech in occupation.technology_skills if tech.hot_tech
            ),
            "in_demand_count": sum(
                1 for tech in occupation.technology_skills if tech.in_demand
            ),
            "synthesis_strategy": "concatenation",
            "max_tasks": self.max_tasks,
            "max_tech_skills": self.max_tech_skills,
        }

    def get_task_metadata(
        self, task: str, occupation: ONetOccupationContext, task_index: int
    ) -> Dict[str, Any]:
        """
        Get metadata for a task statement.

        Args:
            task: Task statement text
            occupation: Occupation context
            task_index: Index of this task in the occupation's task list

        Returns:
            Metadata dictionary for embedding pipeline
        """
        return {
            "soc_code": occupation.soc_code,
            "occupation_title": occupation.occupation_title,
            "task_index": task_index,
            "total_tasks": len(occupation.task_statements),
            "task_length": len(task),
        }

    def get_tech_skill_metadata(
        self, tech_skill: ONetTechnologySkill, occupation: ONetOccupationContext
    ) -> Dict[str, Any]:
        """
        Get metadata for a technology skill.

        Args:
            tech_skill: Technology skill object
            occupation: Occupation context

        Returns:
            Metadata dictionary for embedding pipeline
        """
        return {
            "soc_code": occupation.soc_code,
            "occupation_title": occupation.occupation_title,
            "commodity_title": tech_skill.commodity_title,
            "hot_tech": tech_skill.hot_tech,
            "in_demand": tech_skill.in_demand,
            "skill_name": tech_skill.name,
        }
