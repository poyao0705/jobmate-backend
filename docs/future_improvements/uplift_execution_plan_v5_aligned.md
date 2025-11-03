# Career Engine Uplift — Execution Plan **v5 (Aligned)**
*(Chatbot + Jobs + Learning + Caching + CRAG Gate + HITL (chat‑only) + Optional Planner/Bandit)*

> This v5 plan incorporates your codebase review. It removes assumptions not present today, aligns naming with existing files/endpoints, and specifies concrete thresholds, state, and integration seams. It keeps your current 3‑node gap flow intact and introduces a **separate chat graph** for interactive features.

---

## 0) What changed vs v4 (delta)
- **Separate graphs**: keep the existing *Standalone GapGraph*; add a new *ChatGraph*. No mixing.
- **Endpoint mapping clarified**: use existing `/gap/run` (standalone) and new `/chat/interactive` (chat graph). Existing `/chat/stream` remains unchanged.
- **HITL policy made channel‑aware**: **off** for `/gap/run`, **auto** only for `/chat/interactive`.
- **Persistence scope trimmed**: keep `SkillAlias` (exists). Defer `UserSkillLevel` & `UserPrefs` to *future work*. Use **session overlays** in chat for now.
- **CRAG gate defined concretely** with thresholds & bounded retries around `OnetMapper._filter_hits()`.
- **Level fallback clarified**: default **L2** when missing; optional *years→level* heuristic provided as a later PR.
- **State & diagnostics**: `GapState` and `extras.hitl` fields specified; `InteractionContext` threaded without refactoring engine into nodes.

---

## 1) Endpoints & Graphs

### 1.1 Endpoints
- **Standalone gap (unchanged)**: `POST /gap/run` and `GET /gap/by-job/<id>`  
  - Runs **GapGraph** (no HITL). Returns the skill gap report.
- **Chat (new endpoint)**: `POST /chat/interactive`  
  - Runs **ChatGraph** (can ask for input). May return `status:"need_input"` payloads.
  - **Note**: Uses a new endpoint to avoid breaking existing `/chat/stream` (which remains unchanged for simple LLM streaming).

### 1.2 Graphs

**Standalone GapGraph (existing, unchanged)**
```
START → get_default_resume → load_job → run_career_engine → END
```

**ChatGraph (new)**
```
START
  → parse_and_route (rules → mini LLM JSON)
    → [ gap_path | jobs_path | learning_path | chitchat ]
        gap_path: ensure_resume → ensure_job → run_career_engine → respond_gap_report
        jobs_path: ensure_resume → search_jobs → rank_jobs → respond_job_matches
        learning_path: ensure_resume → (ensure_job|target_role?) → get_gaps → search_learning → rank_learning → respond_learning [FUTURE WORK]
        chitchat: llm_reply
    → (optional) need_input (HITL) ↩︎ (only when chat)
→ END
```

**Inclusion rule**: `need_input` node is **only** wired in ChatGraph.

---

## 2) State & Context

### 2.1 InteractionContext (threaded everywhere)
```python
@dataclass
class InteractionContext:
    channel: Literal["chat","api","batch"] = "api"
    hitl_mode: Literal["off","auto"] = "off"   # /chat sets "auto"; standalone stays "off"
    session_id: str | None = None
```
- `analyze_resume_vs_job(..., policy_overrides=None, ctx: InteractionContext=InteractionContext())`

### 2.2 GapState (additions; non‑breaking)
```python
class GapState(TypedDict, total=False):
    user_id: str
    job_id: int
    resume_id: Optional[int]
    result: Dict[str, Any]
    analysis: GapAnalysisResult
    error: str
    # additions:
    channel: Literal["chat","api","batch"]
    hitl_mode: Literal["off","auto"]
    session_id: Optional[str]
```
- Default values keep current behavior.

### 2.3 Diagnostics schema (`analysis.extras`)
```json
{
  "mapping": { "...": "existing mapper diagnostics" },
  "hitl": {
    "mode": "off | auto",
    "skipped": true,
    "assumptions": [
      "Filled Python level via default L2 (no years)",
      "Mapped 'k8s' via alias table → Kubernetes"
    ]
  }
}
```

---

## 3) Caching (Phase A — **first**)

### 3.1 Canonical hashing
- `normalize_text(txt) → sha256` (lowercase, trim, collapse whitespace).

### 3.2 Table (new)
- **Create** `DocumentExtraction` table in SQL database to store cached extraction results.

**Table Schema:**
```sql
CREATE TABLE document_extractions (
  id INTEGER PRIMARY KEY,
  
  -- Composite unique key components
  doc_type VARCHAR(20) NOT NULL,           -- 'resume' | 'jd'
  text_sha256 VARCHAR(64) NOT NULL,        -- SHA256 hash of normalized text
  extractor_version VARCHAR(50) NOT NULL,   -- e.g., "v2-langchain-best-practices"
  model_id VARCHAR(100) NOT NULL,          -- e.g., "gpt-4o", "deepseek-chat"
  prompt_version VARCHAR(50) NOT NULL,      -- e.g., "v1.0"
  
  -- Status and result
  status VARCHAR(20) NOT NULL DEFAULT 'running',  -- 'running' | 'ready' | 'failed'
  result_json JSONB,                       -- Cached extraction result
  user_corrections JSONB DEFAULT '{}',     -- User-provided corrections/overrides
  diag JSONB DEFAULT '{}',                 -- Diagnostics metadata
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP,
  
  -- Unique constraint
  UNIQUE(doc_type, text_sha256, extractor_version, model_id, prompt_version)
);

CREATE INDEX idx_doc_extr_lookup ON document_extractions(
  doc_type, text_sha256, extractor_version, model_id, prompt_version
);
CREATE INDEX idx_doc_extr_status ON document_extractions(status) WHERE status = 'running';
```

**Key Design:**
- Unique key: `(doc_type, text_sha256, extractor_version, model_id, prompt_version)`
- Supports concurrent extraction requests via row-level locking (see getter pattern below)

### 3.3 Getters (shared utility, idempotent)
- `get_resume_skills(resume_id|text, ctx)`  
- `get_jd_skills(job_id|text, ctx)`  

**Implementation pattern (idempotent):**

1. **Normalize & hash** input text → `text_sha256`
2. **Construct cache key**: `(doc_type, text_sha256, extractor_version, model_id, prompt_version)`
3. **SELECT with lock**:
   ```sql
   SELECT * FROM document_extractions
   WHERE doc_type = ? AND text_sha256 = ? 
     AND extractor_version = ? AND model_id = ? AND prompt_version = ?
   FOR UPDATE SKIP LOCKED;
   ```
4. **Branch on result:**
   - **If row found with `status='ready'`** → return cached `result_json` immediately
   - **If row found with `status='running'`** → 
     - Short join-wait (2–3 seconds)
     - Re-query; if still `running` → return `{status:"generating", run_id}` to caller
     - If now `ready` → return cached `result_json`
   - **If no row found** → 
     - INSERT row with `status='running'` (unique constraint prevents race)
     - If insert succeeds → kick off extraction async, return `{status:"generating", run_id}`
     - If insert fails (race condition) → another process already started; re-query and follow `running` path

**Note:** `SKIP LOCKED` ensures concurrent requests don't block; first caller sets status, others wait or join-wait.

### 3.4 Integration
- Replace raw extractor calls in:
  - `run_career_engine` (Standalone & Chat) → use getters.
  - `ensure_resume`, `ensure_job` nodes in ChatGraph.

### 3.5 Invalidation
- New text hash or bumped `extractor_version/model_id/prompt_version` → new row.

---

## 4) Request‑Scoped Overrides & Diagnostics (Phase B)
- `CareerEngine.analyze_resume_vs_job(..., policy_overrides=None, ctx)`
- `config.copy().with_overrides(...)` and persist **effective** config + `onet_snapshot` to `ProcessingRun.params_json`.
- Return `mapping_diagnostics` in `analysis.extras.mapping` (surface only).

---

## 5) CRAG‑style Gate for Mapping (Phase C)

**Goal:** When `OnetMapper._filter_hits()` yields low confidence, perform bounded, deterministic adjustments before accepting or giving up.

### 5.1 Signals
- `accepted_count` (hits after guard)
- `top1_minus_top2_margin` (score gap)
- `literal_reject_rate` (#literal_rejected / #candidates)

### 5.2 Thresholds (config)
```yaml
crag:
  min_hits: 2
  min_margin: 0.08      # 8% normalized gap
  max_retries: 3
  max_topk: 20
  bump_topk_by: 4
  allow_recipe_switch: true   # e.g., try "task_first" once
```
### 5.3 Policy (bounded retries)
1) If `accepted_count < min_hits` → increase `topk += bump_topk_by` (cap `max_topk`).
2) If `margin < min_margin` and `allow_recipe_switch` → switch recipe once.
3) If `literal_reject_rate` high → tighten/loosen floor by small epsilon.

Attach `gate_summary` into diagnostics. If still low after retries:
- **ChatGraph (hitl=auto)** → emit HITL with 2–3 candidates.
- **GapGraph (hitl=off)** → accept conservative best (top‑1 if margin ≥ floor) or mark unmapped; add `hitl.skipped=true`.

---

## 6) Level fallback (Phase B/C; minimal)
- When candidate level missing in **standalone** (hitl=off): set **default L2** (configurable).  
- Optional later PR: heuristic `years→level` mapper (regex `(\d+)\s*(?:years|yrs)` → bins `<1y=1, 1–3y=2, 3–5y=3, 5+=4`).

---

## 7) ChatGraph: paths (Phases D & E)

### 7.1 Router
- Rules first (keywords); fallback mini‑LLM emits `{intent, entities}`.

### 7.2 Gap path (chat-triggered compare)
```
ensure_resume (getter) → ensure_job (getter) → run_career_engine(ctx.hitl=auto?) → respond_gap_report
```
- Even in chat, **engine** still runs with `ctx.hitl_mode="off"` to keep the same analysis; only pre/post steps may HITL for missing inputs.

### 7.3 Jobs path (“What jobs fit me?”)
- `ensure_resume` → `search_jobs` (hybrid dense + BM25) → `rank_jobs` (overlap, cosine, level_fit, recency, location) → `respond_job_matches`.
- **Preferences**: keep **session‑local** (in ChatGraph state) for now; no DB `UserPrefs` yet.

### 7.4 Learning path (“Close my gaps”) — **FUTURE WORK**
- `ensure_resume` → (optional `ensure_job|target_role`) → `get_gaps` → `search_learning` → `rank_learning` → `respond_learning_items`.
- Constraints (budget/time/goal) stored **in session state** (no DB yet).
- **Note**: Requires learning catalog implementation, indexing, and ranking logic. Deferred to future phases.

### 7.5 HITL in ChatGraph only
- Invoked from `ensure_resume` (alias confirm), mapping fallback, and preference gathering.
- **Note**: Learning path HITL deferred with learning path (future work).
- Serialized as:
```json
{
  "status": "need_input",
  "action": "ask_user",
  "payload": { "question": "...", "options": ["A","B","C"], "question_id": "..." }
}
```
- On reply, ChatGraph resumes at the originating node (requires **LangGraph checkpointing**).

**Checkpointing Configuration (required for PR-6):**
- LangGraph memory store must be configured to persist graph state between turns.
- Options: in-memory (dev), SQL-backed (production), or Redis (high-scale).
- State includes: user_id, session_id, current node, pending HITL question_id, partial results.
- Configuration to be added in PR-4 setup before HITL implementation.

---

## 8) Models & Migrations (min scope for v5)
- **Keep** existing `SkillAlias` table for alias confirmations (global or user‑scoped if supported).  
- **Defer** new DB entities `UserSkillLevel`, `UserPrefs` to future. Use **session state overlays** in ChatGraph for now.
- **Create** `DocumentExtraction` table (see §3.2 for full schema) with columns:
  - `doc_type`, `text_sha256`, `extractor_version`, `model_id`, `prompt_version` (unique key)
  - `status`, `result_json`, `user_corrections JSONB`, `diag JSONB`
  - Timestamps: `created_at`, `updated_at`, `completed_at`

---

## 9) Config & Thresholds (defaults)
```yaml
hitl:
  extractor: { high: 0.85, low: 0.60 }
  mapper:    { high: 0.80, low: 0.55 }
  ranking:   { high: 0.75, low: 0.50 }
  learning:  { high: 0.75, low: 0.50 }

crag:
  min_hits: 2
  min_margin: 0.08
  max_retries: 3
  max_topk: 20
  bump_topk_by: 4
  allow_recipe_switch: true
```
- In v5, **only ChatGraph** may act on `hitl` thresholds (ask user). GapGraph logs assumptions only.

---

## 10) Testing Strategy (CI‑friendly)

**Unit**
- Getters: ready/running/missing; join‑wait; correct cache keys; overlay merge.  
- CRAG gate: retries capped; deterministic outputs; diagnostics include `gate_summary`.  
- Level fallback: default L2 applied; assumptions logged.

**Integration**
- `/gap/run`: never emits `need_input`; `extras.hitl.skipped=true`.  
- `/chat/interactive`: returns `need_input` when thresholds cross; resumes on simulated reply (requires checkpointing).

**E2E (fixtures)**
- Compare pre‑v5 and v5 outputs for gap report with `ctx.hitl=off` — outputs within tolerance.  
- Latency improvements on repeat runs due to caching.

---

## 11) Rollout

1) **Phase A**: ship caching + getters; no behavior change.  
2) **Phase B**: request‑scoped overrides + diagnostics surfacing.  
3) **Phase C**: CRAG gate (bounded) — with conservative fallback; **no HITL** yet.  
4) **Phase D**: ChatGraph (router + jobs path + checkpointing setup) — enable in small canary.  
5) **Phase E**: Learning path — **DEFERRED** (future work).  
6) **Phase F**: HITL in chat only; collect metrics.  
7) **Phase G (opt)**: planner/bandit shadow.

---

## 12) PR Breakdown (aligned to files)

- **PR‑1 (Caching)**  
  - `migrations/versions/xxx_create_document_extraction_table.py` (new table schema)  
  - `models.py` (DocumentExtraction model class)  
  - `services/extraction_getters.py` (get_resume_skills/get_jd_skills with SELECT FOR UPDATE SKIP LOCKED pattern)  
  - Wire callers in `gap_agent.py` and `career_engine.py`

- **PR‑2 (Overrides & Diag)**  
  - `config.py`: `copy()/with_overrides()`  
  - `career_engine.py`: `policy_overrides`, persist effective config + `onet_snapshot`, return diagnostics  
  - `schemas.py`: `analysis.extras` typing

- **PR‑3 (CRAG Gate)**  
  - `onet_mapper.py`: `_filter_hits_with_gate()` around `_filter_hits()`, bounded retries, `gate_summary`  
  - `config.py`: `crag` defaults

- **PR‑4 (ChatGraph + Jobs + Checkpointing Setup)**  
  - `chat/graph.py`: ChatGraph, state, router, nodes; `need_input` node wired here only  
  - `chat/endpoints.py`: bind new `/chat/interactive` endpoint to ChatGraph runner  
  - `chat/checkpointing.py`: configure LangGraph memory store (SQL-backed or Redis for production)  
  - **Note**: Learning path deferred to future work (see §7.4)

- **PR‑5 (Learning)** — **DEFERRED TO FUTURE WORK**  
  - `learning/models.py` (catalog) & indexers (if applicable)  
  - `chat/nodes_learning.py`: `get_gaps/search_learning/rank_learning/respond_learning`  
  - **Note**: Learning path requires catalog implementation and is not in v5 scope.

- **PR‑6 (HITL in chat)**  
  - `chat/nodes_shared.py`: HITL triggers (alias confirm, prefs)  
  - `schemas.py`: add `need_input` payload schema

- **PR‑7 (opt Planner/Bandit)**  
  - Planner LLM + executor; bandit shadow hook in `gap_agent.run_career_engine`

---

## 13) Minimal Frontend Contract (chat only)
```json
// need_input
{
  "status": "need_input",
  "action": "ask_user",
  "payload": {
    "question": "When you wrote 'k8s', did you mean Kubernetes?",
    "options": ["Yes, Kubernetes","No","Something else…"],
    "question_id": "q_abc123"
  }
}
```
- Reply shape:
```json
{ "question_id":"q_abc123", "answer":"Yes, Kubernetes" }
```

---

## 14) Open Questions resolved
- **Chat integration:** separate ChatGraph; new `/chat/interactive` endpoint (existing `/chat/stream` remains unchanged).  
- **Graph mismatch:** clarified both graphs and node wiring.  
- **Persistence gaps:** only `SkillAlias` + `DocumentExtraction` table (new) for caching; `UserSkillLevel/UserPrefs` deferred.  
- **CRAG definition:** concrete thresholds + bounded policy around `_filter_hits()`.  
- **Level estimator:** default L2; optional heuristic later.  
- **Sync vs graph:** engine remains synchronous; `ctx` threaded; nodes wrap function calls.  
- **Endpoint naming:** use `/gap/run` (standalone) and `/chat/interactive` (new chat graph).  
- **DocumentExtraction:** new table schema specified with composite unique key and row-locking pattern.  
- **Checkpointing:** LangGraph memory store configuration required before HITL implementation (PR-4 setup).  
- **Learning path:** deferred to future work; not in v5 scope.

---
