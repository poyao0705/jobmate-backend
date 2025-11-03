# ARCHITECTURE.md — Jobmate.Agent (Current Implementation)

**Scope:** Resume → skill extraction/normalization → job requirements extraction/normalization → gap analysis → learning items.  
**Backend Stack:** Flask • PostgreSQL/SQLite • ChromaDB • LangChain (LCEL) • OpenAI‑compatible LLM/embeddings.  
**Frontend Stack:** **Next.js 15 (App Router) + TypeScript + TailwindCSS + shadcn/ui** with Auth0 integration. The frontend consumes Flask APIs via proxy.

**Current Implementation Status:**
- ✅ **Vector Database**: ChromaDB with O*NET skills ontology (299 core skills, 32,681 technology examples)
- ✅ **Gap Analyzer**: Level-aware skill gap analysis with O*NET mapping
- ✅ **Career Engine**: Complete skill-only analysis pipeline
- ✅ **Resume Management**: S3 storage, parsing, and text extraction
- ✅ **O*NET Integration**: Comprehensive skills database with vector embeddings
- ✅ **Frontend Foundation**: Next.js 15 with Auth0, basic components, and API proxy

**Key decisions:**
- Skills are **first‑class ontology nodes** (`Skill`, `SkillAlias`) with O*NET integration.
- In current "skill‑only" mode, extracted skills are not persisted as `ResumeSkill`/`JobSkill` rows; normalized results are used in‑memory and persisted in `SkillGapReport.*_skills_json` only.
- **Embeddings live outside SQL** (Chroma); SQL stores only `vector_doc_id` references.
- **Provenance** captured via `ProcessingRun` (model names, params, code hash).
- **Skill‑only mode**: No resume/job vectors stored; only O*NET skills in ChromaDB.
- **One‑shot extraction**: extractor produces skills + levels + evidence; evidence is used for reporting and not persisted as separate rows.

---

## 0) Goals (MVP)
- Upload resume (PDF/DOCX/TXT) → parse → extract skills → normalize to ontology.
- Ingest a target job description → extract required skills → normalize to ontology.
- Compute a skill‑gap report (matched/missing/weak + score).
- Generate learning items for missing/weak skills; user schedules manually.
- Export gap report and learning items as JSON/CSV.

---

## 1) System Overview
- **Frontend:** Next.js 15 app (App Router) with Auth0 integration, deployed separately or as a static export served behind the Flask API (via CORS or reverse proxy). Uses **fetch**/**Redux Toolkit** for data fetching, **Server Actions/Route Handlers** only for client‑side conveniences (no business logic duplication).
- **Backend:** Flask app with API blueprint structure under `/api/*` routes; Python 3.11+.
- **Authentication:** Primary authentication via Auth0 JWT tokens (Bearer tokens) validated by `jwt_auth.py`. Legacy `User` model exists only for server-rendered Jinja templates (not used by Next.js frontend).
- **AI/RAG:** LangChain pipelines (LCEL) for extraction/normalization; ChromaDB vector store for `skills_ontology` only (skill-only mode).
- **Storage:**
  - **PostgreSQL/SQLite** for application data (`Resume`, `JobListing`, `Skill`, `SkillAlias`, `SkillGapReport`, `SkillGapStatus`, `PreloadedContext`, `LearningItem`, `Task`, `ProcessingRun`, `UserProfile`, etc.).
  - **ChromaDB** for O*NET skills embeddings + semantic search.
  - **S3** for uploaded files; optional local copy under `./data/uploads/` when `STORE_LOCAL_UPLOAD_COPY=1`.

> Dev setup: set `CHROMA_PERSIST_DIR=./instance/chroma`. Career Engine uses OpenAI `text-embedding-3-large` (fixed, 3072 dims). O*NET skills are pre-embedded and stored in ChromaDB. No resume/job vectors are stored in skill-only mode.

---

## 2) Data Model (PostgreSQL/SQLite — aligned with DATA_MODEL.md)
Core entities and relationships (see `DATA_MODEL.md` for full definitions):

- **Ontology:** `Skill(skill_id, name, taxonomy_path, vector_doc_id, framework, external_id, meta_json, onet_soc_code, occupation_title, commodity_title, hot_tech, in_demand, skill_type)`, `SkillAlias(skill_id_fk, alias, meta_json)`.
- **Authentication:** `UserProfile(id TEXT PK, email, name, picture, contact_*)` - Auth0 identity keyed by `sub`. Legacy `User` model exists only for templates.
- **Resume ingest:** `Resume(file_url, parsed_json, vector_doc_id, processing_run_id, s3_bucket, s3_key, status, is_default, user_id FK → UserProfile.id)`.
- **Job ingest:** `JobListing(title, description, vector_doc_id, company, location, salary_min, salary_max, …)`, `JobCollection(user_id FK → UserProfile.id, job_listing_id)`.
- **Reporting:** `SkillGapReport(user_id FK → UserProfile.id, resume_id, job_listing_id, score, matched_skills_json, missing_skills_json, weak_skills_json, resume_skills_json, analysis_version, analysis_json, processing_run_id)`, `SkillGapStatus(user_id FK → UserProfile.id, job_listing_id, status)`.
- **Context:** `PreloadedContext(user_id FK → UserProfile.id, job_listing_id, doc_type, content)` - precomputed context snippets for chat.
- **Learning:** `LearningItem(skill_id_fk, title, url, source, est_time_min, difficulty)` + `ReportLearningItem(report_id, learning_item_id, reason)`.
- **Ops:** `ProcessingRun(llm_model, embed_model, code_version_hash, params_json)`.
- **Chat:** `Chat(user_id FK → UserProfile.id, title, model, timestamp)`, `ChatMessage(chat_id, role, content, timestamp)`.

**Vector pointers:** `Skill.vector_doc_id` references Chroma documents (O*NET skills only in skill-only mode).

### O*NET/ESCO Integration (Skills Ontology)
- The skills ontology supports external taxonomies via explicit fields:
  - `Skill.framework` enum: `ONET` | `ESCO` | `Custom`
  - `Skill.external_id` string: external taxonomy identifier (e.g., O*NET element ID)
  - `Skill.meta_json`: stores taxonomy-specific attributes, e.g., `{ soc_code, element_id, importance, level, evidence_url }`
- `SkillAlias` may include preferred/alternate labels from O*NET/ESCO. Provenance for imported aliases should be captured in `SkillAlias.meta_json`.
- Normalization writes should persist the chosen `framework` and `external_id` on matched `Skill` rows so downstream reports can link to authoritative sources.

---

## 3) Vector Collections (ChromaDB)
- `skills_ontology` — one doc per `Skill` (aliases folded into the doc's text/metadata) with O*NET integration.  
- ~~`resumes`~~ — **Not used in skill-only mode** (resume text stored in SQL only).  
- ~~`jobs`~~ — **Not used in skill-only mode** (job text stored in SQL only).  
- ~~`learning_corpus`~~ — **Not used in skill-only mode** (learning items stored in SQL only).

> **Embeddings:** OpenAI `text-embedding-3-large` (requires `OPENAI_API_KEY`). O*NET skills are pre-embedded and stored in ChromaDB. No resume/job vectors are created in skill-only mode.

#### O*NET Metadata in `skills_ontology`
- Each skill document may include O*NET fields in `metadata` for deterministic grounding:
  - `framework`, `external_id` (O*NET element ID), `soc_code`, `importance`, `level`, `source_url`
- These fields enable hybrid retrieval (semantic + metadata filters), evidence linking, and explainability in reports.

---

## 4) Pipelines (LangChain, LCEL)

### 4.0 RAG Core (retrieval strategy) - ✅ IMPLEMENTED
1. Hybrid retrieval for skills and evidence:
   - Vector search over `skills_ontology` with `k=8` and metadata filters (e.g., `framework == ONET`).
   - Optional keyword filter using preferred/alternate labels from `SkillAlias`.
2. ~~Job/resume context retrieval~~ — **Not used in skill-only mode** (text stored in SQL only).
3. Grounding and validation:
   - Cross-check top skill candidates against O*NET `external_id`/`soc_code` where available.
   - Attach `source_url` and importance/level when present for explainability.
4. Output structured JSON with normalized `skill_id`, confidence, and evidence spans/links.

### 4.1 Resume Ingest - ✅ IMPLEMENTED
1. **Upload & parse** → detect MIME; extract text (PDF/DOCX/TXT).  
2. ~~**Chunk & embed**~~ → **Not used in skill-only mode** (text stored in SQL only).  
3. **Extract skills (LLM)** → all-in-one extraction returns `{name, level, nice_to_have, evidence_spans}` per skill.  
4. **Normalize to ontology** →
   - exact/alias match via `SkillAlias` cache; else semantic NN search over `skills_ontology` with threshold (e.g., ≥0.6).  
   - write `ResumeSkill` rows with `confidence` + `evidence` + optional `level_detected`.  
5. **Provenance** → create `ProcessingRun`; store id on `Resume`.

- When matched to external taxonomies, persist `Skill.framework` = `ONET`/`ESCO` and `Skill.external_id`. Include `source_url` (e.g., O*NET detail page) in `ResumeSkill.evidence` where available.

### 4.2 Job Listing Ingest - ✅ IMPLEMENTED
1. **Create JobListing** (title + description text).  
2. ~~**Chunk & embed**~~ → **Not used in skill-only mode** (text stored in SQL only).  
3. **Extract required skills** (LLM) → all-in-one extraction with `is_job_description=True`; normalize to ontology and attach `required_level`.
4. **Provenance** → `ProcessingRun` on `JobListing`.

- During normalization, prefer ontology nodes with `framework == ONET` when available; record `external_id`, importance/level from O*NET (if present) into `JobSkill.meta_json` for downstream scoring and transparency.

### 4.3 Gap Analysis - ✅ IMPLEMENTED
- **Inputs:** `resume_id`, `job_listing_id`.  
- **Join on skill IDs:** compare `ResumeSkill.skill_id_fk` vs `JobSkill.skill_id_fk`.  
- **Heuristics:**
  - Matched = intersection on skill FK.  
  - Weak = matched with low `confidence` or insufficient `level_detected` vs `required_level`.  
  - Missing = in `JobSkill` not present in `ResumeSkill`.  
  - Score = weighted coverage (e.g., Σ matched weights / Σ all weights × 100).  
- **Output:** `SkillGapReport` with `matched_skills_json`, `missing_skills_json`, `weak_skills_json`, `score`.

- RAG grounding: attach O*NET `source_url`/`external_id` for any normalized skills to support verifiable evidence in gap reports.

### 4.4 Learning Generation - ○ PLANNED
- For each **missing/weak** skill, query `learning_corpus` (semantic + metadata filters).  
- Rank by authority/recency/fit; synthesize **LearningItem** rows and link via **ReportLearningItem**.  
- Optional dedup and domain trust heuristics.

---

## 5) API (Stable Contracts; ID‑first)
All responses are JSON unless `?format=csv` is used on export endpoints.

> **Note:** To preserve SPEC compatibility, the route name `job_target` is kept at the API layer but maps internally to the `JobListing` entity.

### 5.1 API Structure
All API routes are under `/api/*` prefix and organized into blueprints:
- `/api/chat/*` - Chat functionality (chat.py)
- `/api/context/*` - Context management (context.py)
- `/api/external-jobs/*` - External job fetching (external_jobs.py)
- `/api/backend/gap/*` - Gap analysis endpoints (gap.py)
- `/api/job-collections/*` - Job collection management (job_collections.py)
- `/api/backend/jobs/*` - Job listings CRUD (jobListings.py)
- `/api/langgraph/*` - LangGraph agent endpoints (langgraph.py, langgraph_dev.py)
- `/api/backend/resume/*` - Resume upload and management (resumes.py)
- `/api/backend/tasks/*` - Task management (tasks.py)
- `/api/user-profile/*` - User profile management (user_profile.py)

All routes require JWT authentication via `@require_jwt` decorator from `jwt_auth.py` (except public endpoints).

### 5.2 Ingest - ✅ IMPLEMENTED
- **POST `/api/backend/resume/upload`**  
  **Body:** multipart `resume_file`  
  **Returns:** `{ "resume_id": int, "message": str, "chunks_created": int, "text_length": int, "s3_key": str, "bucket": str }`

- **GET `/api/backend/resume/<id>/download-url`**  
  **Returns:** `{ "download_url": str, "filename": str, "content_type": str, "file_size": int, "expires_in": int }`

- **GET/POST `/api/backend/jobs/*`** - Job listings management (see jobListings.py)

### 5.3 Analysis - ✅ IMPLEMENTED
- **POST `/api/backend/gap/run`** - Trigger gap analysis (background processing)
- **GET `/api/gap/by-job/<job_id>`** - Get gap report by job ID
- **DELETE `/api/backend/gap/by-job/<job_id>`** - Delete gap report

### 5.4 Learning - ○ PLANNED
- **POST `/api/learn/generate`**  
  **Body:** `{ "gap_report_id": int }`  
  **Returns:** `{ "learning_item_ids": [int,...] }`

- **GET `/api/learn/<learning_item_id>`**  
  **Returns:** the `LearningItem` JSON.

- **POST `/api/tasks/add`**  
  **Body:** `{ "learning_item_ids": [int,...] }`  
  **Returns:** `{ "added": int }`

### 5.5 Export - ○ PLANNED
- **GET `/api/export`**  
  **Query:** `type=gap_report|learning_items&format=json|csv&gap_report_id=...`  
  **Returns:** JSON or CSV file.

---

## 6) Contracts (schemas)

### 6.1 Extracted skills (LLM → app)
```json
{
  "sections": [ { "name": "Skills", "start": 120, "end": 340 } ],
  "skills": [
    {
      "name": "React.js",
      "nice_to_have": false,
      "evidence_spans": [ { "start": 120, "end": 158 } ],
      "evidence_texts": ["Built SPA with React 18"],
      "level": {"label": "working", "score": 2.0, "years": 1, "confidence": 0.6, "signals": ["explicit years"]}
    }
  ]
}
```

### 6.2 Normalized skills (for DB writes)
```json
{
  "normalized": [
    { "skill_id": "fe.react", "evidence": "Built SPA with React 18", "confidence": 0.84, "level_detected": "intermediate" },
    { "skill_id": "cloud.aws.ec2", "evidence": "Deployed on EC2", "confidence": 0.78 }
  ]
}
```

### 6.3 Gap report (API GET)
```json
{
  "gap_report_id": 42,
  "resume_id": 7,
  "job_target_id": 11,
  "score": 73.5,
  "matched_skills": [{ "skill_id": "fe.react", "evidence": "...", "level": "intermediate", "confidence": 0.84 }],
  "missing_skills": [{ "skill_id": "cloud.aws.ec2", "required_level": "basic", "rationale": "Listed in JD, not found in resume" }],
  "weak_skills": [],
  "created_at": "2025-10-16T01:23:45Z"
}
```

---

## 7) Frontend Pages (Next.js mapping)
| Route | Next.js Path | Status | Notes |
|---|---|---|---|
| Landing | `app/page.tsx` | ✅ | Auth0 integration, job list, contact dialog |
| Profile | `app/profile/page.tsx` | ✅ | User profile management |
| Work Goal | `app/work_goal/page.tsx` | ✅ | Task scheduling (placeholder) |
| Chat Help | `app/chat_help/page.tsx` | ✅ | AI chat interface (placeholder) |
| Upload | `app/upload/page.tsx` | ○ | Drag/drop resume; POST to `/api/backend/resume/upload` |
| Create Target | `app/target/new/page.tsx` | ○ | Form; posts to jobs API (no `job_target` alias) |
| Gap Report | `app/gap/[id]/page.tsx` | ○ | SSR fetch for fast TTFB; client hydration for tabs |
| Tasks | `app/tasks/page.tsx` | ○ | Client page with optimistic updates (local state + API) |
| Export | Button triggers GET `/api/export?...` | ○ | File download via `Response.blob()` |

**UI Kit:** shadcn/ui components; **state/data:** Redux Toolkit with RTK Query; **Auth:** Auth0 integration.

---



## 8) Repo Layout

### Current Implementation (✓ = exists, ○ = planned)

```
/                        # Project root
├── jobmate_agent/      # Main application package
│   ├── app.py          ✓ Flask app factory + API blueprint registration
│   ├── run.py          ✓ App entry point
│   ├── extensions.py   ✓ Flask extensions (db, bcrypt, migrate)
│   ├── jwt_auth.py     ✓ Auth0 JWT authentication middleware
│   ├── models.py       ✓ All data models:
│   │                   ✓ Legacy: User, Goal, Task, Note, Membership, UserSettings (templates only)
│   │                   ✓ Auth: UserProfile (Auth0 identity)
│   │                   ✓ Chat: Chat, ChatMessage
│   │                   ✓ AI: Resume, JobListing, Skill, SkillAlias, SkillGapReport, SkillGapStatus
│   │                   ✓ AI: PreloadedContext, LearningItem, ReportLearningItem, ProcessingRun
│   │                   ✓ Collections: JobCollection
│   │
│   ├── blueprints/     ✓ API blueprint structure
│   │   ├── __init__.py ✓
│   │   └── api/        ✓ API blueprint for /api/* routes
│   │       ├── __init__.py ✓ Blueprint registration and ChromaDB init
│   │       ├── chat.py     ✓ Chat functionality endpoints
│   │       ├── context.py  ✓ Context management endpoints
│   │       ├── external_jobs.py ✓ External job fetching endpoints
│   │       ├── gap.py      ✓ Gap analysis endpoints
│   │       ├── job_collections.py ✓ Job collection management
│   │       ├── jobListings.py ✓ Job listings CRUD
│   │       ├── langgraph.py ✓ LangGraph agent endpoints
│   │       ├── langgraph_dev.py ✓ LangGraph dev endpoints
│   │       ├── resumes.py  ✓ Resume upload and management
│   │       ├── tasks.py    ✓ Task management endpoints
│   │       └── user_profile.py ✓ User profile management
│   │
│   ├── services/       ✓ AI/RAG service layer
│   │   ├── career_engine/  ✓ Complete skill-only analysis pipeline
│   │   │   ├── career_engine.py ✓ Main orchestrator
│   │   │   ├── chroma_client.py ✓ ChromaDB wrapper for O*NET skills
│   │   │   ├── gap_analyzer.py ✓ Level-aware skill gap analysis
│   │   │   ├── llm_extractor.py ✓ LLM-based skill extraction
│   │   │   ├── onet_mapper.py ✓ O*NET skill mapping
│   │   │   ├── report_renderer.py ✓ Markdown report generation
│   │   │   └── level_estimator.py ✓ Skill level estimation
│   │   ├── resume_management/ ✓ Resume processing and storage
│   │   │   ├── resume_pipeline.py ✓ Complete resume processing pipeline
│   │   │   ├── resume_storage_service.py ✓ S3 storage and database operations
│   │   │   └── ingest.py ✓ File parsing utilities (PDF/DOCX/TXT)
│   │   ├── vector_store/   ✓ ChromaDB setup and operations
│   │   │   └── vector_store.py ✓ Collection management and helpers
│   │   ├── external_apis/  ✓ External job fetching
│   │   │   └── external_job_fetcher.py ✓ LinkedIn Job Search API integration
│   │   ├── context_builder.py ✓ Context building utilities
│   │   ├── document_processor.py ✓ Document processing utilities
│   │   └── preloader.py ✓ Preloader service
│   │
│   ├── templates/      ✓ Current Jinja2 templates (legacy - server-rendered only)
│   │   ├── dashboard/  ✓ Dashboard, user center, privacy/terms
│   │   ├── work_goal/  ✓ Work goal index, calendar, notes, today todo
│   │   ├── *.html      ✓ Login, register, chat, layout, index
│   │   └── partials/   ✓ Reusable template components
│   │
│   ├── static/         ✓ Current CSS/JS assets (legacy - to be replaced by Next.js)
│   │   ├── css/        ✓ Styling for all current features
│   │   └── js/         ✓ Client-side functionality
│   │
│   ├── migrations/     ✓ Alembic database migrations
│   │   └── versions/   ✓ Migration scripts
│   │
│   └── agents/         ✓ AI agents
│       └── gap_agent.py ✓ Gap analysis agent
│
├── data/               ✓ File storage
│   └── uploads/        ✓ Stored resume/job files
│
├── docs/               ✓ Documentation
│   ├── ARCHITECTURE.md ✓ This file
│   ├── DATA_MODEL.md   ✓ Current data model
│   ├── SPEC.md         ✓ MVP specifications
│   ├── JIRA.md         ✓ Implementation tasks
│   ├── WORKFLOW.md     ✓ End-to-end workflow
│   ├── PLAN.md         ✓ Implementation phases
│   └── CAREER_ENGINE_GUIDE.md ✓ Career Engine usage guide
│
├── frontend/           ✓ Next.js 15 frontend (replaces templates/ + static/)
│   ├── package.json    ✓ Next.js 15, TypeScript, TailwindCSS, shadcn/ui dependencies
│   ├── next.config.ts  ✓ Next.js configuration with API proxy
│   ├── tailwind.config.js ✓ TailwindCSS configuration
│   ├── tsconfig.json   ✓ TypeScript configuration
│   ├── .env.local      ✓ NEXT_PUBLIC_API_BASE_URL configuration
│   │
│   ├── app/            ✓ Next.js App Router structure
│   │   ├── layout.tsx  ✓ Root layout with shadcn/ui providers
│   │   ├── page.tsx    ✓ Landing page with Auth0 integration
│   │   ├── profile/    ✓ User profile pages
│   │   │   └── page.tsx ✓ Profile management
│   │   ├── work_goal/  ✓ Work goal pages
│   │   │   └── page.tsx ✓ Task management (placeholder)
│   │   ├── chat_help/  ✓ Chat pages
│   │   │   └── page.tsx ✓ AI chat interface (placeholder)
│   │   ├── upload/     ○ AI Features: Resume upload
│   │   │   └── page.tsx ○ FileDropzone for resume upload
│   │   ├── target/     ○ AI Features: Job target creation
│   │   │   └── new/page.tsx ○ Job target form
│   │   ├── gap/        ○ AI Features: Gap analysis
│   │   │   └── [id]/page.tsx ○ Gap report with SSR + tabs
│   │   ├── tasks/      ○ AI Features: Learning tasks
│   │   │   └── page.tsx ○ Task table with optimistic updates
│   │   └── globals.css ✓ Global styles with TailwindCSS
│   │
│   ├── components/     ✓ Reusable React components
│   │   ├── ui/         ✓ shadcn/ui components
│   │   │   ├── button.tsx ✓ Button component
│   │   │   ├── card.tsx ✓ Card component
│   │   │   ├── dialog.tsx ✓ Modal component
│   │   │   ├── tabs.tsx ✓ Tabs component
│   │   │   └── table.tsx ✓ Table component
│   │   ├── FileDropzone.tsx ○ Drag-and-drop file upload
│   │   ├── SummaryPanel.tsx ○ Resume summary display
│   │   ├── GapHeader.tsx ○ Gap report header
│   │   ├── GapTabs.tsx ○ Matched/Missing/Weak tabs
│   │   ├── EvidenceModal.tsx ○ Skill evidence modal
│   │   └── TaskTable.tsx ○ Learning tasks table
│   │
│   ├── lib/            ✓ Utility functions and configurations
│   │   ├── api.ts      ✓ Typed API client functions
│   │   ├── utils.ts    ✓ Utility functions
│   │   └── validations.ts ✓ Form validation schemas
│   │
│   ├── store/          ✓ Redux Toolkit state management
│   │   ├── store.ts    ✓ Redux store configuration
│   │   ├── provider.tsx ✓ Redux provider component
│   │   └── hooks.ts    ✓ Redux hooks
│   │
│   └── types/          ✓ TypeScript type definitions
│       ├── api.ts      ✓ API response types
│       ├── resume.ts   ✓ Resume-related types
│       └── gap.ts      ✓ Gap analysis types
│
└── instance/           ✓ Database and vector store
    ├── efficientai.db  ✓ SQLite database with all models
    └── chroma/         ✓ ChromaDB vector store with O*NET skills
```

### Integration Notes

**Authentication Architecture:**

- **Primary Auth**: Auth0 JWT tokens validated by `jwt_auth.py` with `@require_jwt` decorator
- **User Model**: `UserProfile` model (id = Auth0 `sub`) owns Resume/JobCollection/SkillGapReport entities
- **Legacy Auth**: `User` model exists only for server-rendered Jinja templates, not used by Next.js frontend
- **JWT Flow**: Frontend obtains JWT from Auth0, sends in `Authorization: Bearer <token>` header
- **Hydration**: Optional `hydrate=True` parameter in `@require_jwt` fetches and upserts UserProfile from Auth0 Management API

**Current Features → AI Resume System Integration:**

- **UserProfile Model**: Owns Resume/JobCollection/SkillGapReport/SkillGapStatus entities
- **Task Model**: Has `learning_item_id` field (per DATA_MODEL.md) - ready for AI-generated learning items
- **Goal Model**: Provides foundation for organizing learning objectives from skill gaps
- **Chat System**: References UserProfile, DeepSeek integration for AI resume analysis interactions
- **Notes System**: Can store AI-generated insights and user annotations on gap reports

**Next.js Frontend Structure:**
- **App Router**: Uses Next.js 15 App Router for file-based routing
- **TypeScript**: Full type safety with API contracts and component props
- **TailwindCSS**: Utility-first CSS framework for consistent styling
- **shadcn/ui**: Accessible component library for consistent UI patterns
- **API Integration**: Typed API client in `/lib/api.ts` for Flask backend communication
- **State Management**: TanStack Query (or SWR) for server state, React state for UI
- **File Organization**: Clear separation of pages, components, utilities, and types

---

## 9) Observability
- **Structured logs** per step (ingest, extract, normalize, compare, learn) incl. latency + token metrics.
- **ProcessingRun** recorded for `Resume`, `JobListing`, `SkillGapReport` with `llm_model`, `embed_model`, `code_version_hash`.
- **Debug artifacts**: store top‑K chunk IDs, match scores, and thresholds alongside reports.

---

## 10) Security & Privacy (MVP/dev)
- File size limits, MIME allowlist; sanitize/strip macros from DOCX.
- Do not store API keys in DB; use environment variables.
- Treat resumes as PII; keep local only for MVP. Consider per‑user directories.

---

## 11) Non‑Goals (MVP)
- No OAuth/calendar integration.
- No large‑scale scraping of job markets.
- No multi‑tenant auth or RBAC.

---

## 12) Evolution (post‑MVP)
- **LangGraph orchestration** for retries, human‑in‑loop on low‑confidence skill matches, and checkpointing.
- **Multi‑resume / multi‑job comparisons** with parallel nodes.
- **External skill frameworks** mapping (SFIA, O*NET) stored in `Skill.meta_json`.
- **Confidence calibration** via small labeled set to tune thresholds.

---

## 13) Migration Notes

### Backend (Flask)
- Enable CORS on Flask (dev): `flask_cors` or reverse proxy through Next.js dev server.
- Keep all business logic in Flask; React components only orchestrate UX.
- Maintain existing API contracts during frontend migration.

### Frontend (Next.js)
- Configure envs in Next.js: `NEXT_PUBLIC_API_BASE_URL`.
- Use Next.js App Router for file-based routing (replaces Flask route decorators).
- Implement SSR for `/gap/[id]` page for fast initial render.
- Use client-side hydration for interactive features (tabs, modals, forms).
- Leverage shadcn/ui components for consistent, accessible UI patterns.
- Implement typed API client for type-safe communication with Flask backend.

### Development Workflow
- **Dev Mode**: Next.js dev server on `localhost:3000`, Flask API on `localhost:5000` with CORS.
- **Production**: Reverse proxy (Nginx/Caddy) serving Next.js static/edge app and proxying `/api/*` to Flask.
- **Alternative**: Next.js hosted (Vercel) with `NEXT_PUBLIC_API_BASE_URL` pointing to Flask API URL.

### File Migration Mapping
- `templates/*.html` → `frontend/app/*/page.tsx`
- `static/css/*.css` → `frontend/app/globals.css` (TailwindCSS)
- `static/js/*.js` → `frontend/components/*.tsx` and `frontend/hooks/*.ts`
- `templates/partials/*.html` → `frontend/components/ui/*.tsx`
