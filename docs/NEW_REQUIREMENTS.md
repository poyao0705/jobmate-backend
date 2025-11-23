# New Requirements

### Refactor Service
- skill service
    - add new skill
    - normalize skill
    - find similar skills
    - backfilling skill description (from the csv file)
    - backfilling skill embedding (from the populated description in the skill table)

- resume service
    - parse resume from PDF, DOCX, TXT
    - extract skills from resume (independent implementation)
    - save to db

- job service
    - get the job description from the job posting
    - extract skills from job description (independent implementation)
    - save to db
    - **embed job description**

- enrichment service
    - get the job description using langchain wiki tool
    
### Agent Roles (Refactored 2025-11-23)
- **Job Agent (The Recruiter):**
    - **Goal:** Find jobs and help the user apply.
    - **Capabilities:**
        - Search for jobs (Internal DB + Web).
        - Analyze job fit (Gap Analysis).
        - Tailor Resume & Generate Cover Letters.
    - **Tools:** `search_jobs`, `get_job_details`, `analyze_fit`, `generate_application`.

- **Career Coach (The Mentor):**
    - **Goal:** Help the user grow and prepare.
    - **Capabilities:**
        - Generate Learning Paths (Skill gaps).
        - Interview Preparation (Mock Interviews).
        - Concept Explanation (Teaching).
    - **Tools:** `generate_learning_path`, `mock_interview`, `explain_concept`.

### Architecture Decisions
- **Unified Job Agent:** Merged `JobHunter` and `GapAnalyst` to reduce friction. Finding a job and analyzing it are now one continuous workflow.
- **Talker-Reasoner Pattern:**
    - **Talker (System 1):** Fast, conversational entry point.
    - **Supervisor (System 2):** Routes to `JobAgent` or `CareerCoach`.
- **Placeholder Implementation:**
    - All agents are currently implemented as **Placeholders** to validate the routing architecture before adding complex logic.