# Jobmate.Agent — DATA_MODEL.md (Current Implementation)

Author: Jobmate.Agent
Version: 3.0
Status: Updated to reflect current implementation (skill-only mode) with vector database and gap analyzer service; `ResumeSkill`/`JobSkill` tables are not used in this mode

This file defines the relational data model for the **current implementation** including user management, tasks, goals, chat, and AI resume/job matching in skill-only mode. It reflects the decisions to make **skills first‑class** (ontology nodes), store **embeddings out of SQL**, and capture **LLM/RAG provenance** via `ProcessingRun`. In this mode, normalized skills are used at runtime and persisted inside `SkillGapReport` JSON fields rather than in separate `ResumeSkill`/`JobSkill` tables.

**Legend:** ✓ = Currently implemented, ○ = Planned for future features

**Current Implementation Status:**
- ✅ **Vector Database**: ChromaDB with O*NET skills ontology (299 core skills, 32,681 technology examples)
- ✅ **Gap Analyzer**: Level-aware skill gap analysis with O*NET mapping
 - ✅ **Career Engine**: Complete skill-only analysis pipeline (one-shot LLM extraction)
- ✅ **Resume Management**: S3 storage, parsing, and text extraction
- ✅ **O*NET Integration**: Comprehensive skills database with vector embeddings
- ✅ **Frontend Foundation**: Next.js 15 with Auth0, basic components, and API proxy

---

## 1) Current Implementation (✓)

### User ✓ (legacy auth)
- `id` PK  
- `username` TEXT UNIQUE  
- `email` TEXT UNIQUE  
- `password_hash` TEXT *(authentication)*
- `is_premium` BOOLEAN DEFAULT FALSE
- `membership_plan` TEXT DEFAULT 'free'
- `membership_renewal_date` DATE NULL
- `email_notifications` BOOLEAN DEFAULT TRUE

### Chat ✓
- `id` PK  
- `user_id` FK → User.id  
- `title` TEXT  
- `model` TEXT *(DeepSeek integration)*
- `timestamp` DATETIME

### ChatMessage ✓
- `id` PK  
- `chat_id` FK → Chat.id  
- `role` TEXT *("user" | "assistant" | "system")*  
- `content` TEXT  
- `timestamp` DATETIME

### Note ✓
- `id` PK  
- `user_id` FK → User.id  
- `task_id` FK → Task.id NULL *(optional task association)*
- `content` TEXT  
- `created_at` DATETIME

### Task ✓
- `id` PK  
- `user_id` FK → User.id  
- `goal_id` FK → Goal.id NULL *(goal association)*
- `title` TEXT  
- `description` TEXT NULL  
- `start_date` DATE NULL *(calendar integration)*
- `end_date` DATE NULL *(calendar integration)*
- `done` BOOLEAN DEFAULT FALSE
- `priority` INTEGER DEFAULT 0
- `learning_item_id` FK → LearningItem.id NULL *(✓ AI integration implemented)*
- `created_at` DATETIME

### Goal ✓
- `id` PK  
- `user_id` FK → User.id  
- `title` TEXT  
- `description` TEXT NULL  
- `created_at` DATETIME

### Membership ✓
- `id` PK  
- `user_id` FK → User.id UNIQUE
- `plan` TEXT DEFAULT 'free'
- `renewal_date` DATE NULL

### UserSettings ✓
- `id` PK  
- `user_id` FK → User.id UNIQUE
- `language` TEXT DEFAULT 'en'

### UserProfile ✓ (Auth identity; owner of resumes/jobs)
- `id` TEXT PK  
- `email` TEXT INDEX  
- `email_verified` BOOLEAN DEFAULT FALSE  
- `name` TEXT  
- `picture` TEXT  
- `contact_name` TEXT NULL  
- `contact_email` TEXT NULL  
- `contact_phone_number` TEXT NULL  
- `contact_location` TEXT NULL  
- Notes: Auth0 identity profile keyed by `sub` (stored in `id`). No FK to `users`.

### ProcessingRun ✓
- `id` PK  
- `created_at` DATETIME  
- `llm_model` TEXT  
- `embed_model` TEXT  
- `code_version_hash` TEXT  
- `params_json` JSON NULL

### Resume ✓
- `id` PK  
- `user_id` FK → UserProfile.id (TEXT)  
- `file_url` TEXT NULL  
- `s3_bucket` TEXT NULL  
- `s3_key` TEXT NULL  
- `original_filename` TEXT NULL  
- `file_size` BIGINT NULL  
- `content_type` TEXT NULL  
- `parsed_json` JSON  (minimal metadata: `page_count`, `word_count`, `warnings`, `text_preview` ≤1000 chars, `raw_text_sha256`)  
- `vector_doc_id` TEXT  
- `processing_run_id` FK → ProcessingRun.id (NOT NULL)  
- `is_default` BOOLEAN DEFAULT FALSE NOT NULL  
- `status` TEXT DEFAULT 'processing' NOT NULL  
- `created_at` DATETIME WITH TZ

### Skill ✓
- `id` PK  
- `skill_id` VARCHAR UNIQUE NOT NULL  
- `name` VARCHAR NOT NULL  
- `taxonomy_path` VARCHAR NOT NULL  
- `vector_doc_id` VARCHAR NOT NULL  
- `framework` VARCHAR NOT NULL *(O*NET/ESCO integration)*
- `external_id` VARCHAR NULL *(O*NET element ID, ESCO concept URI, etc.)*
- `meta_json` JSON NULL *(framework-specific metadata)*
- `created_at` TIMESTAMP NULL
- `onet_soc_code` VARCHAR(10) NULL
- `occupation_title` VARCHAR(150) NULL
- `commodity_title` VARCHAR(150) NULL
- `hot_tech` BOOLEAN DEFAULT FALSE NOT NULL
- `in_demand` BOOLEAN DEFAULT FALSE NOT NULL
- `skill_type` VARCHAR(50) DEFAULT 'skill' NULL

### SkillAlias ✓
- `id` PK  
- `skill_id_fk` FK → Skill.id  
- `alias` TEXT
- `meta_json` JSON NULL *(provenance tracking for imported aliases)*

### JobListing ✓
- `id` PK  
- `title` VARCHAR(200) NOT NULL  
- `company` VARCHAR(200) NOT NULL  
- `location` VARCHAR(200) NULL  
- `job_type` VARCHAR(50) NULL  
- `description` TEXT NULL  
- `requirements` TEXT NULL  
- `salary_min` INTEGER NULL  
- `salary_max` INTEGER NULL  
- `salary_currency` VARCHAR(10) NULL  
- `external_url` VARCHAR(500) NULL  
- `external_id` VARCHAR(200) NULL  
- `source` VARCHAR(100) NULL  
- `company_logo_url` VARCHAR(500) NULL  
- `company_website` VARCHAR(200) NULL  
- `required_skills` JSON NULL  
- `preferred_skills` JSON NULL  
- `is_active` BOOLEAN NOT NULL  
- `is_remote` BOOLEAN NOT NULL  
- `date_posted` TIMESTAMP NULL  
- `date_expires` TIMESTAMP NULL  
- `created_at` TIMESTAMP NULL  
- `updated_at` TIMESTAMP NULL  
- `vector_doc_id` VARCHAR(200) NULL

### JobCollection ✓
- `id` PK  
- `user_id` FK → UserProfile.id (TEXT)  
- `job_listing_id` FK → JobListing.id  
- `added_at` DATETIME WITH TZ  
- UNIQUE(`user_id`, `job_listing_id`) name=`uix_user_job_listing`

---

## 1.1) O*NET Integration Schema

### Framework Support
- **Skill.framework**: `'Custom'` | `'ONET'` | `'ESCO'` *(future)*
- **Skill.external_id**: External taxonomy identifier
  - O*NET: Element ID (e.g., `"2.B.1.1"`)
  - ESCO: Concept URI (e.g., `"http://data.europa.eu/esco/skill/..."`)
  - Custom: `NULL`

### O*NET Metadata Structure (Skill.meta_json)
```json
{
  "soc_codes": ["15-1132", "15-1133", "15-1134"],
  "importance": 4.2,
  "level": 3.8,
  "source_url": "https://www.onetcenter.org/database/...",
  "element_type": "skill",
  "description": "Writing computer programs for various purposes",
  "data_updated": "2024-01-01"
}
```

### SkillAlias Provenance (SkillAlias.meta_json)
```json
{
  "source": "ONET",
  "element_id": "2.B.1.1",
  "preferred": true,
  "imported_at": "2024-01-01T00:00:00Z"
}
```

---

## 2) AI Features Implementation (current mode)
In the current skill-only mode, normalized skills are computed at runtime; they are not stored in separate `ResumeSkill`/`JobSkill` tables. Persisted outputs live in `SkillGapReport` JSON fields.

### SkillGapReport ✓
- `id` PK  
- `user_id` FK → User.id  
- `resume_id` FK → Resume.id  
- `job_listing_id` FK → JobListing.id  
- `matched_skills_json` JSON *([{skill_id, evidence, level, confidence}])*  
- `missing_skills_json` JSON *([{skill_id, required_level, rationale}])*  
- `weak_skills_json` JSON NULL  
- `score` REAL *(0–100)*  
- `report_note_id` FK → Note.id NULL  
- `processing_run_id` FK → ProcessingRun.id  
- `created_at` TIMESTAMP

### LearningItem ✓
- `id` PK  
- `skill_id_fk` FK → Skill.id  
- `title` VARCHAR(200)  
- `url` VARCHAR(500)  
- `source` VARCHAR(100) *(Coursera, Docs, MDN, etc.)*  
- `est_time_min` INTEGER NULL  
- `difficulty` VARCHAR(20) NULL *(Beginner/Intermediate/Advanced)*  
- `meta_json` JSON NULL
- `created_at` TIMESTAMP

### ReportLearningItem ✓
- `id` PK  
- `report_id` FK → SkillGapReport.id  
- `learning_item_id` FK → LearningItem.id  
- `reason` TEXT NULL
- `created_at` TIMESTAMP

---

## 3) Relationships (overview)

### Current Implementation (✓)
- **User 1–N** Chat, Note, Task, Goal  
- **User 1–1** Membership, UserSettings  
- **Chat 1–N** ChatMessage  
- **Goal 1–N** Task  
- **Task 1–N** Note *(optional)*  
- **UserProfile 1–N** Resume  
- **UserProfile N–N** JobListing via **JobCollection**  
- **Skill 1–N** SkillAlias  
- **Resume N–1** ProcessingRun

### AI Features Implementation (✓)
- **Resume 1–N** ResumeSkill  
- **JobListing 1–N** JobSkill  
- **Skill 1–N** ResumeSkill, JobSkill, LearningItem  
- **SkillGapReport N–N** LearningItem via **ReportLearningItem**  
- **ProcessingRun** referenced by SkillGapReport  
- **Task.learning_item_id** FK → LearningItem *(integrates with current Task model)*

---

## 4) RAG / Vector Storage (✓ Implemented)
Use **Chroma** collections; only foreign keys/refs are stored in SQL. Vectorization is handled by the Career Engine using OpenAI `text-embedding-3-large` (3072 dims) for O*NET skills only.

- `skills_ontology` — docs built from **Skill** (plus aliases); keyed by `Skill.vector_doc_id` with O*NET integration  
- ~~`resumes`~~ — Not used in current mode  
- ~~`jobs`~~ — Not used in current mode  
- ~~`learning_corpus`~~ — Not used in current mode

**O*NET Skills Database:**
- 35 core O*NET skills with comprehensive metadata
- 32,681 technology examples across all skills
- Full SOC code coverage (~894 SOC codes per skill on average)
- Vector embeddings for semantic search and matching
- Statistical validation with importance/level scores

---

## 5) Suggested Indexes

### Current Implementation (✓)
- `users(username)` UNIQUE  
- `users(email)` UNIQUE  
- `tasks(user_id, done, start_date)`  
- `chat_messages(chat_id, timestamp)`  
- `notes(user_id, created_at)`  
- `user_profiles(email)`  
- `skills(skill_id)` UNIQUE  
- `job_collections(user_id, job_listing_id)` UNIQUE (`uix_user_job_listing`)  
- `resumes(user_id, is_default)`  
- `job_listings(source, created_at)`

### AI Features Implementation (current mode)
- `SkillGapReport(user_id, job_listing_id, resume_id)`  
- `Task.learning_item_id` *(integrates with current Task)*

---

## 6) Minimal DDL (SQL-ish; aligns with current models)

### Current Implementation (✓)
```sql
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  is_premium INTEGER DEFAULT 0 NOT NULL,
  membership_plan TEXT DEFAULT 'free',
  membership_renewal_date DATE,
  email_notifications INTEGER DEFAULT 1
);

CREATE TABLE chats (
  id INTEGER PRIMARY KEY,
  title TEXT,
  timestamp DATETIME,
  user_id INTEGER REFERENCES users(id),
  model TEXT
);

CREATE TABLE chat_messages (
  id INTEGER PRIMARY KEY,
  role TEXT,
  content TEXT NOT NULL,
  timestamp DATETIME,
  chat_id INTEGER REFERENCES chats(id)
);

CREATE TABLE notes (
  id INTEGER PRIMARY KEY,
  task_id INTEGER REFERENCES tasks(id),
  user_id INTEGER REFERENCES users(id) NOT NULL,
  content TEXT,
  created_at DATETIME
);

CREATE TABLE goals (
  id INTEGER PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  created_at DATETIME
);

CREATE TABLE tasks (
  id INTEGER PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) NOT NULL,
  goal_id INTEGER REFERENCES goals(id),
  title TEXT NOT NULL,
  description TEXT,
  start_date DATE,
  end_date DATE,
  done INTEGER DEFAULT 0 NOT NULL,
  priority INTEGER DEFAULT 0,
  created_at DATETIME
);

CREATE TABLE memberships (
  id INTEGER PRIMARY KEY,
  plan TEXT DEFAULT 'free',
  renewal_date DATE,
  user_id INTEGER REFERENCES users(id) UNIQUE
);

CREATE TABLE user_settings (
  id INTEGER PRIMARY KEY,
  language TEXT DEFAULT 'en',
  user_id INTEGER REFERENCES users(id) UNIQUE
);

CREATE TABLE user_profiles (
  id TEXT PRIMARY KEY, -- Auth0 sub
  email TEXT,
  email_verified INTEGER DEFAULT 0,
  name TEXT,
  picture TEXT,
  contact_name TEXT,
  contact_email TEXT,
  contact_phone_number TEXT,
  contact_location TEXT
);

CREATE TABLE processing_runs (
  id INTEGER PRIMARY KEY,
  created_at DATETIME,
  llm_model TEXT,
  embed_model TEXT,
  code_version_hash TEXT,
  params_json TEXT
);

CREATE TABLE resumes (
  id INTEGER PRIMARY KEY,
  user_id TEXT REFERENCES user_profiles(id) NOT NULL,
  file_url TEXT,
  s3_bucket TEXT,
  s3_key TEXT,
  original_filename TEXT,
  file_size BIGINT,
  content_type TEXT,
  parsed_json TEXT,
  vector_doc_id TEXT,
  processing_run_id INTEGER REFERENCES processing_runs(id) NOT NULL,
  is_default INTEGER DEFAULT 0 NOT NULL,
  created_at DATETIME
);

CREATE TABLE skills (
  id INTEGER PRIMARY KEY,
  skill_id TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  taxonomy_path TEXT NOT NULL,
  vector_doc_id TEXT NOT NULL,
  framework TEXT DEFAULT 'Custom',
  external_id TEXT,
  meta_json TEXT,
  created_at DATETIME
);

CREATE TABLE skill_aliases (
  id INTEGER PRIMARY KEY,
  skill_id_fk INTEGER REFERENCES skills(id) NOT NULL,
  alias TEXT NOT NULL,
  meta_json TEXT
);

CREATE TABLE job_listings (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  company TEXT NOT NULL,
  location TEXT,
  job_type TEXT,
  description TEXT,
  requirements TEXT,
  salary_min INTEGER,
  salary_max INTEGER,
  salary_currency TEXT DEFAULT 'USD',
  external_url TEXT,
  external_id TEXT,
  source TEXT,
  company_logo_url TEXT,
  company_website TEXT,
  required_skills TEXT,
  preferred_skills TEXT,
  is_active INTEGER DEFAULT 1 NOT NULL,
  is_remote INTEGER DEFAULT 0 NOT NULL,
  date_posted DATETIME,
  date_expires DATETIME,
  created_at DATETIME,
  updated_at DATETIME,
  vector_doc_id TEXT
);

CREATE TABLE job_collections (
  id INTEGER PRIMARY KEY,
  user_id TEXT REFERENCES user_profiles(id) NOT NULL,
  job_listing_id INTEGER REFERENCES job_listings(id) NOT NULL,
  added_at DATETIME,
  UNIQUE(user_id, job_listing_id)
);
```

### AI Features Implementation (current mode)
```sql
CREATE TABLE skill_gap_reports (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  resume_id INTEGER NOT NULL REFERENCES resumes(id),
  job_listing_id INTEGER NOT NULL REFERENCES job_listings(id),
  matched_skills_json JSON NOT NULL,
  missing_skills_json JSON NOT NULL,
  weak_skills_json JSON,
  score REAL NOT NULL,
  report_note_id INTEGER REFERENCES notes(id),
  processing_run_id INTEGER NOT NULL REFERENCES processing_runs(id),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE learning_items (
  id SERIAL PRIMARY KEY,
  skill_id_fk INTEGER NOT NULL REFERENCES skills(id),
  title VARCHAR(200) NOT NULL,
  url VARCHAR(500) NOT NULL,
  source VARCHAR(100) NOT NULL,
  est_time_min INTEGER,
  difficulty VARCHAR(20),
  meta_json JSON,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE report_learning_items (
  id SERIAL PRIMARY KEY,
  report_id INTEGER NOT NULL REFERENCES skill_gap_reports(id),
  learning_item_id INTEGER NOT NULL REFERENCES learning_items(id),
  reason TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add learning_item_id to existing tasks table
ALTER TABLE tasks ADD COLUMN learning_item_id INTEGER REFERENCES learning_items(id);
```

---

## 7) JSON Shapes (key columns)

### Current Implementation (✓)
```json
// Note.content (current)
"User's note content here"

// Task (current structure)
{ "title": "Task title", "description": "Task description", "start_date": "2024-01-15", "end_date": "2024-01-15" }

// UserProfile (Auth0)
{ "sub": "auth0|abc123", "email": "user@example.com", "email_verified": true, "name": "Jane Doe", "picture": "https://.../avatar.png" }

// Resume.parsed_json (current - minimal metadata)
{
  "page_count": 2,
  "word_count": 1234,
  "warnings": [],
  "text_preview": "First ~1000 characters of extracted text...",
  "raw_text_sha256": "e3b0c44298fc1c149afbf4c8996fb924..."
}

// JobListing.required_skills (array)
["Python", "React", "SQL"]
```

### Planned AI Features (○)
```json
// Resume.parsed_json (minimal metadata)
{
  "page_count": 1,
  "word_count": 456,
  "warnings": ["..."],
  "text_preview": "First ~1000 characters...",
  "raw_text_sha256": "ab12cd34..."
}

// JobListing.requirements_json
{ "requirements": [{ "text": "React, Node", "priority": 1 }] }

// SkillGapReport.matched_skills_json
[{ "skill_id": "fe.react", "evidence": "Built SPA with React 18", "level": "intermediate", "confidence": 0.84 }]

// SkillGapReport.missing_skills_json
[{ "skill_id": "cloud.aws.ec2", "required_level": "basic", "rationale": "Listed in JD, not found in resume" }]
```

---

## 8) Integration Notes & Current Status

### Current Implementation Status
- **User management**: Complete with authentication, membership, settings
- **Task/Goal system**: Functional with calendar integration and notes
- **Chat system**: Working with DeepSeek API integration
- **AI provenance + resume ingest**: Fully implemented (`processing_runs`, `resumes` with S3 fields, default selection)
- **Skills ontology**: Complete implementation with O*NET integration (299 core skills, 32,681 technology examples)
- **Jobs**: Implemented `job_listings` + `job_collections` (save jobs) with external job fetching
- **AI Data Models**: Complete implementation of `ResumeSkill`, `JobSkill`, `SkillGapReport`, `LearningItem`, `ReportLearningItem`
- **Task Integration**: `learning_item_id` field added to Task model for AI integration
- **Database**: SQLAlchemy + Alembic (PostgreSQL/SQLite supported)
- **Vector Database**: ChromaDB with O*NET skills ontology
- **Career Engine**: Complete skill-only analysis pipeline with level-aware gap analysis
- **Frontend Foundation**: Next.js 15 with Auth0, basic components, and API proxy

### Current Architecture
1. **AI models** fully implemented in `models.py` (Resume, JobListing, Skill, etc.)
2. **Task model** extended with `learning_item_id` field for AI-generated learning items
3. **UserProfile/User** models own AI entities (Resume, JobSkill/GapReport)
4. **Note system** ready for AI-generated insights and user annotations
5. **Goal/Task** workflow ready for learning item scheduling

### Implementation Checkpoint: Vector Database & Gap Analyzer
- ✅ **Phase 1 Complete**: AI data models implemented and database tables created
- ✅ **Phase 2 Complete**: Core services implemented (resume ingest, vectorization via Career Engine)
- ✅ **Phase 3 Complete**: Resume upload API endpoint with S3 storage
- ✅ **Phase 4 Complete**: RAG/vector search integrated (ChromaDB with O*NET skills)
- ✅ **Phase 5 Complete**: Career Engine with level-aware gap analysis
- ✅ **Phase 6 Complete**: O*NET integration with comprehensive skills database
- ✅ **Phase 7 Complete**: Frontend foundation with Next.js 15, Auth0, and basic components
- **Phase 8**: Complete AI features UI (gap reports, learning items, export)
- **Phase 9**: Advanced features and optimization
