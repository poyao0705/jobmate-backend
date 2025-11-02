from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List

from jobmate_agent.extensions import db
from jobmate_agent.models import Resume, JobListing, SkillGapReport
from .llm_extractor import LLMExtractor
from .onet_mapper import OnetMapper
from .gap_analyzer import GapAnalyzer
from .report_renderer import ReportRenderer
from .config import config
from jobmate_agent.services.resume_management.helpers import get_resume_text

logger = logging.getLogger(__name__)


class CareerEngine:
    def __init__(self, onet_chroma: Any, llm: Any):
        self.extractor = LLMExtractor(llm)
        self.mapper = OnetMapper(onet_chroma)
        self.analyzer = GapAnalyzer(llm)
        self.renderer = ReportRenderer()
        self._extractor_mode = (config.extraction.mode or "current").lower()

    def analyze_resume_vs_job(
        self,
        resume_id: int,
        job_text: str | None = None,
        job_title: str | None = None,
        company: str | None = None,
        job_id: int | None = None,
    ) -> Dict[str, Any]:
        logger.info(
            f"[GAP] CareerEngine.analyze: start resume_id={resume_id}, job_id={job_id}, title={job_title or ''}, company={company or ''}"
        )
        # Support test/offline mode where a Flask app context or DB may not be available
        import os as _os

        _test_mode = (_os.getenv("SKILL_EXTRACTOR_TEST") or "0") == "1"
        try:
            resume: Resume = Resume.query.get(resume_id)
        except Exception:
            if _test_mode:
                # Minimal stand-in object for tests without DB/app context
                class _FakeResume:
                    id = resume_id
                    user_id = ""
                    parsed_json = {"raw_text": "test"}
                    processing_run_id = 0

                resume = _FakeResume()  # type: ignore[assignment]
            else:
                raise
        if not resume and not _test_mode:
            raise ValueError(f"Resume {resume_id} not found")
        # In test mode without DB, default to empty text
        resume_text = (
            get_resume_text(resume) if hasattr(resume, "id") and resume else ""
        )

        # Load job from database if job_id is provided
        job_listing: JobListing | None = None
        if job_id is not None:
            job_listing = JobListing.query.get(job_id)
            if not job_listing:
                raise ValueError(f"Job listing {job_id} not found")
            # Use job listing data if job_text not provided
            if not job_text:
                job_text = (
                    "\n\n".join(
                        filter(
                            None, [job_listing.description, job_listing.requirements]
                        )
                    )
                    or ""
                )
                desc_len = len(job_listing.description or "")
                req_len = len(job_listing.requirements or "")
                job_preview = job_text.replace("\n", " ")[:200]
                if job_preview and len(job_text) > 200:
                    job_preview += "..."
                logger.info(
                    "[GAP] CareerEngine.analyze: job_id=%s built job_text from DB desc_len=%s req_len=%s preview='%s'",
                    job_id,
                    desc_len,
                    req_len,
                    job_preview,
                )

            # Enrich job_text with structured information (skills, metadata)
            def _normalize_list_field(raw_value):
                if not raw_value:
                    return []
                if isinstance(raw_value, list):
                    return [str(v).strip() for v in raw_value if str(v).strip()]
                if isinstance(raw_value, str):
                    import json

                    try:
                        parsed = json.loads(raw_value)
                        if isinstance(parsed, list):
                            return [str(v).strip() for v in parsed if str(v).strip()]
                    except (json.JSONDecodeError, TypeError, ValueError):
                        pass
                    return [raw_value.strip()]
                return []

            required_skills = _normalize_list_field(job_listing.required_skills)
            preferred_skills = _normalize_list_field(job_listing.preferred_skills)

            enriched_sections: list[str] = []

            metadata_lines: list[str] = []
            if job_listing.title:
                metadata_lines.append(f"Job Title: {job_listing.title}")
            if job_listing.company:
                metadata_lines.append(f"Company: {job_listing.company}")
            if job_listing.location:
                metadata_lines.append(f"Location: {job_listing.location}")
            if job_listing.job_type:
                metadata_lines.append(f"Employment Type: {job_listing.job_type}")
            if job_listing.salary_min or job_listing.salary_max:
                min_val = (
                    f"{job_listing.salary_currency or ''} {job_listing.salary_min}"
                    if job_listing.salary_min is not None
                    else None
                )
                max_val = (
                    f"{job_listing.salary_currency or ''} {job_listing.salary_max}"
                    if job_listing.salary_max is not None
                    else None
                )
                salary_parts = [p for p in [min_val, max_val] if p]
                if salary_parts:
                    metadata_lines.append("Salary Range: " + " - ".join(salary_parts))
            if metadata_lines:
                enriched_sections.append("\n".join(metadata_lines))

            def _format_bullet_section(title: str, items: list[str]) -> str | None:
                if not items:
                    return None
                bullet_lines = "\n".join(f"- {item}" for item in items)
                return f"{title}:\n{bullet_lines}"

            required_section = _format_bullet_section(
                "Required skills", required_skills
            )
            if required_section:
                enriched_sections.append(required_section)

            preferred_section = _format_bullet_section(
                "Preferred skills", preferred_skills
            )
            if preferred_section:
                enriched_sections.append(preferred_section)

            if job_listing.external_url:
                enriched_sections.append(f"Job posting: {job_listing.external_url}")

            combined_sections = []
            if job_text:
                combined_sections.append(job_text.strip())
            combined_sections.extend(enriched_sections)

            job_text = "\n\n".join(section for section in combined_sections if section)

            # Use job listing metadata if not provided
            if not job_title:
                job_title = job_listing.title
            if not company:
                company = job_listing.company

        # Ensure we have job text
        if not job_text:
            logger.error(
                "[GAP] CareerEngine.analyze: missing job_text after job_id resolution"
            )
            raise ValueError("Either job_text or job_id must be provided")

        # Log extractor mode and job text diagnostics
        job_text_preview = (job_text or "")[:300].replace("\n", " ")
        logger.info(
            f"[GAP] CareerEngine.analyze: extractor_mode={self._extractor_mode}, job_title='{job_title or ''}', company='{company or ''}', job_text_len={len(job_text or '')}, preview='{job_text_preview}'"
        )

        # 1) Extract with level information (mode-gated)
        try:
            if self._extractor_mode == "all_in_one":
                res_aio = self.extractor.extract_all_in_one(
                    resume_text, is_job_description=False
                )
                job_aio = self.extractor.extract_all_in_one(
                    job_text, is_job_description=True
                )
                res_struct = self._adapt_all_in_one(res_aio)
                job_struct = self._adapt_all_in_one(job_aio)
            else:
                res_struct = self._ensure_resume_cached_extract_with_levels(resume)
                job_struct = self.extractor.extract_with_levels(
                    job_text, is_job_description=True
                )
        except Exception as e:
            jt_snippet = (job_text or "")[:200].replace("\n", " ")
            logger.exception(
                f"[GAP] CareerEngine.analyze: extraction failed mode={self._extractor_mode}, job_text_len={len(job_text or '')}, snippet='{jt_snippet}'"
            )
            raise

        # Log extracted skills for debugging
        logger.debug(f"JD extracted skills: {job_struct.get('skills')}")
        logger.debug(f"JD responsibilities: {job_struct.get('responsibilities')}")
        logger.debug(f"Resume extracted skills: {res_struct.get('skills')}")
        logger.debug(f"Resume responsibilities: {res_struct.get('responsibilities')}")

        # 2) Map to O*NET with level data
        logger.info("Starting O*NET mapping for resume and job description")
        resume_map = self._map_with_levels(res_struct, resume_text, is_resume=True)
        logger.info(f"Resume mapping complete: {len(resume_map)} skills mapped")

        job_map = self._map_with_levels(job_struct, job_text, is_resume=False)
        logger.info(f"Job mapping complete: {len(job_map)} skills mapped")

        # Log detailed mapping results
        if resume_map:
            logger.debug("Resume mapped skills:")
            for skill in resume_map[:5]:  # Show first 5
                match = skill.get("match", {})
                logger.debug(f"  - {match.get('name')}: score={skill.get('score')}")

        if job_map:
            logger.debug("Job mapped skills:")
            for skill in job_map[:5]:  # Show first 5
                match = skill.get("match", {})
                logger.debug(f"  - {match.get('name')}: score={skill.get('score')}")

        # 2.5) Persist strategy configuration
        self._persist_strategy_config(resume.processing_run_id)

        # 2.6) Log mapping diagnostics (for debugging, not included in result)
        mapping_diagnostics = self.mapper.get_last_mapping_diagnostics()
        logger.info(
            f"Mapping diagnostics: {mapping_diagnostics.get('total_accepted')} accepted, "
            f"{mapping_diagnostics.get('total_dropped')} dropped, "
            f"{mapping_diagnostics.get('total_ambiguous')} ambiguous"
        )

        # 3) Compare & persist
        result = self.analyzer.compare(resume_map, job_map)
        logger.info(
            f"[GAP] CareerEngine.analyze: comparison done overall_match={result.get('overall_match')}"
        )
        # Extract all resume skills for detailed analysis display
        resume_skills = [
            skill
            for skill in resume_map
            if (skill.get("match") or {}).get("skill_type") == "skill"
        ]
        result["resume_skills"] = resume_skills

        # Extract underqualified skills for backward compatibility with DB schema
        underqualified = [
            skill
            for skill in result.get("matched_skills", [])
            if skill.get("status") == "underqualified"
        ]

        logger.info(
            f"[RESUME_SKILLS] CareerEngine.analyze: Extracted {len(resume_skills)} resume skills "
            f"for resume_id={resume_id}, job_id={job_id}"
        )
        if resume_skills:
            sample_skill = resume_skills[0]
            skill_name = (sample_skill.get("match") or {}).get("name", "unknown")
            candidate_level = sample_skill.get("candidate_level", {})
            logger.debug(
                f"[RESUME_SKILLS] CareerEngine.analyze: Sample skill '{skill_name}' "
                f"with level={candidate_level.get('label', 'N/A')} "
                f"score={candidate_level.get('score', 'N/A')}"
            )

        rec_id = None
        try:
            rec = SkillGapReport(
                user_id=resume.user_id,  # store UserProfile.id (string) as report owner
                resume_id=resume_id,
                job_listing_id=job_listing.id if job_listing else None,
                matched_skills_json=result["matched_skills"],
                missing_skills_json=result["missing_skills"],
                weak_skills_json=underqualified,
                resume_skills_json=result["resume_skills"],
                score=result["overall_match"],
                processing_run_id=resume.processing_run_id,
            )
            db.session.add(rec)
            db.session.commit()
            rec_id = rec.id

            # Log what was saved to database
            saved_resume_skills_count = (
                len(rec.resume_skills_json) if rec.resume_skills_json else 0
            )
            logger.info(
                f"[RESUME_SKILLS] CareerEngine.analyze: Saved to database - "
                f"SkillGapReport id={rec_id}, resume_skills_json count={saved_resume_skills_count}, "
                f"resume_skills_json is NULL={rec.resume_skills_json is None}"
            )
            if rec.resume_skills_json and len(rec.resume_skills_json) > 0:
                first_saved = rec.resume_skills_json[0]
                saved_name = (first_saved.get("match") or {}).get("name", "unknown")
                logger.debug(
                    f"[RESUME_SKILLS] CareerEngine.analyze: First saved skill in DB: '{saved_name}'"
                )
            logger.info(
                f"[GAP] CareerEngine.analyze: SkillGapReport persisted id={rec_id}"
            )
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
            logger.exception(
                "[GAP] CareerEngine.analyze: failed to persist SkillGapReport"
            )

        result["analysis_id"] = rec_id
        result["report_md"] = self.renderer.render(result)
        logger.info(
            f"[GAP] CareerEngine.analyze: end resume_id={resume_id}, job_id={job_id}, analysis_id={rec_id}"
        )
        return result

    def _ensure_resume_cached_extract(self, resume: Resume) -> Dict[str, Any]:
        pj = resume.parsed_json or {}
        if (
            pj.get("extracted_json")
            and pj.get("extractor_version") == self.extractor.version
        ):
            return pj["extracted_json"]
        struct = self.extractor.extract(get_resume_text(resume))
        pj["extracted_json"] = struct
        pj["extractor_version"] = self.extractor.version
        resume.parsed_json = pj
        # In test/offline mode there may be no app context; skip commit
        try:
            db.session.commit()
        except Exception:
            pass
        return struct

    def _ensure_resume_cached_extract_with_levels(
        self, resume: Resume
    ) -> Dict[str, Any]:
        """Extract resume with level information, with caching."""
        pj = resume.parsed_json or {}
        cache_key = "extracted_json_with_levels"
        if pj.get(cache_key) and pj.get("extractor_version") == self.extractor.version:
            return pj[cache_key]

        struct = self.extractor.extract_with_levels(
            get_resume_text(resume), is_job_description=False
        )
        pj[cache_key] = struct
        pj["extractor_version"] = self.extractor.version
        resume.parsed_json = pj
        # In test/offline mode there may be no app context; skip commit
        try:
            db.session.commit()
        except Exception:
            pass
        return struct

    def _map_with_levels(
        self, struct: Dict[str, Any], text: str, is_resume: bool
    ) -> List[Dict[str, Any]]:
        """Map skills and responsibilities to O*NET with level information."""

        # Extract nice-to-have skills for job descriptions
        nice_skills = []
        if not is_resume and config.extraction.parse_nice_to_have:
            nice_skills = self._extract_nice_section(text)
            logger.debug(f"Extracted nice-to-have skills: {nice_skills}")

        # Extract skills with level information
        skills_with_levels = []
        for category, skills in struct.get("skills", {}).items():
            for skill_data in skills:
                if isinstance(skill_data, dict):
                    skill_name = skill_data.get("name", "")
                    level_info = skill_data.get("level", {})
                else:
                    # Fallback for old format: wrap with neutral default level
                    skill_name = skill_data
                    level_info = {
                        "label": "working",
                        "score": 2.0,
                        "years": None,
                        "confidence": 0.5,
                        "signals": [],
                    }

                if skill_name:
                    # Check if this skill is in the nice-to-have section or flagged as such
                    flagged_optional = bool(
                        isinstance(skill_data, dict) and skill_data.get("nice_to_have")
                    )
                    is_required = (
                        not is_resume
                        and skill_name.lower() not in nice_skills
                        and not flagged_optional
                    )

                    # Optional clamp for JD nice-to-have without explicit years
                    if (
                        not is_resume
                        and flagged_optional
                        and config.extraction.cap_nice_to_have
                    ):
                        yrs = (level_info or {}).get("years")
                        if yrs is None:
                            # cap to at most 'working'
                            try:
                                sc = float((level_info or {}).get("score", 2.0))
                            except Exception:
                                sc = 2.0
                            sc = min(sc, 2.0)
                            label = (level_info or {}).get("label", "working").lower()
                            if label in ["proficient", "advanced"]:
                                label = "working"
                            level_info = {
                                "label": label,
                                "score": sc,
                                "years": None,
                                "confidence": float(
                                    (level_info or {}).get("confidence", 0.6)
                                ),
                                "signals": (level_info or {}).get("signals") or [],
                            }
                    skills_with_levels.append(
                        {
                            "name": skill_name,
                            "level": level_info,
                            "is_required": is_required,
                        }
                    )

        # Map skills to O*NET with source_text for literal validation
        skill_tokens = [s["name"] for s in skills_with_levels]
        source_type = "resume" if is_resume else "jd"

        # Log the actual thresholds that will be used
        floor = config.match_strategy.get_floor_for_source_type(source_type)
        quantile = config.match_strategy.get_quantile_for_source_type(source_type)
        logger.info(
            f"Mapping {source_type} skills with floor={floor}, quantile={quantile}, lexical_guard={config.match_strategy.lexical_guard}"
        )

        mapped_skills = self.mapper.map_tokens(
            skill_tokens, source_type=source_type, source_text=text
        )

        # Add level information to mapped skills
        for mapped_skill in mapped_skills:
            # Handle both "token" (from real mapper) and "query" (from demo/test mocks)
            skill_name = mapped_skill.get("token") or mapped_skill.get("query", "")
            # Find the corresponding level info
            level_info = None
            for skill_data in skills_with_levels:
                if skill_data["name"] == skill_name:
                    level_info = skill_data["level"]
                    break

            if level_info:
                if is_resume:
                    mapped_skill["candidate_level"] = level_info
                else:
                    mapped_skill["required_level"] = level_info

        # Map responsibilities/tasks
        responsibilities = struct.get("responsibilities", [])
        # Extract text from responsibility dictionaries if they are in the new format
        responsibility_texts = []
        for resp in responsibilities:
            if isinstance(resp, dict):
                responsibility_texts.append(resp.get("text", ""))
            else:
                responsibility_texts.append(resp)

        # Log task mapping thresholds
        task_floor = config.match_strategy.get_floor_for_source_type("task")
        task_quantile = config.match_strategy.get_quantile_for_source_type("task")
        logger.info(
            f"Mapping {len(responsibility_texts)} tasks with floor={task_floor}, quantile={task_quantile}"
        )

        mapped_tasks = self.mapper.map_tasks(responsibility_texts, source_text=text)

        return mapped_skills + mapped_tasks

    def _adapt_all_in_one(self, aio: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt all-in-one output to legacy structured skills dict shape."""
        skills_arr = aio.get("skills") or []
        legacy: Dict[str, List[Dict[str, Any]]] = {"other": []}
        for s in skills_arr:
            name = s.get("name")
            if not name:
                continue
            legacy["other"].append(
                {
                    "name": name,
                    "level": s.get("level") or {},
                    "nice_to_have": bool(s.get("nice_to_have", False)),
                }
            )
        return {"role": None, "skills": legacy, "responsibilities": []}

    def _flatten(self, skills_dict: Dict[str, List[str]]) -> List[str]:
        out: List[str] = []
        for arr in (skills_dict or {}).values():
            out.extend(arr or [])
        return sorted({s for s in out if s and s.strip()})

    def _extract_nice_section(self, text: str) -> List[str]:
        """
        Extract skills mentioned in 'Nice to have' section of job description.
        Returns list of skill names that are optional requirements.
        """
        import re

        # Look for "Nice to have:" section
        nice_pattern = r"(?:nice\s+to\s+have|preferred|bonus|optional)[\s:]*([^.]*?)(?:\n\n|\n[A-Z]|$)"
        match = re.search(nice_pattern, text, re.IGNORECASE | re.DOTALL)

        if not match:
            return []

        nice_text = match.group(1)
        # Extract individual skills/technologies mentioned
        skills = []

        # Common patterns for skills in nice-to-have sections
        skill_patterns = [
            r"\b([A-Z][a-z]+(?:\.[a-z]+)?)\b",  # Capitalized words (React.js, Node.js)
            r"\b([A-Z]{2,}(?:\+[A-Z0-9]+)?)\b",  # Acronyms (AWS, CI/CD)
            r"\b([a-z]+(?:\s+[a-z]+)*)\b",  # Lowercase multi-word (machine learning)
        ]

        for pattern in skill_patterns:
            matches = re.findall(pattern, nice_text)
            skills.extend(matches)

        # Clean up and deduplicate
        cleaned_skills = []
        for skill in skills:
            skill = skill.strip().lower()
            if len(skill) > 1 and skill not in [
                "the",
                "and",
                "or",
                "with",
                "for",
                "in",
                "on",
                "at",
                "to",
                "of",
                "a",
                "an",
            ]:
                cleaned_skills.append(skill)

        return list(set(cleaned_skills))

    def _persist_strategy_config(self, processing_run_id: int) -> None:
        """Persist career engine configuration to ProcessingRun.params_json."""
        try:
            from jobmate_agent.models import ProcessingRun

            # Get current configuration
            config_params = config.to_dict()

            # Get existing ProcessingRun
            processing_run = ProcessingRun.query.get(processing_run_id)
            if not processing_run:
                return

            # Update params_json with configuration
            existing_params = processing_run.params_json or {}
            existing_params.update(config_params)
            processing_run.params_json = existing_params

            db.session.commit()

        except Exception as e:
            # Log error but don't fail the analysis
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to persist strategy config: {e}")
            try:
                db.session.rollback()
            except Exception:
                pass
