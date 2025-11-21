"""
O*NET Embedding Pipeline

This module orchestrates the complete O*NET data ingestion flow:
1. Load Excel data and normalize by SOC code
2. Insert individual records into SQL (tasks, tech skills, job profiles)
3. Generate embeddings and store in Chroma

Key Features:
- Processes all three skill types: task, skill, job_profile
- Uses existing DocumentProcessor infrastructure
- Maintains consistency between SQL and Chroma stores
- Provides comprehensive error handling and progress reporting

Usage:
    from jobmate_agent.services.data_import.onet_embedding_pipeline import ONetEmbeddingPipeline

    pipeline = ONetEmbeddingPipeline(data_dir="./data")
    stats = pipeline.run_full_pipeline(limit_occupations=50)
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from jobmate_agent.extensions import db
from jobmate_agent.models import Skill
from jobmate_agent.services.document_processor import DocumentProcessor
from jobmate_agent.services.data_import.onet_excel_loader import (
    ONetExcelLoader,
    ONetOccupationContext,
    ONetTechnologySkill,
)
from jobmate_agent.services.data_import.onet_profile_synthesizer import (
    ONetProfileSynthesizer,
)

logger = logging.getLogger(__name__)


@dataclass
class ONetEmbeddingStats:
    """Statistics about the O*NET embedding pipeline execution."""

    occupations_processed: int = 0
    task_skills_created: int = 0
    tech_skills_created: int = 0
    job_profiles_created: int = 0
    task_embeddings_created: int = 0
    tech_skill_embeddings_created: int = 0
    job_profile_embeddings_created: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class ONetEmbeddingPipeline:
    """Orchestrates the complete O*NET embedding pipeline."""

    def __init__(self, data_dir: str, collection_name: str = "skills_ontology"):
        """
        Initialize the O*NET embedding pipeline.

        Args:
            data_dir: Path to directory containing O*NET Excel files
            collection_name: Chroma collection name for embeddings
        """
        self.data_dir = data_dir
        self.collection_name = collection_name
        self.loader = ONetExcelLoader(data_dir)
        self.synthesizer = ONetProfileSynthesizer()
        self.document_processor = DocumentProcessor(collection_name)
        self.stats = ONetEmbeddingStats()

    def run_full_pipeline(
        self,
        limit_occupations: Optional[int] = None,
        skip_embeddings: bool = False,
    ) -> ONetEmbeddingStats:
        """
        Run the complete O*NET embedding pipeline.

        Args:
            limit_occupations: Optional limit on number of occupations to process
            skip_embeddings: When True, skip vector generation and only seed SQL

        Returns:
            ONetEmbeddingStats with execution statistics
        """
        logger.info("Starting O*NET embedding pipeline...")

        # Reset stats for each pipeline run
        self.stats = ONetEmbeddingStats()

        try:
            # Step 1: Load and normalize data
            logger.info("Loading O*NET data from Excel files...")
            occupations = self.loader.load_all_occupations()

            if limit_occupations:
                occupations = occupations[:limit_occupations]
                logger.info(f"Limited to {limit_occupations} occupations")

            self.stats.occupations_processed = len(occupations)
            logger.info(f"Processing {len(occupations)} occupations")

            # Step 2: Process each occupation
            for i, occupation in enumerate(occupations, 1):
                try:
                    logger.info(
                        f"Processing occupation {i}/{len(occupations)}: {occupation.soc_code}"
                    )
                    self._process_occupation(
                        occupation, skip_embeddings=skip_embeddings
                    )
                except Exception as e:
                    error_msg = (
                        f"Failed to process occupation {occupation.soc_code}: {e}"
                    )
                    logger.error(error_msg)
                    self.stats.errors.append(error_msg)

            # Step 3: Commit all changes
            logger.info("Committing changes to database...")
            db.session.commit()

            logger.info("O*NET embedding pipeline completed successfully!")
            self._log_final_stats()

        except Exception as e:
            logger.error(f"O*NET embedding pipeline failed: {e}")
            db.session.rollback()
            self.stats.errors.append(f"Pipeline failed: {e}")
            raise

        return self.stats

    def seed_sql_only(
        self, limit_occupations: Optional[int] = None
    ) -> ONetEmbeddingStats:
        """
        Seed O*NET task, technology, and job profile records into SQL without embeddings.

        Args:
            limit_occupations: Optional limit on number of occupations to process

        Returns:
            ONetEmbeddingStats with execution statistics (embedding counts will be zero)
        """
        logger.info("Seeding O*NET data into SQL without generating embeddings...")
        return self.run_full_pipeline(
            limit_occupations=limit_occupations, skip_embeddings=True
        )

    def _process_occupation(
        self, occupation: ONetOccupationContext, skip_embeddings: bool = False
    ) -> None:
        """
        Process a single occupation context.

        Args:
            occupation: ONetOccupationContext to process
        """
        # Process individual task statements
        for task_index, task in enumerate(occupation.task_statements):
            try:
                self._create_task_skill(
                    occupation, task, task_index, skip_embeddings=skip_embeddings
                )
            except Exception as e:
                error_msg = (
                    f"Failed to create task skill for {occupation.soc_code}: {e}"
                )
                logger.warning(error_msg)
                self.stats.warnings.append(error_msg)

        # Process individual technology skills
        for tech_skill in occupation.technology_skills:
            try:
                self._create_tech_skill(
                    occupation, tech_skill, skip_embeddings=skip_embeddings
                )
            except Exception as e:
                error_msg = (
                    f"Failed to create tech skill for {occupation.soc_code}: {e}"
                )
                logger.warning(error_msg)
                self.stats.warnings.append(error_msg)

        # Process synthesized job profile
        try:
            self._create_job_profile(occupation, skip_embeddings=skip_embeddings)
        except Exception as e:
            error_msg = f"Failed to create job profile for {occupation.soc_code}: {e}"
            logger.warning(error_msg)
            self.stats.warnings.append(error_msg)

    def _create_task_skill(
        self,
        occupation: ONetOccupationContext,
        task: str,
        task_index: int,
        skip_embeddings: bool = False,
    ) -> None:
        """Create a task skill record and optionally its embedding."""
        skill_id = f"onet.task.{occupation.soc_code}.{task_index}"
        vector_doc_id = f"skill:{skill_id}"

        if not self._upsert_task_skill_record(
            occupation, task, task_index, skill_id, vector_doc_id
        ):
            return

        if skip_embeddings:
            logger.debug(f"Seeded task skill {skill_id} without embeddings")
            return

        self._embed_task_skill(occupation, task, task_index, skill_id, vector_doc_id)

    def _create_tech_skill(
        self,
        occupation: ONetOccupationContext,
        tech_skill: ONetTechnologySkill,
        skip_embeddings: bool = False,
    ) -> None:
        """Create a technology skill record and optionally its embedding."""
        skill_id = f"onet.tech.{self._normalize_skill_name(tech_skill.name)}"
        vector_doc_id = f"skill:{skill_id}"

        if not self._upsert_tech_skill_record(
            occupation, tech_skill, skill_id, vector_doc_id
        ):
            return

        if skip_embeddings:
            logger.debug(f"Seeded tech skill {skill_id} without embeddings")
            return

        self._embed_tech_skill(occupation, tech_skill, skill_id, vector_doc_id)

    def _create_job_profile(
        self, occupation: ONetOccupationContext, skip_embeddings: bool = False
    ) -> None:
        """Create a job profile record and optionally its embedding."""
        skill_id = f"onet.profile.{occupation.soc_code}"
        vector_doc_id = f"skill:{skill_id}"

        if not self._upsert_job_profile_record(occupation, skill_id, vector_doc_id):
            return

        if skip_embeddings:
            logger.debug(f"Seeded job profile {skill_id} without embeddings")
            return

        self._embed_job_profile(occupation, skill_id, vector_doc_id)

    def _upsert_task_skill_record(
        self,
        occupation: ONetOccupationContext,
        task: str,
        task_index: int,
        skill_id: str,
        vector_doc_id: str,
    ) -> bool:
        """Insert the task skill row if missing; return True when inserted."""
        existing_skill = Skill.query.filter_by(skill_id=skill_id).first()
        if existing_skill:
            logger.debug(f"Task skill {skill_id} already exists, skipping")
            return False

        skill = Skill(
            skill_id=skill_id,
            name=task[:200] if len(task) > 200 else task,
            taxonomy_path=f"ONET/TASKS/{occupation.soc_code}",
            vector_doc_id=vector_doc_id,
            framework="ONET",
            skill_type="task",
            onet_soc_code=occupation.soc_code,
            occupation_title=occupation.occupation_title,
            meta_json=self.synthesizer.get_task_metadata(task, occupation, task_index),
        )

        db.session.add(skill)
        self.stats.task_skills_created += 1
        return True

    def _embed_task_skill(
        self,
        occupation: ONetOccupationContext,
        task: str,
        task_index: int,
        skill_id: str,
        vector_doc_id: str,
    ) -> None:
        """Generate and persist embeddings for a task skill."""
        synthesized_task = self.synthesizer.synthesize_task_statement(
            task, occupation.occupation_title, occupation.soc_code
        )
        metadata = {
            "skill_id": skill_id,
            "skill_type": "task",
            "soc_code": occupation.soc_code,
            "occupation": occupation.occupation_title,
            "framework": "ONET",
            "task_index": task_index,
            "total_tasks": len(occupation.task_statements),
        }

        chunks_created = self.document_processor.process_document(
            doc_id=vector_doc_id,
            text=synthesized_task,
            metadata=metadata,
            delete_existing=True,
        )

        self.stats.task_embeddings_created += chunks_created
        logger.debug(f"Created task skill {skill_id} with {chunks_created} chunks")

    def _upsert_tech_skill_record(
        self,
        occupation: ONetOccupationContext,
        tech_skill: ONetTechnologySkill,
        skill_id: str,
        vector_doc_id: str,
    ) -> bool:
        """Insert the technology skill row if missing; return True when inserted."""
        existing_skill = Skill.query.filter_by(skill_id=skill_id).first()
        if existing_skill:
            logger.debug(f"Tech skill {skill_id} already exists, skipping")
            return False

        skill = Skill(
            skill_id=skill_id,
            name=tech_skill.name,
            taxonomy_path=f"ONET/TECHNOLOGY/{tech_skill.commodity_title or 'GENERAL'}",
            vector_doc_id=vector_doc_id,
            framework="ONET",
            skill_type="skill",
            onet_soc_code=occupation.soc_code,
            occupation_title=occupation.occupation_title,
            commodity_title=tech_skill.commodity_title,
            hot_tech=tech_skill.hot_tech,
            in_demand=tech_skill.in_demand,
            meta_json=self.synthesizer.get_tech_skill_metadata(tech_skill, occupation),
        )

        db.session.add(skill)
        self.stats.tech_skills_created += 1
        return True

    def _embed_tech_skill(
        self,
        occupation: ONetOccupationContext,
        tech_skill: ONetTechnologySkill,
        skill_id: str,
        vector_doc_id: str,
    ) -> None:
        """Generate and persist embeddings for a technology skill."""
        synthesized_tech = self.synthesizer.synthesize_technology_skill(
            tech_skill, occupation.occupation_title
        )
        metadata = {
            "skill_id": skill_id,
            "skill_type": "skill",
            "soc_code": occupation.soc_code,
            "occupation": occupation.occupation_title,
            "commodity_title": tech_skill.commodity_title,
            "hot_tech": tech_skill.hot_tech,
            "in_demand": tech_skill.in_demand,
            "framework": "ONET",
        }

        chunks_created = self.document_processor.process_document(
            doc_id=vector_doc_id,
            text=synthesized_tech,
            metadata=metadata,
            delete_existing=True,
        )

        self.stats.tech_skill_embeddings_created += chunks_created
        logger.debug(f"Created tech skill {skill_id} with {chunks_created} chunks")

    def _upsert_job_profile_record(
        self,
        occupation: ONetOccupationContext,
        skill_id: str,
        vector_doc_id: str,
    ) -> bool:
        """Insert the job profile row if missing; return True when inserted."""
        existing_skill = Skill.query.filter_by(skill_id=skill_id).first()
        if existing_skill:
            logger.debug(f"Job profile {skill_id} already exists, skipping")
            return False

        skill = Skill(
            skill_id=skill_id,
            name=occupation.occupation_title,
            taxonomy_path=f"ONET/PROFILES/{occupation.soc_code}",
            vector_doc_id=vector_doc_id,
            framework="ONET",
            skill_type="job_profile",
            onet_soc_code=occupation.soc_code,
            occupation_title=occupation.occupation_title,
            meta_json=self.synthesizer.get_profile_metadata(occupation),
        )

        db.session.add(skill)
        self.stats.job_profiles_created += 1
        return True

    def _embed_job_profile(
        self,
        occupation: ONetOccupationContext,
        skill_id: str,
        vector_doc_id: str,
    ) -> None:
        """Generate and persist embeddings for a job profile."""
        synthesized_profile = self.synthesizer.synthesize_job_profile(occupation)
        metadata = {
            "skill_id": skill_id,
            "skill_type": "job_profile",
            "soc_code": occupation.soc_code,
            "occupation": occupation.occupation_title,
            "framework": "ONET",
        }

        chunks_created = self.document_processor.process_document(
            doc_id=vector_doc_id,
            text=synthesized_profile,
            metadata=metadata,
            delete_existing=True,
        )

        self.stats.job_profile_embeddings_created += chunks_created
        logger.debug(f"Created job profile {skill_id} with {chunks_created} chunks")

    def _normalize_skill_name(self, name: str) -> str:
        """Normalize skill name for use in skill_id."""
        # Remove special characters and convert to lowercase
        import re

        normalized = re.sub(r"[^a-zA-Z0-9]", "_", name.lower())
        # Remove multiple underscores
        normalized = re.sub(r"_+", "_", normalized)
        # Remove leading/trailing underscores
        normalized = normalized.strip("_")
        return normalized

    def _log_final_stats(self) -> None:
        """Log final pipeline statistics."""
        logger.info("=== O*NET Embedding Pipeline Statistics ===")
        logger.info(f"Occupations processed: {self.stats.occupations_processed}")
        logger.info(f"Task skills created: {self.stats.task_skills_created}")
        logger.info(f"Tech skills created: {self.stats.tech_skills_created}")
        logger.info(f"Job profiles created: {self.stats.job_profiles_created}")
        logger.info(f"Task embeddings created: {self.stats.task_embeddings_created}")
        logger.info(
            f"Tech skill embeddings created: {self.stats.tech_skill_embeddings_created}"
        )
        logger.info(
            f"Job profile embeddings created: {self.stats.job_profile_embeddings_created}"
        )

        if self.stats.warnings:
            logger.warning(f"Warnings: {len(self.stats.warnings)}")
            for warning in self.stats.warnings[:5]:  # Show first 5 warnings
                logger.warning(f"  - {warning}")

        if self.stats.errors:
            logger.error(f"Errors: {len(self.stats.errors)}")
            for error in self.stats.errors[:5]:  # Show first 5 errors
                logger.error(f"  - {error}")

    def get_loader_statistics(self) -> Dict[str, Any]:
        """Get statistics from the Excel loader."""
        return self.loader.get_statistics()

    def validate_data_quality(self) -> Dict[str, Any]:
        """Validate the quality of loaded data."""
        stats = self.get_loader_statistics()

        quality_issues = []

        # Check for occupations with no tasks
        if stats["avg_tasks_per_occupation"] < 1:
            quality_issues.append("Some occupations have no task statements")

        # Check for occupations with no tech skills
        if stats["avg_tech_skills_per_occupation"] < 1:
            quality_issues.append("Some occupations have no technology skills")

        # Check for very low hot tech count
        if stats["hot_technologies"] < stats["total_occupations"] * 0.1:
            quality_issues.append("Low number of hot technologies detected")

        return {
            "quality_score": max(0, 1.0 - len(quality_issues) * 0.2),
            "issues": quality_issues,
            "statistics": stats,
        }
