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
    
### Agents
- job hunter (Find it)
    - suggest job
    - job search
- gap analyst (Analyze it)
    - gap analysis
    - resume refinement/tailoring
    - cover letter generation
- career coach (Learn about it)
    - concept explanation
    - learning item generation (via internal knowledge/chat)
    - learning path planning
    - career development
- ai interviewer (Practice for it)
    - ai interview

### Agent enhancement: 
- Adaptive RAG on Career Coach

### Architecture Decisions (2025-11-23)
- **Agent Roles:**
    - **Job Hunter:** Focus on *finding* jobs using Internal DB (primary) + Web Search (fallback). No complex RAG.
    - **Application Agent (formerly Gap Analyst):** Focus on *applying*. Deterministic RAG (Resume + Job). Handles Gaps, Resume Tailoring, Cover Letters. Proactively suggests Learning Plans.
    - **Career Coach:** Focus on *learning*. **Advanced RAG (Adaptive + CRAG)**. Routes between Chat, Internal Skill DB, and Web Search (for courses/trends). Generates recursive Skill Trees.
    - **Interviewer:** Separate Agent & UI Page. Handles mock interviews with specific job context.

- **Advanced RAG Strategy:**
    - Only implemented in `CareerCoach`.
    - **Adaptive Router:** Decides datasource (Chat vs DB vs Web).
    - **CRAG Grader:** Checks DB result quality; falls back to Web if poor.

- **UI/UX:**
    - **Unified Chat:** Main entry point for Job Hunter, Application Agent, Career Coach.
    - **Specialized Widgets:** Chat renders artifacts (e.g., "Gap Report", "Learning Plan") with action buttons.
    - **Separate Page:** Interviewer Agent runs in a dedicated "Interview Room" mode.

- **Talker-Reasoner Pattern (System 1 / System 2):**
    - **The Talker (System 1):** Fast LLM (GPT-4o-mini). Handles "Hello", small talk, and personality. Decides if "Real Work" is needed.
    - **The Reasoner (System 2):** The Supervisor + Specialist Agents. Only invoked when the Talker delegates a task.
    - **Flow:** User -> Talker -> (if task) -> Supervisor -> Worker -> Talker (to reply).