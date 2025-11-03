# Career Engine Uplift — Detailed Execution Plan v2
*(Chatbot + Jobs + Learning + Caching + CRAG Gate + Optional Planner/Bandit)*

> This plan assumes your current 3‑node LangGraph spine: `get_default_resume → load_job → run_career_engine`. We keep that intact and layer on caching, diagnostics, mapping robustness, job/learning recs, and optional online policy selection. The file is structured so a Cursor agent can execute tasks in phases.

---

## 0) Scope & Goals

- Keep the **existing gap report** flow functionally stable.
- Add a **chatbot** entrypoint with intents: `gap_report`, `recommend_jobs`, `recommend_learning`, `ask_skill_info`, `status_query`, `chitchat`.
- **Reduce LLM calls & latency** by caching both **resume** and **JD** skill+level extraction, with idempotent start + join‑wait.
- Add **request‑scoped policy_overrides**, expose **diagnostics** in responses.
- Add a bounded **CRAG-style mapping gate** (retry‑capped) in the O*NET mapper.
- Add **Jobs That Fit Me** and **Related Learning Items** branches.
- (Optional) Add **planner** (LLM) and **bandit** (shadow) for policy selection.
- Make all additions **flag‑gated**, **reversible**, and **observable**.

---

## 1) Architecture Baseline (unchanged)
- LangGraph: `get_default_resume → load_job → run_career_engine`.
- CareerEngine: `LLMExtractor` → `OnetMapper` → `GapAnalyzer` → report.
- Resume extraction cache exists partially; we formalize + generalize it; add JD cache.

---

## 2) Phases (execution order)

### Phase A — Caching First (Resume & JD) — *High ROI*
**Goal:** Consolidate extraction outputs and eliminate repeat LLM calls.

**A1) Canonical text normalization & hashing**
- Implement `normalize_text(txt)` (lowercase, trim, collapse whitespace; optional boilerplate stripping).
- Compute `text_sha256 = sha256(normalize_text(txt))`.
- Include `extractor_version`, `model_id`, and `prompt_version` in the cache key tuple.

**A2) Table(s)**
- Create `DocumentExtraction` (or `ResumeExtraction` + `JDExtraction` if you prefer separate tables):
  - `id (uuid)`
  - `doc_type` ENUM: `resume` | `jd`
  - `text_sha256` (indexed, unique in combo key)
  - `extractor_version` (string/int)
  - `model_id` (string)
  - `prompt_version` (string/int)
  - `status` ENUM: `ready` | `running` | `failed`
  - `result_json` (skills+levels, diag)
  - `created_at`, `updated_at`
  - **Unique key:** `(doc_type, text_sha256, extractor_version, model_id, prompt_version)`

**A3) Idempotent getters (one place)**
- `get_resume_skills(resume_id|text) -> {status, run_id?, skills, version}`
- `get_jd_skills(job_id|text) -> {status, run_id?, skills, version}`
- Behavior:
  - Lookup by unique key. If **ready**, return immediately.
  - If **running**, perform **join‑wait** (e.g., 2–3 seconds). If still running → return `{status:"generating", run_id}`.
  - If **missing**, `INSERT ... status=running` using `SELECT ... FOR UPDATE SKIP LOCKED` (SQLAlchemy pattern), kick off extraction (background or async task), and return `{status:"generating", run_id}`.
- Emit small diagnostics: `num_skills`, `level_coverage`, `model_id`, `duration_ms`.

**A4) Integration points (no graph rewrite)**
- In your gap report node and any path that needs extraction:
  - Replace direct extractor calls with `get_resume_skills(...)` and `get_jd_skills(...)`.
  - If `{status:"generating"}`, return a `status:"generating", run_id` response from the chat/graph layer; let the checkpointer resume.

**A5) Invalidation**
- Bump `extractor_version` when prompts/models change.
- New text → new `text_sha256` entry.
- No TTL for resumes; optional TTL (14–30 days) for scraped JDs.

**A6) Metrics (dashboards)**
- Cache hit rate (resume, JD), extraction duration, join‑wait average, failure rate, tokens saved per request.

---

### Phase B — Request‑Scoped Overrides & Diagnostics
- Add param: `CareerEngine.analyze_resume_vs_job(..., policy_overrides: dict | None = None)`.
- Implement `CareerEngineConfig.copy()` and `.with_overrides()` (deep copy; nested dict merge).
- Thread `effective_config` to `LLMExtractor`, `OnetMapper`, `GapAnalyzer` constructors.
- Persist `effective_config` + `onet_snapshot` to `ProcessingRun.params_json` (or equivalent).
- Return `mapping_diagnostics` (and extraction diagnostics if available) in `analysis.extras`.

---

### Phase C — CRAG‑Style Mapping Gate (bounded)
- Implement `_filter_hits_with_gate()` around existing `_filter_hits()`:
  - Inputs: diagnostics like `accepted_count`, `top1_minus_top2_margin`, `literal_text_rejected`.
  - Progressive adjustments (each **at most once**) with **max 3 retries** and **`topk ≤ 20`**:
    1. If `accepted_count < floor` → increase `topk` by Δk.
    2. If `margin < threshold` → switch `search_recipe` (e.g., `task_first`) once.
    3. If many literal rejections → nudge floor slightly (tighten/loosen within guard bounds).
- Attach `gate_summary` to diagnostics; ensure deterministic fallback (no infinite loops).

---

### Phase D — Chatbot: “Jobs That Fit Me”
- New chat endpoint `/chat` (returns `{messages, status, action?}`).
- Router: rules → tiny LLM JSON for `{intent, entities}`.
- Entities: `resume_id`, `location`, `seniority`, `domains`, `top_k`.
- Flow:
  1) `get_resume_skills` (may return `generating` → surface progress).
  2) `search_jobs` (hybrid: dense embeddings from resume skills; plus BM25 overlap).
  3) `rank_jobs` (`0.35*overlap + 0.35*cos + 0.2*level_fit + 0.05*recency + 0.05*location`).
  4) `respond_job_matches`: Top‑K with `title/company/url/score`, `why_it_fits` (matched skills), `gaps` (critical misses), refine chips.

---

### Phase E — Chatbot: Related Learning Items
- Add `LearningItem` catalog:
  - `id, provider, title, url, skills[], level, duration_hours, cost, rating, last_updated_at, language, tags[]`
  - Precompute embeddings from `title + desc + skills`.
- Flow:
  1) `get_gaps(resume_id, job_id|target_role)` – reuse cached extractions and gap output.
  2) `search_learning` (hybrid over catalog), filter by prefs (budget, time_per_week, provider).
  3) `rank_learning` (`0.45*skill_match + 0.2*level_alignment + 0.15*quality + 0.1*duration_fit + 0.1*recency`).
  4) `respond_learning_items`: group by gap, include effort & why‑fit; “Build 2‑week plan” action.

---

### Phase F — Optional Planner & Bandit
- **Planner (flag: `ENABLE_PLANNER`)**: small LLM emits ≤4‑step JSON plans using allowed tools; executor enforces schemas/timeouts.
- **Bandit (flag: `ENABLE_BANDIT`)**: in `run_career_engine` node, select overrides → call engine → compute reward (e.g., gap precision or acceptance proxy) → update. Start **shadow‑only**; no behavioral change until promoted.

---

### Phase G — Observability, Flags, Rollout
- **Feature flags**: `ENABLE_CRAG_GATE`, `ENABLE_RECOMMEND_JOBS`, `ENABLE_RECOMMEND_LEARNING`, `ENABLE_PLANNER`, `ENABLE_BANDIT`.
- **Metrics**: intent distribution; cache hit rates; join‑wait durations; extraction/mapper latency; CRAG retries; job CTR; learning CTR; error rates.
- **Logs**: per‑job score components; `gate_summary`; overrides applied; bandit `{obs, act, reward}`.
- **Rollout**: dev → canary (5–10%) → ramp; promote features incrementally.

---

## 3) Database & Migrations

**Tables / Columns**
- `DocumentExtraction` (or split types): see Phase A2.
- (Optional) `JobListing.parsed_json` for JD cache if you prefer a separate field on the jobs table.
- `LearningItem` catalog + vector/BM25 indexes.
- (Optional) `run_log` for bandit shadow logs, else embed in `ProcessingRun.params_json`.

**Migrations**
- Alembic revision for new tables/columns.
- Seed script for initial `LearningItem` catalog (if available).

---

## 4) Endpoints & Graph Wiring

**Endpoints**
- `/chat` → returns `{messages[], status: ok|need_input|generating|error, action?}`.

**Graph (keep original intact)**
- Reuse: `get_default_resume → load_job → run_career_engine` for gap reports.
- New nodes:
  - Shared: `get_resume_skills`, `get_jd_skills`, `get_gaps`.
  - Jobs path: `search_jobs`, `rank_jobs`, `respond_job_matches`.
  - Learning path: `search_learning`, `rank_learning`, `respond_learning_items`.

**Status handling**
- If `get_*_skills` returns `generating`, short‑circuit response with `action: show_progress` and `status:"generating"`; client polls; checkpointer resumes.

---

## 5) Testing & QA

**Unit**
- Config `copy()`/`with_overrides()` deep‑copy & nested override tests.
- Caching: ready/running/missing; join‑wait; key correctness (hash+version+model+prompt).
- Mapper gate: retry cap; deterministic outcomes; latency bounds.
- Rankers: deterministic scores; evidence attachments.

**Integration**
- Warm vs cold caches; concurrent extraction (idempotent lock + join‑wait).
- Chat → jobs; chat → learning; chat → gap_report; planner bypass when entities complete.

**E2E Acceptance**
- Warm cache: “Jobs that fit me” ≤ 1.5s; “Gap report with cached resume+JD” ≤ 2–3s.
- ≥60% reduction in LLM tokens for repeats.

---

## 6) PR Breakdown (Cursor‑friendly)

- **PR‑1**: Caching Foundation
  - Normalizer + hashing
  - `DocumentExtraction` table & DAL
  - `get_resume_skills`, `get_jd_skills` (idempotent + join‑wait)
  - Instrumentation

- **PR‑2**: Overrides & Diagnostics
  - `policy_overrides` plumbed through; persist effective config + `onet_snapshot`
  - Return diagnostics in `analysis.extras`

- **PR‑3**: CRAG Gate
  - `_filter_hits_with_gate()` + bounded retries
  - `gate_summary` diagnostics

- **PR‑4**: Chatbot — Jobs Path
  - `/chat` endpoint + router
  - `search_jobs`, `rank_jobs`, `respond_job_matches`

- **PR‑5**: Learning Items
  - `LearningItem` schema + embeddings/index
  - `get_gaps`, `search_learning`, `rank_learning`, `respond_learning_items`

- **PR‑6 (opt)**: Planner & Bandit (shadow)

---

## 7) Implementation Checklist (copy/paste for Cursor)

- [ ] Add `normalize_text()` + `text_sha256` utility
- [ ] Create `DocumentExtraction` table and DAL
- [ ] Implement `get_resume_skills()` (idempotent + join‑wait)
- [ ] Implement `get_jd_skills()` (idempotent + join‑wait)
- [ ] Replace direct extractor calls with getters in gap & chat flows
- [ ] Add `CareerEngineConfig.copy()` and `.with_overrides()`
- [ ] Accept `policy_overrides` in `analyze_resume_vs_job(...)`
- [ ] Thread `effective_config` to extractor/mapper/analyzer
- [ ] Persist `effective_config` + `onet_snapshot`; return diagnostics
- [ ] Implement `_filter_hits_with_gate()` (bounded retries, cap topk)
- [ ] Add `/chat` endpoint + router (rules → mini‑LLM JSON)
- [ ] Add nodes: `search_jobs`, `rank_jobs`, `respond_job_matches`
- [ ] Add `LearningItem` schema + embeddings/indexes
- [ ] Add nodes: `get_gaps`, `search_learning`, `rank_learning`, `respond_learning_items`
- [ ] Add flags + metrics + logs; create dashboards
- [ ] E2E tests; canary rollout; ramp

---

## 8) Appendix — Example Keys & Payloads

**Cache key tuple**
```text
(doc_type, text_sha256, extractor_version, model_id, prompt_version)
```

**Getter return (ready)**
```json
{
  "status": "ready",
  "version": {"extractor_version": "3", "model_id": "gpt-4o", "prompt_version": "7"},
  "skills": [{"name": "Kubernetes", "level": 3, "evidence": "..."}],
  "diag": {"num_skills": 42, "level_coverage": 0.86, "duration_ms": 812}
}
```

**Getter return (generating)**
```json
{
  "status": "generating",
  "run_id": "run_123e4567"
}
```
