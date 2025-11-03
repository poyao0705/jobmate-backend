# Complete Guide: Skill Gap Report Generation Through gap_agent

> **Comprehensive technical documentation on how skill gap reports are generated using the LangGraph-based gap_agent system.**

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [LangGraph Agent Flow](#langgraph-agent-flow)
4. [CareerEngine Pipeline](#careerengine-pipeline)
5. [Data Models and Schemas](#data-models-and-schemas)
6. [Persistence and State Management](#persistence-and-state-management)
7. [Error Handling and Edge Cases](#error-handling-and-edge-cases)
8. [Configuration and Tuning](#configuration-and-tuning)

---

## Executive Summary

The skill gap report generation system is an **AI-powered analysis pipeline** that compares a user's resume against a job listing to identify skill gaps, proficiencies, and overall match scores. The system is orchestrated by a **LangGraph agent** (`gap_agent`) that coordinates multiple specialized components:

### Key Characteristics

- **LangGraph Orchestration**: Uses LangGraph's StateGraph for structured workflow execution
- **LLM-Powered Extraction**: Extracts skills with proficiency levels from resumes and job descriptions
- **O*NET Taxonomy Mapping**: Maps extracted skills to standardized O*NET skill database using vector similarity search
- **Level-Based Comparison**: Compares candidate skill levels against job requirements
- **Automated Background Processing**: Runs asynchronously in background threads
- **Structured Output**: Produces versioned, schema-validated analysis results

### High-Level Flow

```
User saves job → Background thread spawned → gap_agent.run_gap_agent()
  → LangGraph executes 3 nodes:
    1. get_default_resume() → Load user's default resume
    2. load_job() → Validate and load job listing
    3. run_career_engine() → CareerEngine.analyze_resume_vs_job()
       → Extract skills (LLM)
       → Map to O*NET (Vector Search)
       → Analyze gaps (Comparison Logic)
       → Persist to DB (SkillGapReport)
       → Generate markdown report
```

---

## Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    gap_agent.py                            │
│  LangGraph StateGraph Orchestrator                         │
│  - GapState (TypedDict)                                     │
│  - 3 nodes: get_default_resume, load_job, run_career_engine│
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│              CareerEngine Pipeline                            │
├─────────────────────────────────────────────────────────────┤
│  1. LLMExtractor      → Extract skills with levels           │
│  2. OnetMapper        → Map to O*NET taxonomy               │
│  3. GapAnalyzer       → Compare and calculate gaps           │
│  4. ReportRenderer    → Generate markdown report             │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│              Data Persistence Layer                          │
│  - SkillGapReport (full analysis results)                   │
│  - SkillGapStatus (generation status tracking)               │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | File | Responsibility |
|-----------|------|----------------|
| **gap_agent** | `agents/gap_agent.py` | LangGraph orchestration, state management |
| **CareerEngine** | `services/career_engine/career_engine.py` | Main analysis pipeline coordinator |
| **LLMExtractor** | `services/career_engine/llm_extractor.py` | Skill extraction with proficiency levels |
| **OnetMapper** | `services/career_engine/onet_mapper.py` | O*NET skill taxonomy mapping |
| **GapAnalyzer** | `services/career_engine/gap_analyzer.py` | Gap comparison and scoring |
| **ReportRenderer** | `services/career_engine/report_renderer.py` | Markdown report generation |
| **Schemas** | `services/career_engine/schemas.py` | Type-safe data models |

---

## LangGraph Agent Flow

### Entry Point

**File:** `jobmate_agent/agents/gap_agent.py`

```python
def run_gap_agent(user_id: str, job_id: int) -> Dict[str, Any]:
    """Main entry point for gap analysis."""
    builder = StateGraph(GapState)
    builder.add_node("get_default_resume", get_default_resume)
    builder.add_node("load_job", load_job)
    builder.add_node("run_career_engine", run_career_engine)
    
    # Define execution flow
    builder.add_edge(START, "get_default_resume")
    builder.add_edge("get_default_resume", "load_job")
    builder.add_edge("load_job", "run_career_engine")
    builder.add_edge("run_career_engine", END)
    
    graph = builder.compile()
    out = graph.invoke({"user_id": user_id, "job_id": job_id})
    return out.get("result", {})
```

### State Definition

```python
class GapState(TypedDict, total=False):
    user_id: str           # Input: User identifier
    job_id: int            # Input: Job listing ID
    resume_id: Optional[int] # Output: Resolved default resume ID
    result: Dict[str, Any]  # Output: CareerEngine analysis result
    analysis: GapAnalysisResult # Output: Structured analysis object
    error: str              # Error message if processing fails
```

### Node 1: `get_default_resume`

**Purpose:** Resolve the user's default resume ID.

**Implementation:**

```python
def get_default_resume(state: GapState) -> GapState:
    user_id = state.get("user_id")
    if not user_id:
        return {"error": "Missing user_id"}
    
    res = Resume.get_default_resume(user_id)
    if not res:
        return {"error": "No default resume"}
    
    logger.info(f"Resolved resume_id={res.id} for user_id={user_id}")
    return {"resume_id": res.id}
```

**Key Points:**
- Uses `Resume.get_default_resume()` static method
- Sets `resume_id` in state for downstream nodes
- Returns error state if resume not found

### Node 2: `load_job`

**Purpose:** Validate job listing exists and prepare for analysis.

**Implementation:**

```python
def load_job(state: GapState) -> GapState:
    job_id = state.get("job_id")
    if job_id is None:
        return {"error": "Missing job_id"}
    
    job = JobListing.query.get(job_id)
    if not job:
        return {"error": "Job not found"}
    
    # Log job metadata for debugging
    logger.info(
        f"job_id={job_id} title={job.title} company={job.company} "
        f"desc_len={len(job.description or '')}"
    )
    return {}  # No state update needed, validation only
```

**Key Points:**
- Validates job listing exists in database
- Logs job metadata for traceability
- Returns empty dict if successful (no state mutation)

### Node 3: `run_career_engine`

**Purpose:** Invoke CareerEngine to perform the actual analysis.

**Implementation:**

```python
def run_career_engine(state: GapState) -> GapState:
    if state.get("error"):
        return {}  # Skip if prior error
    
    resume_id = state.get("resume_id")
    job_id = state.get("job_id")
    
    if not resume_id or job_id is None:
        return {"error": "Missing resume_id or job_id"}
    
    # Initialize LLM client
    llm_client = None
    try:
        llm_client = ChatOpenAI(
            model=config.extraction.extractor_model,
            max_retries=3,
            temperature=0,
            model_kwargs={"response_format": {"type": "json_object"}},
        )
    except Exception:
        logger.warning("ChatOpenAI init failed; falling back to extractor default")
        llm_client = None
    
    # Get CareerEngine and run analysis
    engine = get_career_engine(use_real_llm=llm_client is not None, llm=llm_client)
    result = engine.analyze_resume_vs_job(resume_id=resume_id, job_id=job_id)
    
    # Extract structured analysis
    analysis_payload = result.get("analysis")
    analysis_obj = None
    if isinstance(analysis_payload, dict):
        try:
            analysis_obj = GapAnalysisResult(**analysis_payload)
        except Exception:
            logger.exception("Failed to hydrate GapAnalysisResult")
    
    # Update state with results
    state_update: GapState = {"result": result}
    if analysis_obj:
        state_update["analysis"] = analysis_obj
    
    return state_update
```

**Key Points:**
- Skips execution if prior nodes failed (error propagation)
- Initializes LLM client with retry logic
- Falls back to test mode if LLM unavailable
- Returns both legacy `result` dict and structured `analysis` object
- Extracts `analysis_id` from result for status tracking

### Execution Flow Diagram

```
START
  │
  ▼
get_default_resume(state)
  │
  ├─► Success → {resume_id: int}
  └─► Error → {error: str} ──┐
                              │
                              ▼ (skip remaining nodes)
load_job(state)
  │
  ├─► Success → {}
  └─► Error → {error: str} ──┐
                              │
                              ▼ (skip remaining nodes)
run_career_engine(state)
  │
  ├─► Success → {result: {...}, analysis: GapAnalysisResult}
  └─► Error → {error: str}
  │
END
```

---

## CareerEngine Pipeline

**File:** `jobmate_agent/services/career_engine/career_engine.py`

The CareerEngine orchestrates a 5-step analysis process that transforms raw resume and job text into structured gap analysis results.

### Main Method: `analyze_resume_vs_job`

```python
def analyze_resume_vs_job(
    self,
    resume_id: int,
    job_text: str | None = None,
    job_title: str | None = None,
    company: str | None = None,
    job_id: int | None = None,
) -> Dict[str, Any]:
```

### Step 1: Data Loading and Enrichment

**Resume Loading:**
```python
resume = Resume.query.get(resume_id)
resume_text = get_resume_text(resume)  # Extracts raw text from parsed_json
```

**Job Text Preparation:**
```python
if job_id:
    job_listing = JobListing.query.get(job_id)
    job_text = "\n\n".join([
        job_listing.description or "",
        job_listing.requirements or ""
    ])
    
    # Enrich with structured metadata
    enriched_sections = []
    if job_listing.title:
        enriched_sections.append(f"Job Title: {job_listing.title}")
    if job_listing.required_skills:
        enriched_sections.append("Required skills:\n- " + "\n- ".join(...))
    if job_listing.preferred_skills:
        enriched_sections.append("Preferred skills:\n- " + "\n- ".join(...))
    
    job_text = "\n\n".join([job_text] + enriched_sections)
```

**Key Points:**
- Combines `description` and `requirements` fields
- Enriches job text with structured skills arrays
- Includes metadata (title, company, location, salary)

### Step 2: Skill Extraction

**Extraction Modes:**

1. **`all_in_one` mode** (newer, recommended):
   ```python
   res_aio = self.extractor.extract_all_in_one(
       resume_text, is_job_description=False
   )
   job_aio = self.extractor.extract_all_in_one(
       job_text, is_job_description=True
   )
   res_struct = self._adapt_all_in_one(res_aio)
   job_struct = self._adapt_all_in_one(job_aio)
   ```

2. **`current` mode** (legacy):
   ```python
   res_struct = self._ensure_resume_cached_extract_with_levels(resume)
   job_struct = self.extractor.extract_with_levels(
       job_text, is_job_description=True
   )
   ```

**LLMExtractor Output Structure:**

```python
{
    "skills": [
        {
            "name": "React.js",
            "level": {
                "label": "proficient",      # none|basic|working|proficient|advanced
                "score": 2.5,               # 0.0-4.0
                "years": 3,                 # Optional years of experience
                "confidence": 0.9,          # 0.0-1.0
                "signals": ["led team", "scaled to 1M users"],
                "evidence_texts": ["Built React dashboard..."]
            },
            "nice_to_have": False,          # Job descriptions only
            "evidence_spans": [{"start": 120, "end": 145}]
        }
    ],
    "responsibilities": [
        "Developed full-stack web applications",
        "Managed CI/CD pipelines"
    ]
}
```

**Key Points:**
- LLM extracts skills with proficiency levels inferred from context
- Evidence spans provide traceability to source text
- Resume extraction is cached in `parsed_json` to avoid redundant LLM calls
- Test mode uses keyword matching if no LLM available

### Step 3: O*NET Mapping

**Purpose:** Map extracted skill tokens to standardized O*NET skill taxonomy using vector similarity search.

**Implementation:**

```python
def _map_with_levels(
    self, struct: Dict[str, Any], text: str, is_resume: bool
) -> List[Dict[str, Any]]:
    # Extract skills with level information
    skills_with_levels = []
    for category, skills in struct.get("skills", {}).items():
        for skill_data in skills:
            skill_name = skill_data.get("name") if isinstance(skill_data, dict) else skill_data
            level_info = skill_data.get("level") if isinstance(skill_data, dict) else {}
            
            skills_with_levels.append({
                "name": skill_name,
                "level": level_info,
                "is_required": not is_resume and skill_name not in nice_skills
            })
    
    # Map to O*NET
    skill_tokens = [s["name"] for s in skills_with_levels]
    mapped_skills = self.mapper.map_tokens(
        skill_tokens,
        source_type="resume" if is_resume else "jd",
        source_text=text
    )
    
    # Attach level information to mapped skills
    for mapped_skill in mapped_skills:
        token = mapped_skill.get("token") or mapped_skill.get("query", "")
        level_info = next(
            (s["level"] for s in skills_with_levels if s["name"] == token),
            None
        )
        if level_info:
            if is_resume:
                mapped_skill["candidate_level"] = level_info
            else:
                mapped_skill["required_level"] = level_info
    
    # Map responsibilities/tasks as well
    mapped_tasks = self.mapper.map_tasks(responsibility_texts, source_text=text)
    
    return mapped_skills + mapped_tasks
```

**OnetMapper Strategy:**

The mapper uses **adaptive filtering** with source-specific thresholds:

1. **Quantile Strategy** (default):
   - Retrieves top-k candidates via vector search
   - Calculates quantile-based cutoff (e.g., 85th percentile)
   - Applies floor threshold (minimum acceptable score)
   - Filters out low-confidence matches

2. **Static Strategy** (legacy):
   - Uses fixed threshold (e.g., 0.55 similarity)
   - Less adaptive to varying job description quality

**Mapping Output:**

```python
{
    "token": "React.js",
    "match": {
        "skill_id": "fe.react",
        "name": "React.js",
        "framework": "Custom",
        "hot_tech": True,
        "in_demand": True,
        "skill_type": "skill",
        ...
    },
    "score": 0.92,                    # Vector similarity score
    "candidate_level": {               # For resume mappings
        "label": "proficient",
        "score": 2.5,
        "years": 3,
        "confidence": 0.9
    },
    "required_level": {               # For job mappings
        "label": "working",
        "score": 2.0,
        "years": None,
        "confidence": 0.8
    }
}
```

**Key Points:**
- Separate thresholds for resume, job description, and task mappings
- Literal-text guard ensures matched skill names appear in source text
- Preserves level information from extraction step
- Maps both skills and responsibilities/tasks

### Step 4: Gap Analysis

**Purpose:** Compare mapped resume skills against job requirements and calculate match score.

**Implementation:**

```python
def compare(
    self, resume_map: List[Dict[str, Any]], job_map: List[Dict[str, Any]]
) -> GapAnalyzerOutput:
    # Filter to skills-only (exclude tasks for coverage calculation)
    resume_skills = [m for m in resume_map if self._is_skill(m)]
    job_skills = [m for m in job_map if self._is_skill(m)]
    
    # Build lookup by skill_id
    r_by_id = {m["match"]["skill_id"]: m for m in resume_skills if m.get("match", {}).get("skill_id")}
    
    matched, missing = [], []
    
    # Partition job skills
    for jm in job_skills:
        sid = jm.get("match", {}).get("skill_id")
        if sid in r_by_id:
            # Skill exists in resume - calculate level delta
            rm = r_by_id[sid]
            delta = self._level_delta(rm.get("candidate_level"), jm.get("required_level"))
            
            matched.append({
                **jm,
                "candidate_level": rm.get("candidate_level"),
                "required_level": jm.get("required_level"),
                "level_delta": delta,  # positive = underqualified
                "resume_score": rm.get("score"),
            })
        else:
            # Skill missing from resume
            missing.append({
                **jm,
                "is_hot_tech": jm.get("match", {}).get("hot_tech"),
                "is_in_demand": jm.get("match", {}).get("in_demand"),
            })
    
    # Calculate overall score
    score = self._score(matched, missing)
    
    # Classify matched skills by qualification status
    level_grace = config.score_weights.level_grace  # default: 0.25
    for m in matched:
        if (m.get("level_delta") or 0) > level_grace:
            m["status"] = "underqualified"
        else:
            m["status"] = "meets_or_exceeds"
    
    # Convert to canonical schema
    canonical_matched = [matched_skill_from_legacy(m) for m in matched]
    canonical_missing = [missing_skill_from_legacy(m) for m in missing]
    canonical_resume = [resume_skill_from_legacy(s) for s in resume_skills]
    
    return GapAnalyzerOutput(
        score=score,
        matched_skills=canonical_matched,
        missing_skills=canonical_missing,
        resume_skills=canonical_resume,
        raw_matched=matched,
        raw_missing=missing,
        raw_resume=resume_skills,
        diagnostics={...}
    )
```

**Level Delta Calculation:**

```python
def _level_delta(self, cand: Dict[str, Any], req: Dict[str, Any]) -> float:
    """Positive value means candidate is under required level."""
    c = float(cand.get("score", 2.0))  # Default to 'working'
    r = float(req.get("score", 2.0))
    return max(0.0, r - c)
```

**Score Calculation:**

```python
def _score(self, matched: List[Dict], missing: List[Dict]) -> float:
    # Base coverage: percentage of job skills found in resume
    total = max(1, len(matched) + len(missing))
    coverage = (len(matched) / total) * 10.0  # Scale to 0-10
    
    # Currently simplified (penalty logic commented out)
    # Future: Apply penalties for missing hot tech, in-demand skills, level gaps
    raw = coverage
    return round(max(0.0, min(10.0, raw)), 2)
```

**Key Points:**
- Categorizes skills into: matched, missing, underqualified
- Level delta indicates qualification gap (positive = underqualified)
- Score is currently based on coverage percentage (penalty logic in development)
- Produces both canonical schema objects and legacy dict format

### Step 5: Persistence and Report Generation

**Database Persistence:**

```python
rec = SkillGapReport(
    user_id=resume.user_id,
    resume_id=resume_id,
    job_listing_id=job_listing.id,
    matched_skills_json=comparison.raw_matched,
    missing_skills_json=comparison.raw_missing,
    weak_skills_json=underqualified,  # Skills with level_delta > 0
    resume_skills_json=comparison.raw_resume,
    score=comparison.score,
    processing_run_id=resume.processing_run_id,
)

db.session.add(rec)
db.session.flush()
rec_id = rec.id

# Generate structured analysis
analysis = comparison.as_analysis(
    context={
        "resume_id": resume_id,
        "job_id": job_id,
        "job_title": job_title,
        "company": company,
        ...
    }
)
analysis.analysis_id = rec_id

# Store canonical payload
rec.analysis_version = analysis.version
rec.analysis_json = analysis_to_transport_payload(analysis)
db.session.commit()
```

**Report Generation:**

```python
report_markdown = self.renderer.render(analysis)
analysis.report_markdown = report_markdown
```

**Report Structure:**

```markdown
# Career Gap Analysis

Overall Match: 0.75

## Missing Skills (Required)
- Kubernetes
- AWS Lambda 🔥

## Underqualified Skills (Required - Present but Below Required Level)
- Python
  Candidate Level: working (2.0/4.0) - 2+ years
  Required Level: proficient (2.5/4.0)
  ⚠️  Level Gap: 0.5 points below required

## Skills Meeting Requirements (Required)
- React.js
  Candidate Level: proficient (3.0/4.0) - 3+ years
  Required Level: working (2.0/4.0)

## Resume Skills (All Detected Skills)
- TypeScript
  Candidate Level: working (2.0/4.0)
...
```

**Key Points:**
- Persists both legacy JSON columns and canonical `analysis_json` column
- ReportRenderer generates structured markdown with sections for matched/missing/underqualified skills
- Includes level comparisons and gap indicators
- Highlights hot tech and in-demand skills

---

## Data Models and Schemas

### GapState (LangGraph State)

**Location:** `jobmate_agent/agents/gap_agent.py`

```python
class GapState(TypedDict, total=False):
    user_id: str                    # Input
    job_id: int                     # Input
    resume_id: Optional[int]        # Set by get_default_resume
    result: Dict[str, Any]          # CareerEngine legacy output
    analysis: GapAnalysisResult    # Structured canonical output
    error: str                      # Error message
```

### GapAnalysisResult (Canonical Schema)

**Location:** `jobmate_agent/services/career_engine/schemas.py`

```python
class GapAnalysisResult(BaseModel):
    version: str = "1.0.0"
    analysis_id: Optional[int]
    context: AnalysisContext
    metrics: GapMetrics
    matched_skills: List[MatchedSkill]
    missing_skills: List[MissingSkill]
    resume_skills: List[ResumeSkill]
    report_markdown: Optional[str]
    diagnostics: Dict[str, Any]
    extras: Dict[str, Any]
```

**Sub-schemas:**

```python
class MatchedSkill(SkillSnapshot):
    status: Literal["meets_or_exceeds", "underqualified"]
    candidate_level: Optional[LevelSnapshot]
    required_level: Optional[LevelSnapshot]
    level_delta: Optional[float]

class MissingSkill(SkillSnapshot):
    status: Literal["missing"] = "missing"

class ResumeSkill(SkillSnapshot):
    origin: Literal["resume"] = "resume"
    status: Literal["resume_only"] = "resume_only"
    candidate_level: Optional[LevelSnapshot]

class LevelSnapshot(BaseModel):
    label: Optional[str]              # none|basic|working|proficient|advanced
    score: Optional[float]           # 0.0-4.0
    years: Optional[float]
    confidence: Optional[float]      # 0.0-1.0
    evidence: List[str]
    signals: List[str]

class SkillDescriptor(BaseModel):
    skill_id: Optional[str]
    name: Optional[str]
    skill_type: Optional[str]
    framework: Optional[str]
    hot_tech: Optional[bool]
    in_demand: Optional[bool]
    ...
```

### Database Models

**SkillGapReport:**

```python
class SkillGapReport(db.Model):
    id: int
    user_id: str                     # UserProfile.id
    resume_id: int
    job_listing_id: int
    matched_skills_json: JSON        # Legacy format
    missing_skills_json: JSON
    weak_skills_json: JSON           # Underqualified skills
    resume_skills_json: JSON
    score: float                     # 0.0-10.0 overall match
    analysis_version: str            # Schema version
    analysis_json: JSON              # Canonical GapAnalysisResult payload
    processing_run_id: int
    created_at: datetime
```

**SkillGapStatus:**

```python
class SkillGapStatus(db.Model):
    id: int
    user_id: str
    job_listing_id: int
    status: str                       # "generating" | "ready"
    created_at: datetime
    updated_at: datetime
```

---

## Persistence and State Management

### Generation Status Tracking

The system uses `SkillGapStatus` table to track generation state:

```python
# When job is saved (API endpoint)
SkillGapStatus.set_status(user_id, job_id, "generating")

# After successful analysis
if result.get("analysis_id"):
    SkillGapStatus.set_status(user_id, job_id, "ready")
else:
    SkillGapStatus.clear_status(user_id, job_id)
```

**Status Values:**
- `"generating"`: Analysis in progress
- `"ready"`: Analysis complete and report available

### Report Persistence

**Primary Storage: SkillGapReport Table**

```python
rec = SkillGapReport(
    user_id=resume.user_id,
    resume_id=resume_id,
    job_listing_id=job_id,
    matched_skills_json=comparison.raw_matched,      # Legacy format
    missing_skills_json=comparison.raw_missing,
    weak_skills_json=underqualified,
    resume_skills_json=comparison.raw_resume,
    score=comparison.score,
    analysis_version=analysis.version,               # Schema version
    analysis_json=analysis_to_transport_payload(analysis),  # Canonical format
    processing_run_id=resume.processing_run_id,
)
db.session.add(rec)
db.session.commit()
```

**Dual Format Storage:**
- **Legacy JSON columns**: `matched_skills_json`, `missing_skills_json`, etc. (for backwards compatibility)
- **Canonical JSON column**: `analysis_json` (versioned, type-safe schema)

### Configuration Persistence

CareerEngine configuration is persisted to `ProcessingRun.params_json`:

```python
def _persist_strategy_config(self, processing_run_id: int):
    processing_run = ProcessingRun.query.get(processing_run_id)
    existing_params = processing_run.params_json or {}
    existing_params.update(config.to_dict())  # Match strategy, score weights, extraction config
    processing_run.params_json = existing_params
    db.session.commit()
```

This enables:
- Audit trail of configuration used for each analysis
- Debugging configuration-related issues
- Reproducing analyses with exact same settings

---

## Error Handling and Edge Cases

### Error Propagation in LangGraph

Errors are propagated through state:

```python
def run_career_engine(state: GapState) -> GapState:
    if state.get("error"):
        return {}  # Skip execution if prior error
    # ... rest of logic
```

Each node checks for prior errors and can set `error` field to halt execution.

### Missing Resume

**Handled in:** `get_default_resume` node

```python
res = Resume.get_default_resume(user_id)
if not res:
    return {"error": "No default resume"}
```

**Result:** Analysis fails early, status cleared, no report generated.

### Missing Job

**Handled in:** `load_job` node

```python
job = JobListing.query.get(job_id)
if not job:
    return {"error": "Job not found"}
```

**Result:** Analysis fails early with error state.

### LLM Extraction Failures

**Fallback Strategy:**

```python
# If ChatOpenAI initialization fails
try:
    llm_client = ChatOpenAI(...)
except Exception:
    logger.warning("ChatOpenAI init failed; falling back to extractor default")
    llm_client = None

# CareerEngine handles None LLM gracefully
engine = get_career_engine(use_real_llm=False, llm=None)
# Falls back to keyword-based test extraction
```

**Test Mode Behavior:**
- Uses simple keyword matching
- Returns deterministic results
- Suitable for development/testing

### O*NET Mapping Failures

**Handled in:** `OnetMapper.map_tokens()`

- Low-confidence matches filtered by adaptive thresholds
- Literal-text guard rejects phantom matches not in source text
- Missing mappings result in skills appearing as unmatched

### Database Transaction Failures

**Rollback Strategy:**

```python
try:
    rec = SkillGapReport(...)
    db.session.add(rec)
    db.session.commit()
except Exception:
    db.session.rollback()
    logger.exception("Failed to persist SkillGapReport")
    # Report not persisted, but analysis result still returned
```

**Result:** Analysis completes but report not saved. Status cleared to allow retry.

### Background Thread Failures

**Handled in:** `_trigger_gap_analysis_background()`

```python
def _run_with_context():
    with app.app_context():
        try:
            result = run_gap_agent(user_id, job_id)
            if result.get("analysis_id"):
                SkillGapStatus.set_status(user_id, job_id, "ready")
            else:
                SkillGapStatus.clear_status(user_id, job_id)
        except Exception as e:
            logger.exception("Failed to run background gap analysis")
            try:
                SkillGapStatus.clear_status(user_id, job_id)
            except Exception:
                logger.exception("Failed to clear gap status")
```

**Result:** Status cleared on any exception, allowing user to retry.

---

## Configuration and Tuning

### Configuration Source

**File:** `jobmate_agent/services/career_engine/config.py`

Configuration is loaded from environment variables with sensible defaults:

```python
@dataclass
class CareerEngineConfig:
    match_strategy: MatchStrategy
    score_weights: ScoreWeights
    extraction: ExtractionConfig
```

### Match Strategy Configuration

**O*NET Mapping Thresholds:**

```python
@dataclass
class MatchStrategy:
    strategy: str = "quantile"  # quantile | static
    topk: int = 10              # Number of candidates to retrieve
    
    # Quantile thresholds (85th percentile by default)
    jd_q: float = 0.85          # Job description quantile
    resume_q: float = 0.85       # Resume quantile
    task_q: float = 0.85         # Task/responsibility quantile
    
    # Floor thresholds (minimum acceptable scores)
    jd_floor: float = 0.40
    resume_floor: float = 0.30
    task_floor: float = 0.40
    
    # Literal-text guard
    lexical_guard: bool = True  # Reject matches not in source text
```

**Environment Variables:**

```bash
ONET_MATCH_STRATEGY=quantile    # or "static"
ONET_JD_Q=0.85                  # Job description quantile
ONET_RESUME_Q=0.85              # Resume quantile
ONET_JD_FLOOR=0.40              # Minimum job description match score
ONET_RESUME_FLOOR=0.30          # Minimum resume match score
ONET_LEXICAL_GUARD=1            # Enable literal-text validation
```

### Extraction Configuration

**LLM Settings:**

```python
@dataclass
class ExtractionConfig:
    extractor_model: str = "gpt-4o-mini"
    mode: str = "current"              # current | all_in_one
    parse_nice_to_have: bool = True
    cap_nice_to_have: bool = True      # Cap nice-to-have levels to "working"
    test_mode: bool = False            # Use keyword extraction instead of LLM
```

**Environment Variables:**

```bash
EXTRACTOR_MODEL=gpt-4o-mini           # LLM model for extraction
EXTRACTOR_MODE=all_in_one             # Extraction mode
PARSE_NICE_TO_HAVE=1                  # Parse "nice to have" sections
CAP_NICE_TO_HAVE=1                    # Cap nice-to-have skill levels
SKILL_EXTRACTOR_TEST=0                # Enable test mode (no LLM calls)
OPENAI_API_KEY=sk-...                 # Required for real LLM extraction
```

### Score Weights Configuration

**Penalty Weights (for future scoring enhancements):**

```python
@dataclass
class ScoreWeights:
    miss: float = 0.20          # Penalty per missing skill
    hot: float = 0.70            # Penalty per missing hot tech
    ind: float = 0.40            # Penalty per missing in-demand skill
    level: float = 0.90          # Penalty per level gap point
    level_grace: float = 0.25     # Grace threshold for level delta
```

**Environment Variables:**

```bash
GE_MISS_W=0.20                    # Missing skill penalty
GE_HOT_W=0.70                     # Missing hot tech penalty
GE_LEVEL_GRACE=0.25               # Level delta grace threshold
```

### Tuning Guidelines

**For More Aggressive Matching (fewer false negatives):**
- Lower `ONET_JD_FLOOR` and `ONET_RESUME_FLOOR`
- Lower quantile thresholds (`ONET_JD_Q`, `ONET_RESUME_Q`)
- Disable `ONET_LEXICAL_GUARD=0` (less strict validation)

**For Stricter Matching (fewer false positives):**
- Raise `ONET_JD_FLOOR` and `ONET_RESUME_FLOOR`
- Raise quantile thresholds
- Keep `ONET_LEXICAL_GUARD=1` enabled

**For Better Level Extraction:**
- Use `EXTRACTOR_MODE=all_in_one` (newer, more accurate)
- Use `gpt-4o` model for more nuanced level inference (slower, more expensive)
- Ensure `OPENAI_API_KEY` is set for real LLM extraction

**For Development/Testing:**
- Set `SKILL_EXTRACTOR_TEST=1` (no API calls, faster)
- Use `EXTRACTOR_MODE=current` (legacy, simpler output)

---

## Summary

The skill gap report generation system through `gap_agent` is a sophisticated AI-powered pipeline that:

1. **Orchestrates** complex workflows using LangGraph's StateGraph
2. **Extracts** skills with proficiency levels from unstructured text using LLMs
3. **Maps** extracted skills to standardized O*NET taxonomy via vector similarity
4. **Analyzes** gaps by comparing candidate levels against job requirements
5. **Persists** structured results with dual-format storage (legacy + canonical)
6. **Generates** human-readable markdown reports with detailed skill comparisons

The system is designed for **robustness** with comprehensive error handling, **flexibility** through extensive configuration options, and **traceability** via structured logging and status tracking.

**Key Takeaways:**

- LangGraph provides clean state management and error propagation
- CareerEngine components are modular and independently testable
- Dual-format storage ensures backwards compatibility while enabling schema evolution
- Configuration-driven tuning allows production optimization without code changes
- Background processing ensures responsive API endpoints

---

**End of Guide**

