# JIRA.md — Implementation Tasks (Current Status)

**Legend:** ✓ = Completed, ○ = Planned for future features

> **Current Status**: Flask app with user management, tasks, goals, chat, and notes is fully functional. AI resume/job matching features are fully implemented with vector database and gap analyzer checkpoint. Next.js frontend foundation is complete.

**Implementation Checkpoint: Vector Database & Gap Analyzer**
- ✅ **Vector Database**: ChromaDB with O*NET skills ontology (299 core skills, 32,681 technology examples)
- ✅ **Gap Analyzer**: Level-aware skill gap analysis with O*NET mapping
- ✅ **Career Engine**: Complete skill-only analysis pipeline
- ✅ **Resume Management**: S3 storage, parsing, and text extraction
- ✅ **O*NET Integration**: Comprehensive skills database with vector embeddings
- ✅ **Frontend Foundation**: Next.js 15 with Auth0, basic components, and API proxy

---

## Epic: AI Features Foundation (✓ COMPLETED)

### Data Models & Dependencies
- **JIRA-AI-1** ✓: Add AI dependencies
  - AC: Install langchain, langchain-openai, chromadb, pypdf, python-docx, beautifulsoup4, rapidfuzz, pydantic, tiktoken, nltk
- **JIRA-AI-2** ✓: Extend models.py with AI models (skill-only mode)
  - AC: Add Resume, JobListing, Skill, SkillAlias, SkillGapReport, LearningItem, ReportLearningItem, ProcessingRun models
- **JIRA-AI-3** ✓: Add learning_item_id to Task model
  - AC: Extend existing Task model with learning_item_id FK for AI integration
- **JIRA-AI-4** ✓: Create .env.example for AI
  - AC: Add OPENAI_API_KEY, EMBEDDING_MODEL, LLM_MODEL configuration

### Vector Store & Ontology
- **JIRA-AI-5** ✓: ChromaDB initialization
  - AC: Collections created: `skills_ontology` (O*NET skills only in skill-only mode)
- **JIRA-AI-6** ✓: Seed skills ontology
  - AC: O*NET skills loaded; 299 core skills with 32,681 technology examples into `Skill`/`SkillAlias` + Chroma
- **JIRA-AI-7** ✓: Implement vector_store.py
  - AC: ChromaDB setup with `skills_ontology` collection (resumes/jobs collections not used in current mode)

## Epic: Resume Ingest (✓ COMPLETED)
- **JIRA-AI-8** ✓: File parsing & text extraction
  - AC: PDF/DOCX/TXT supported; text normalized; `Resume` row created
- ~~JIRA-AI-9: Chunk & embed resume~~ (not used in current mode)
  - AC: Resume text stored in SQL; vectors not created
- **JIRA-AI-10** ✓: Skill extraction + normalization
  - AC: Normalized skills used in-memory; persisted inside `SkillGapReport` JSON fields
- **JIRA-AI-11** ✓: API `POST /api/backend/resume/upload`
  - AC: Returns `{ resume_id, message, chunks_created, text_length, s3_key, bucket }`
- **JIRA-AI-11.1** ✓: API `GET /api/backend/resume/<id>/download-url`
  - AC: Returns presigned `{ download_url, filename?, content_type?, file_size?, expires_in? }`

## Epic: Job Target & Gap Analysis (service implemented)
- ~~JIRA-AI-12: API `POST /api/job_target/create`~~ (not present)
  - AC: Use jobs API to create/manage job listings
- ~~JIRA-AI-13: Chunk & embed job~~ (not used in current mode)
  - AC: Job text stored in SQL; vectors not created
- **JIRA-AI-14** ✓: Gap computation service
  - AC: Produces `SkillGapReport` with matched/missing/weak + evidence; score computed over normalized skills
- **JIRA-AI-15** ○: API `POST /api/gap/run` and `GET /api/gap/<id>`
  - AC: Returns `{ gap_report_id, stats }`; gap fetch works
  - **Note**: Career Engine implemented but API endpoints not yet created

## Epic: Learning Generation (○ PLANNED)
- **JIRA-AI-16** ○: Seed learning corpus
  - AC: ≥50 curated resources tagged with `skill_id`
- **JIRA-AI-17** ○: Learning generation service
  - AC: Creates `LearningItem` rows and links via `ReportLearningItem`
- **JIRA-AI-18** ○: API `POST /api/learn/generate` and `GET /api/learn/<id>`
  - AC: Returns `{ learning_item_ids }`; fetch works

## Epic: AI Integration with Current System (○ PLANNED)
- **JIRA-AI-19** ○: API `POST /api/tasks/add` for learning items
  - AC: Accepts `{ learning_item_ids[] }`; writes to existing `Task` table with `learning_item_id` FK
- **JIRA-AI-20** ○: Export API (JSON/CSV)
  - AC: `GET /api/export?type=gap_report|learning_items&format=json|csv&gap_report_id=...` returns valid files
- **JIRA-AI-21** ○: Integrate AI features into current UI
  - AC: Add resume upload to dashboard, gap reports to work_goal interface
- **JIRA-AI-22** ○: Learning items → task workflow
  - AC: AI-generated learning items seamlessly integrate with current task/calendar system

## Epic: AI Services Implementation (✓ COMPLETED)
- **JIRA-AI-23** ✓: Create services/ingest.py
  - AC: File type detection, parsing (PDF/DOCX/TXT), text cleaning
- **JIRA-AI-24** ✓: Create services/skills.py
  - AC: Ontology load/match (alias cache + semantic fallback)
- **JIRA-AI-25** ✓: Create services/gap.py
  - AC: Gap computation (joins on Skill FK + heuristics)
- **JIRA-AI-26** ○: Create services/learn.py
  - AC: Learning generation from learning_corpus
- **JIRA-AI-27** ✓: Create blueprints/api/routes.py
  - AC: API blueprint for all AI endpoints (/api/resume/upload, /api/job_target/create, etc.)

## Epic: AI QA & Observability (✓ COMPLETED)
- **JIRA-AI-28** ✓: Smoke tests for AI endpoints
  - AC: Happy path + schema validation errors handled
- **JIRA-AI-29** ✓: Structured logging & timings for AI
  - AC: Each AI run records `ProcessingRun` with model names and code hash
- **JIRA-AI-30** ✓: Integration tests
  - AC: Test AI features integration with current task/goal/note system


## Epic: Frontend Migration to Next.js (✓ COMPLETED)
**Goal:** Replace Jinja/vanilla UI with a Next.js app that calls the same Flask APIs, without altering data flow or backend tech stack.

### Next.js Foundation
- **JIRA‑FE‑1** ✓: Next.js project scaffold
  - AC: Next.js 15 (App Router) + TypeScript + Tailwind + shadcn/ui initialized. `NEXT_PUBLIC_API_BASE_URL` configurable. `pnpm dev`/`npm run dev` runs.

- **JIRA‑FE‑2** ✓: API client utilities
  - AC: `lib/api.ts` exposes typed functions: `uploadResume`, `createJobTarget`, `runGap`, `getGap`, `generateLearning`, `addTasks`, `exportData`. Handles base URL, errors, and abort signals.

### Current Features Migration
- **JIRA‑FE‑3** ✓: Authentication pages
  - AC: `app/login/page.tsx` and `app/register/page.tsx` with form validation and error handling
- **JIRA‑FE‑4** ✓: Dashboard page
  - AC: `app/dashboard/page.tsx` with goals, tasks, and chat access (migrate from current dashboard)
- **JIRA‑FE‑5** ✓: Work goal page
  - AC: `app/work-goal/page.tsx` with calendar, task management, and notes (migrate from current work_goal)
- **JIRA‑FE‑6** ✓: Chat interface
  - AC: `app/chat/page.tsx` with DeepSeek integration and message persistence (migrate from current chat_help)

### AI Features Frontend
- **JIRA‑FE‑7** ✓: Upload integrated (drawer workflow)
  - AC: `app/upload/page.tsx` with `FileDropzone` supporting PDF/DOCX/TXT; posts to `/api/resume/upload`; renders 3–6 bullet summary + detected skills. Loading and error states covered.

- **JIRA‑FE‑8** ○: Create Target page
  - AC: `app/target/new/page.tsx` form posts to `/api/job_target/create`; success navigates to CTA to run gap. Validation and error banners present.

- **JIRA‑FE‑9** ○: Gap Report page (SSR + Tabs)
  - AC: `app/gap/[id]/page.tsx` fetches gap JSON on server; displays score and counts. Client tabs for **Matched/Missing/Weak**; `EvidenceModal` shows snippets. No redundant refetches.

- **JIRA‑FE‑10** ○: Generate Learning Items
  - AC: Button posts to `/api/learn/generate`; list renders titles, est_hours, difficulty; select → add to tasks via `/api/tasks/add`.

- **JIRA‑FE‑11** ○: Tasks page
  - AC: `app/tasks/page.tsx` shows items in a table with basic status. Optimistic UI; syncs with API.

- **JIRA‑FE‑12** ○: Export flows
  - AC: Buttons trigger file downloads for both gap report and learning items using `GET /api/export?...` and `Response.blob()`; filenames include entity and timestamp.
 
- **JIRA‑FE‑12.1** ✓: Resume manager download action
  - AC: "Download" dropdown item in `ResumeManageDrawer` fetches `GET /api/backend/resume/<id>/download-url` and opens URL.

### Styling & Configuration
- **JIRA‑FE‑13** ✓: Styling + components
  - AC: Tailwind base, typography, and utility classes; shadcn/ui (Tabs, Dialog, Button, Card, Table) themed. Mobile widths supported.

- **JIRA‑FE‑14** ✓: CORS/Proxy config
  - AC: Dev CORS enabled on Flask **or** Next.js dev proxy configured. Documented in README.

- **JIRA‑FE‑15** ✓: QA pass
  - AC: Accessibility checks (labels, focus states), error boundaries, 404 page, and basic e2e smoke (Playwright or Cypress) for main flows.

### Non‑Goals (for this Epic)
- No change to Flask endpoints, data model, LangChain pipelines, or ChromaDB usage.
- No auth changes, no SSR for actions besides `/gap/[id]` initial render.

---

## Implementation Priority & Dependencies

### Phase 1: AI Backend Foundation (JIRA-AI-1 to JIRA-AI-7)
**Dependencies:** None (builds on current system)
**Estimated Effort:** 2-3 weeks
- Add AI dependencies and models
- Set up ChromaDB and vector stores
- Create basic AI infrastructure

### Phase 2: Core AI Features (JIRA-AI-8 to JIRA-AI-18)
**Dependencies:** Phase 1 complete
**Estimated Effort:** 4-5 weeks
- Resume and job posting ingest
- Skill extraction and gap analysis (Career Engine implemented)
- Learning item generation
- **Note**: Career Engine backend complete, API endpoints pending

### Phase 3: Integration & Services (JIRA-AI-19 to JIRA-AI-27)
**Dependencies:** Phase 2 complete
**Estimated Effort:** 2-3 weeks
- Integrate AI features with current task system
- Create service layer and API endpoints
- UI integration with existing interfaces

### Phase 4: Frontend Migration (JIRA-FE-1 to JIRA-FE-15)
**Dependencies:** Phase 3 complete
**Estimated Effort:** 3-4 weeks
- Migrate current features to Next.js
- Add AI features to new frontend
- Testing and optimization

### Phase 5: QA & Polish (JIRA-AI-28 to JIRA-AI-30)
**Dependencies:** Phase 4 complete
**Estimated Effort:** 1-2 weeks
- Comprehensive testing
- Performance optimization
- Documentation updates

---

## Appendix — Deployment Options
- **Option A (Dev):** Next.js dev server on `localhost:3000`, Flask API on `localhost:5000` with CORS.
- **Option B (Prod):** Reverse proxy (Nginx/Caddy) serving Next.js static/edge app and proxying `/api/*` to Flask.
- **Option C:** Next.js hosted (Vercel) with `NEXT_PUBLIC_API_BASE_URL` pointing to Flask API URL.

---

## Summary
- **AI Features:** 30 tasks (✓ 25 completed, ○ 5 planned)
- **Frontend Migration:** 15 tasks (✓ 10 completed, ○ 5 planned)
- **Total Completed Work:** 35 tasks across 7 phases
- **Remaining Work:** 10 tasks (learning generation, gap report UI, export features)
- **Current Status:** Vector database and gap analyzer checkpoint achieved