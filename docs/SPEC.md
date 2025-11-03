# SPEC.md — Jobmate.Agent (Current Implementation)

**Legend:** ✓ = Currently implemented, ○ = Planned for future features

**Current Implementation Status:**
- ✅ **Vector Database**: ChromaDB with O*NET skills ontology (299 core skills, 32,681 technology examples)
- ✅ **Gap Analyzer**: Level-aware skill gap analysis with O*NET mapping
- ✅ **Career Engine**: Complete skill-only analysis pipeline (one-shot LLM extractor)
- ✅ **Resume Management**: S3 storage, parsing, and text extraction
- ✅ **O*NET Integration**: Comprehensive skills database with vector embeddings
- ✅ **Frontend Foundation**: Next.js 15 with Auth0, basic components, and API proxy

## 1. User Stories

### Current Implementation (✓)
1. As a user, I can authenticate via Auth0 (JWT tokens) to access my personal dashboard. *(Legacy User model exists only for server-rendered templates)*
2. As a user, I can create and manage goals with descriptions.
3. As a user, I can create tasks with start/end dates and associate them with goals.
4. As a user, I can view my tasks in a calendar interface and mark them as complete.
5. As a user, I can create and manage notes, optionally linking them to tasks.
6. As a user, I can chat with AI assistants (DeepSeek) and save AI responses as notes.
7. As a user, I can manage my membership and user settings.

### Implemented AI Features (✓)
1. As a user, I can upload my resume and get a quick summary plus extracted skills.
2. As a user, I can define a target role (title + description) to compare against.
3. As a user, I can run a skill-gap report between my resume and a target role (via Career Engine).
4. As a user, I can see skill matches backed by authoritative O*NET data with source links.
5. As a user, I can trust that skill gap analysis uses standardized, industry-recognized skill taxonomies.

### Planned AI Features (○)
1. As a user, I can generate learning items to address missing/weak skills and add selected items to My Tasks.
2. As a user, I can export my gap report and learning items as JSON or CSV.
3. As a user, I can view detailed gap reports with evidence and confidence scores.
4. As a user, I can manage multiple resumes and compare them against different job targets.

## 2. UX Flows

### Current Implementation (✓)
- **Auth0 Login → Dashboard:** Auth0 JWT authentication → user dashboard with goals, tasks, and chat access. *(Legacy login/register routes exist only for server-rendered templates)*
- **Goal Management:** Create/edit/delete goals with descriptions.
- **Task Management:** Create tasks with dates, associate with goals, mark complete.
- **Calendar View:** Drag-and-drop task scheduling, date-based task filtering.
- **Notes System:** Create/edit/delete notes, optionally link to tasks.
- **Chat Interface:** AI conversations with DeepSeek, save responses as notes.

### Implemented AI Features (✓)
- **Upload Resume → Summary:** Drag/drop (FileDropzone) → call `/api/backend/resume/upload` → show summary + detected skills.
- **Create Target → Analyze:** Form → use jobs API (no `job_target` alias in current API) → CTA to run Gap.
- **Gap Report View:** SSR initial fetch to render coverage score quickly; tabs (client) for **Matched / Missing / Weak** with evidence modal.
- **O*NET Integration:** Skills matched to O*NET taxonomy show source links and importance scores.
- **Hybrid Skill Matching:** Prefer O*NET skills when available, fallback to custom ontology.

### Planned AI Features (○)
- **Generate Learning:** Client action → `/api/learn/generate` → list of items; add to **My Tasks**.
- **My Tasks:** Client page with optimistic add; persists via `/api/tasks/add`.
- **Export Features:** JSON/CSV export of gap reports and learning items.
- **Advanced Gap Analysis:** Detailed evidence modal with confidence scores and rationale.

## 3. Screens

### Current Implementation (✓)
- `/` Landing page with Auth0 login (Next.js frontend)
- `/profile` User profile management (Auth0 UserProfile)
- `/work_goal` Task management with calendar and notes
- `/chat_help` AI chat interface
- *(Legacy `/login`, `/register`, `/dashboard` routes exist only for server-rendered Jinja templates)*

### Implemented AI Features (✓)
- `/` Landing: Auth0 integration, job list, contact dialog
- `/profile` Profile: User profile management
- `/work_goal` Work Goal: Task scheduling (placeholder)
- `/chat_help` Chat Help: AI chat interface (placeholder)

### Planned AI Features (○)
- `/upload` Upload: `FileDropzone`, `SummaryPanel`.
- `/gap/[id]` Gap Report: `GapHeader`, `GapTabs`, `EvidenceModal`.
- `/tasks` Tasks: `TaskTable` (integrates with current task system).

## 4. API Contracts

### Current Implementation (✓)
**API Routes (all under `/api/*` prefix, require JWT authentication):**
- `POST /api/chat/*` → Chat functionality (see chat.py)
- `GET /api/backend/tasks/*` → Task management endpoints
- `GET /api/user-profile/*` → User profile management
- `GET /api/context/*` → Context management
- *(Legacy routes `/login`, `/register`, `/dashboard`, `/work_goal/*`, `/chat_help` exist only for server-rendered templates and are not used by Next.js frontend)*

### Implemented AI Features (✓)
> Job creation uses the existing jobs API. In current mode, normalized skills are used in-memory and persisted inside `SkillGapReport` JSON fields.

- `POST /api/backend/resume/upload` → `{ resume_id, message, chunks_created, text_length, s3_key, bucket }` *(requires JWT)*
- `GET /api/backend/resume/<id>/download-url` → `{ download_url, filename?, content_type?, file_size?, expires_in? }` *(requires JWT)*
- `POST /api/backend/gap/run` → Trigger gap analysis (background processing) *(requires JWT)*
- `GET /api/gap/by-job/<job_id>` → Get gap report by job ID *(requires JWT)*
- `DELETE /api/backend/gap/by-job/<job_id>` → Delete gap report *(requires JWT)*
- `GET /api/job-collections` → Get saved jobs with gap status *(requires JWT)*
- `POST /api/job-collections/<job_id>` → Save job and trigger gap analysis *(requires JWT)*
- `DELETE /api/job-collections/<job_id>` → Unsave job *(requires JWT)*
- **Career Engine**: Complete skill-only analysis pipeline with level-aware gap analysis
- **SkillGapStatus**: Status tracking for gap generation (`generating`/`ready`) for efficient polling

### Planned AI Features (○)
- `POST /api/learn/generate` → `{ learning_item_ids[] }` (Body: `{ gap_report_id }`)
- `GET /api/learn/<id>` → `LearningItem`
- `POST /api/tasks/add` → `{ added }` (Body: `{ learning_item_ids[] }`)
- `GET /api/export?type=gap_report|learning_items&format=json|csv&gap_report_id=...`

### O*NET Integration APIs (○)
- `GET /api/skills/onet/search?q=<query>&limit=<n>` → Search O*NET skills with metadata
- `GET /api/skills/onet/<element_id>` → Get O*NET skill details with source links
- `POST /api/skills/onet/sync` → Sync O*NET data (admin endpoint)
- `GET /api/skills/frameworks` → List available skill frameworks (Custom, O*NET, ESCO)

## 5. Non-Functional

### Current Implementation (✓)
- **Authentication**: Primary authentication via Auth0 JWT tokens (Bearer tokens) validated by `jwt_auth.py`. Legacy User model with bcrypt exists only for server-rendered templates.
- **Database**: PostgreSQL/SQLite with SQLAlchemy ORM and Alembic migrations
- **AI Integration**: DeepSeek API for chat functionality
- **Frontend**: Next.js 15 (App Router) with Auth0 integration, TypeScript, TailwindCSS, shadcn/ui
- **Backend API**: Flask with `/api/*` blueprint structure, CORS enabled for frontend
- **Error handling**: JSON error responses for API, flash messages for legacy templates
- **User Model**: `UserProfile` (Auth0 identity, id = Auth0 `sub`) owns AI entities; legacy `User` model for templates only

### Implemented AI Features (✓)
- **Skill-Only Mode**: Normalized skills computed at runtime; persisted in `SkillGapReport` JSON fields (no `ResumeSkill`/`JobSkill` tables).
- **Models**: See ARCHITECTURE.md §2 and DATA_MODEL.md. Includes `SkillGapStatus` for status tracking and `PreloadedContext` for chat context snippets.
- **Error handling**: 400 for bad input; 422 for parsing failures; 500 for unexpected.
- **Next.js SSR** for `/gap/[id]` (fast first paint), client hydration for interactivity.
- **Tailwind** for styles; shadcn/ui for accessible components.
- **O*NET Integration**: 299 core skills with 32,681 technology examples, vector embeddings.
- **Gap Analysis**: Background processing with status tracking via `SkillGapStatus` model for efficient polling.

### Planned AI Features (○)
- **Export**: JSON or CSV; UTF-8, RFC4180 for CSV.
- **Maintain CSV/JSON export** behavior (browser download).

### O*NET Integration Requirements (○)
- **Data Source**: O*NET Web Services API (free tier) with fallback to database download
- **Sync Frequency**: Annual O*NET updates with manual sync capability
- **Performance**: O*NET skill search < 200ms, hybrid retrieval < 500ms
- **Coverage**: Target 80% of common job skills mapped to O*NET
- **Reliability**: Graceful fallback to custom ontology when O*NET unavailable
- **Compliance**: O*NET data usage per CC BY 4.0 license terms
- **Caching**: O*NET API responses cached for 24 hours minimum

## 6. Acceptance Criteria

### Current Implementation (✓)
- User can authenticate via Auth0 and access dashboard (Next.js frontend)
- Goals can be created, edited, and deleted
- Tasks can be created with dates and associated with goals
- Calendar interface allows drag-and-drop task scheduling
- Notes can be created, edited, and linked to tasks
- AI chat works with DeepSeek API and responses can be saved as notes
- User settings and membership management functional

### Implemented AI Features (✓)
- Uploading a valid resume returns `resume_id` and a 3–6 bullet summary.
- Gap report shows at least 3 examples of evidence snippets for matched skills when available.
- Gap report page renders server‑side within 1.5s (dev) given reachable API.
- Upload flow handles 10MB PDFs; shows progress & error states.
- Tabs switch without refetch (data cached in Query cache).
- O*NET skills provide authoritative skill matching with statistical validation.

### Planned AI Features (○)
- Learning generation produces at least 5 items with `est_hours` and `priority` fields populated.
- Export produces valid JSON and CSV for the selected scope.
- AI-generated learning items integrate seamlessly with existing task system.
