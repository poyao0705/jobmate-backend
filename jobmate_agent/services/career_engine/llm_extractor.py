from __future__ import annotations

from typing import Dict, Any, List, Optional
import os
import json
import re
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from .config import config


# Pydantic models for structured output
class SkillLevel(BaseModel):
    """Skill proficiency level information."""

    label: str = Field(
        description="Proficiency level: none, basic, working, proficient, or advanced"
    )
    score: float = Field(description="Numeric score from 0.0 to 4.0")
    years: Optional[int] = Field(
        default=None, description="Years of experience if mentioned"
    )
    confidence: float = Field(description="Confidence score from 0.0 to 1.0")
    signals: List[str] = Field(
        default_factory=list, description="Signals that indicate this level"
    )


class SkillEvidence(BaseModel):
    """Evidence for a skill match."""

    start: int = Field(description="Start character offset in the text")
    end: int = Field(description="End character offset in the text")


class ExtractedSkill(BaseModel):
    """A single extracted skill with evidence and level."""

    name: str = Field(description="Skill name")
    nice_to_have: bool = Field(
        default=False, description="Whether this is a nice-to-have skill"
    )
    evidence_spans: List[SkillEvidence] = Field(
        default_factory=list, description="Character spans showing evidence"
    )
    evidence_texts: List[str] = Field(
        default_factory=list, description="Verbatim text snippets (max 200 chars each)"
    )
    level: SkillLevel = Field(description="Proficiency level information")


class SkillSection(BaseModel):
    """A section of the document containing skills."""

    name: str = Field(description="Section name")
    start: int = Field(description="Start character offset")
    end: int = Field(description="End character offset")


class AllInOneExtraction(BaseModel):
    """Complete extraction result with sections and skills."""

    sections: List[SkillSection] = Field(
        default_factory=list, description="Document sections identified"
    )
    skills: List[ExtractedSkill] = Field(
        default_factory=list, description="All extracted skills"
    )


class LLMExtractor:
    def __init__(self, llm: Any):
        # Use configuration for test mode and model settings
        if llm is None and not config.extraction.test_mode:
            # Only create LLM if we have an API key
            if config.extraction.openai_api_key:
                # Use LangChain's built-in retry logic through max_retries parameter
                self.llm = ChatOpenAI(
                    model=config.extraction.extractor_model,
                    max_retries=3,
                    model_kwargs={"response_format": {"type": "json_object"}},
                )
            else:
                self.llm = None  # Fall back to test mode
        else:
            self.llm = llm  # None indicates test-mode keyword extraction
        self.version = "v2-langchain-best-practices"

        # Initialize ChatPromptTemplate for structured prompts
        self.extract_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are an expert recruiter. Extract a strict JSON object with keys: 
role (string or null), skills (object with keys: programming_languages, frameworks, 
libraries, data_tools, cloud, devops, other; each an array of strings), 
responsibilities (array of action-led strings, each <= 16 words). 
Canonicalize names (e.g., React -> React.js). No prose, JSON ONLY.""",
                ),
                ("user", "{text}"),
            ]
        )

        # Separate prompts for JD and resume extraction
        self.jd_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are an ATS JD parser. Return STRICT JSON with fields {{"sections":[],"skills":[]}}.

- Canonicalize names (React -> React.js, Node -> Node.js, GCP -> Google Cloud).

- For each skill, set nice_to_have=true when cues like "preferred|nice to have|plus|bonus" apply; otherwise required.

- level.score reflects REQUIRED proficiency (0..4). Do not invent years; only extract numeric years if present.

- evidence_texts must be verbatim substrings from the JD.

- Identify sections likely containing skills; return {{name,start,end}} offsets.

- For each skill: name, nice_to_have (bool), evidence_spans [{{start,end}}], evidence_texts (<=200 chars each), 
  level {{label in [none,basic,working,proficient,advanced], score 0..4, years int|null, confidence 0..1, signals [str]}}.

- Calibrate: basic 0.5–1.4, working 1.5–2.4, proficient 2.5–3.4, advanced ≥3.5.""",
                ),
                ("user", "{text}"),
            ]
        )

        self.resume_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a resume parser. Return STRICT JSON {{"sections":[],"skills":[]}}.

- Canonicalize names (React -> React.js, Node -> Node.js, GCP -> Google Cloud).

- Infer level.score as CANDIDATE proficiency using signals (scope, metrics, recency, frequency, action verbs).

- Only infer years when clearly implied by dates in the same section.

- evidence_texts must be verbatim substrings from the resume.

- Identify sections likely containing skills; return {{name,start,end}} offsets.

- For each skill: name, nice_to_have (bool), evidence_spans [{{start,end}}], evidence_texts (<=200 chars each), 
  level {{label in [none,basic,working,proficient,advanced], score 0..4, years int|null, confidence 0..1, signals [str]}}.

- Calibrate: basic 0.5–1.4, working 1.5–2.4, proficient 2.5–3.4, advanced ≥3.5.""",
                ),
                ("user", "{text}"),
            ]
        )

    def extract(self, text: str) -> Dict[str, Any]:
        # Test-mode: deterministic keyword-based extraction (no API calls)
        if self.llm is None:
            # Test mode - return sample data based on text content
            skills = {
                "programming_languages": [],
                "frameworks": [],
                "libraries": [],
                "data_tools": [],
                "cloud": [],
                "devops": [],
                "other": [],
            }
            responsibilities = []

            # Simple keyword matching for testing
            text_lower = text.lower()

            # Programming languages
            if "python" in text_lower:
                skills["programming_languages"].append("Python")
            if "javascript" in text_lower or "js" in text_lower:
                skills["programming_languages"].append("JavaScript")
            if "java" in text_lower:
                skills["programming_languages"].append("Java")
            if "typescript" in text_lower or "ts" in text_lower:
                skills["programming_languages"].append("TypeScript")

            # Frameworks
            if "react" in text_lower:
                skills["frameworks"].append("React")
            if "angular" in text_lower:
                skills["frameworks"].append("Angular")
            if "vue" in text_lower:
                skills["frameworks"].append("Vue.js")
            if "node" in text_lower:
                skills["frameworks"].append("Node.js")

            # Cloud platforms
            if "aws" in text_lower or "amazon" in text_lower:
                skills["cloud"].append("AWS")
            if "azure" in text_lower:
                skills["cloud"].append("Azure")
            if "gcp" in text_lower or "google cloud" in text_lower:
                skills["cloud"].append("Google Cloud")

            # DevOps tools
            if "docker" in text_lower:
                skills["devops"].append("Docker")
            if "kubernetes" in text_lower or "k8s" in text_lower:
                skills["devops"].append("Kubernetes")
            if "jenkins" in text_lower:
                skills["devops"].append("Jenkins")

            # Data tools
            if "sql" in text_lower:
                skills["data_tools"].append("SQL")
            if "postgresql" in text_lower or "postgres" in text_lower:
                skills["data_tools"].append("PostgreSQL")
            if "mysql" in text_lower:
                skills["data_tools"].append("MySQL")
            if "mongodb" in text_lower or "mongo" in text_lower:
                skills["data_tools"].append("MongoDB")

            # Enhanced acronym extraction for test mode
            acronyms = re.findall(
                r"\b[A-Z]{2,}(?:/[A-Z]{2,}|(?:\+[A-Z0-9]+)?)?\b", text
            )
            for acro in acronyms:
                acro_lower = acro.lower()
                if acro_lower in ["aws", "ec2", "s3", "lambda"]:
                    if "AWS" not in skills["cloud"]:
                        skills["cloud"].append("AWS")
                elif acro_lower in ["git", "ci", "cd", "cicd"]:
                    if "Git" not in skills["devops"]:
                        skills["devops"].append("Git")
                elif acro_lower in ["sql", "nosql"]:
                    if "SQL" not in skills["data_tools"]:
                        skills["data_tools"].append("SQL")
                elif acro_lower in ["api", "rest", "graphql"]:
                    if "REST" not in skills["other"]:
                        skills["other"].append("REST APIs")

            # Responsibilities
            if "web" in text_lower or "application" in text_lower:
                responsibilities.append("Develop web applications")
            if "api" in text_lower:
                responsibilities.append("Design RESTful APIs")
            if "database" in text_lower or "db" in text_lower:
                responsibilities.append("Database design and management")
            if "cloud" in text_lower:
                responsibilities.append("Cloud infrastructure management")

            return {
                "role": "Software Engineer" if any(skills.values()) else None,
                "skills": skills,
                "responsibilities": responsibilities,
            }
        # Production mode: structured JSON extraction with GPT using ChatPromptTemplate
        try:
            # Use ChatPromptTemplate for better structured prompts
            chain = self.extract_prompt | self.llm
            msg = chain.invoke({"text": text or ""})
            content = getattr(msg, "content", "") or "{}"
            data = json.loads(content)
            # Minimal validation/normalization
            data.setdefault("role", None)
            data.setdefault("skills", {})
            data.setdefault("responsibilities", [])
            for key in [
                "programming_languages",
                "frameworks",
                "libraries",
                "data_tools",
                "cloud",
                "devops",
                "other",
            ]:
                data["skills"].setdefault(key, [])
            return data
        except Exception as e:
            # Log the error for debugging
            import logging

            logging.getLogger(__name__).warning(f"Extraction failed: {e}")
            # Fallback: return empty structure on parsing/call failure
            return {
                "role": None,
                "skills": {
                    "programming_languages": [],
                    "frameworks": [],
                    "libraries": [],
                    "data_tools": [],
                    "cloud": [],
                    "devops": [],
                    "other": [],
                },
                "responsibilities": [],
            }

    # ---- All-in-one extractor ----
    def extract_all_in_one(
        self, text: str, *, is_job_description: bool
    ) -> Dict[str, Any]:
        """
        One-shot, section-aware extraction with levels and evidence spans.
        Returns {"sections": [...], "skills": [...]}.
        """
        # Test mode or missing LLM → synthesize minimal levels without heuristics
        if self.llm is None or config.extraction.test_mode:
            basic = self.extract(text)
            flat: List[Dict[str, Any]] = []
            for _, arr in (basic.get("skills") or {}).items():
                for skill in arr:
                    flat.append(
                        {
                            "name": skill,
                            "nice_to_have": False,
                            "evidence_spans": [],
                            "evidence_texts": [],
                            "level": {
                                "label": "working",
                                "score": 2.0,
                                "years": None,
                                "confidence": 0.5,
                                "signals": [],
                            },
                        }
                    )
            return {"sections": [], "skills": flat}

        # Choose prompt based on document type
        prompt = self.jd_prompt if is_job_description else self.resume_prompt

        try:
            # Use structured output with Pydantic model
            structured_llm = self.llm.with_structured_output(AllInOneExtraction)
            chain = prompt | structured_llm
            data: AllInOneExtraction = chain.invoke({"text": text})

            # Convert Pydantic model to dict for compatibility
            data_dict = data.model_dump()
        except Exception as e:
            # Log the error for debugging
            import logging

            logging.getLogger(__name__).warning(f"All-in-one extraction failed: {e}")
            if config.extraction.strict_json:
                return {"sections": [], "skills": []}
            data_dict = {"sections": [], "skills": []}
        return self._postprocess_all_in_one(data_dict, text)

    def _postprocess_all_in_one(
        self, data: Dict[str, Any], text: str
    ) -> Dict[str, Any]:
        sections = data.get("sections") or []
        skills = data.get("skills") or []

        def clamp_span(s: int, e: int) -> tuple[int, int]:
            n = len(text)
            s2 = max(0, min(n, int(s)))
            e2 = max(0, min(n, int(e)))
            return s2, max(s2, e2)

        normd: List[Dict[str, Any]] = []
        for s in skills:
            name = (s.get("name") or "").strip()
            if not name:
                continue
            # spans and evidence
            spans_in = s.get("evidence_spans") or []
            ev_texts: List[str] = []
            spans_out: List[Dict[str, int]] = []
            for span in spans_in[: max(0, int(config.extraction.max_spans_per_skill))]:
                start, end = clamp_span(span.get("start", 0), span.get("end", 0))
                frag = text[start:end]
                frag = frag[:200]
                if frag.strip():
                    spans_out.append({"start": start, "end": end})
                    ev_texts.append(frag)

            # normalize level
            lvl = s.get("level") or {}
            label = (lvl.get("label") or "working").lower()
            if label not in {"none", "basic", "working", "proficient", "advanced"}:
                label = "working"
            default_scores = {
                "none": 0.0,
                "basic": 1.0,
                "working": 2.0,
                "proficient": 3.0,
                "advanced": 4.0,
            }
            try:
                score = float(lvl.get("score", default_scores[label]))
            except Exception:
                score = default_scores[label]
            score = max(0.0, min(4.0, score))
            years = lvl.get("years")
            years = int(years) if isinstance(years, (int, float)) else None
            try:
                conf = float(lvl.get("confidence", 0.6))
            except Exception:
                conf = 0.6
            conf = max(0.0, min(1.0, conf))

            normd.append(
                {
                    "name": name,
                    "nice_to_have": bool(s.get("nice_to_have", False)),
                    "evidence_spans": spans_out,
                    "evidence_texts": ev_texts,
                    "level": {
                        "label": label,
                        "score": score,
                        "years": years,
                        "confidence": conf,
                        "signals": (
                            list(lvl.get("signals"))
                            if isinstance(lvl.get("signals"), list)
                            else []
                        ),
                    },
                }
            )

        return {"sections": sections, "skills": normd}
