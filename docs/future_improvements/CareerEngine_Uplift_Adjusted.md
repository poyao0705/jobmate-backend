# Adjusted Uplift Plan — Tailored to Current Agent & Career Engine

> This plan aligns with the actual codepaths and models found in your repo (LangGraph `gap_agent`, `CareerEngine`, `LLMExtractor`, `OnetMapper`, `GapAnalyzer`, `ReportRenderer`). It preserves the deterministic core and introduces CRAG-style gating, request‑scoped overrides, GraphRAG sidecar, and contextual bandits — with minimal, surgical changes.

**Status**: ✅ Reviewed and corrected based on comprehensive codebase analysis.

---

## A) What Already Exists (Confirmed in Code)

- **LangGraph agent** drives a 3‑node flow (`get_default_resume → load_job → run_career_engine`) and returns both a legacy `result` dict and a structured `GapAnalysisResult` (versioned Pydantic schema). It initializes an LLM with retry and falls back to test mode when needed.
- **CareerEngine** orchestrates: Extract (levels) → Map to O*NET (quantile/static, floors) → Analyze → Render → Persist (`SkillGapReport`). Resume text comes from `Resume.parsed_json`.
- **Extraction modes**: `all_in_one` (recommended) and `current` (legacy). Resume extraction is cached inside `parsed_json` using key `extracted_json_with_levels` (not just `extracted_json`).
- **Mapping**: `OnetMapper` uses **quantile strategy** with source‑specific floors and a **literal‑text guard**; exposes rich **diagnostics** (including `skill_diagnostics`, `task_diagnostics`, `literal_text_rejected`, `top_scores`) and a `get_strategy_params()` for persistence.
- **GapAnalyzer** computes coverage‑based score (penalty wiring in progress), classifies **missing/underqualified**, yields **GapAnalyzerOutput** dataclass with `.as_analysis()` (returns `GapAnalysisResult` Pydantic model) and `.legacy_payload()` methods.
- **Persistence**: `SkillGapReport` & `SkillGapStatus`; configuration persisted to `ProcessingRun.params_json` **post-mapping** via `_persist_strategy_config()` method.

---

## B) Changes We’ll Make (Minimal & Composable)

1) **Request‑Scoped Policy Overrides (NEW, tiny hook)**
- Add optional `policy_overrides: dict` to `CareerEngine.analyze_resume_vs_job(...)`. Merge into a local `cfg` copy for that run (no global mutation).
- Why: lets the agent/bandit pick `{q, floor, topk, lexical_guard, search_recipe, extractor_mode}` per request **without** changing env vars.
- Persist **effective config** to `ProcessingRun.params_json` (already supported) and include mapping diagnostics in the returned payload for offline eval.

2) **CRAG‑style Confidence Gate inside OnetMapper (NO schema change)**
- Compute confidence features already available in diagnostics (top‑1/2 margin, p90, accepted/dropped counts, guard pass‑rate, hit_count).
- Apply a **progressive trigger table**: raise `topk` → switch `search_recipe=task_first` → tighten/loosen floor based on sparsity → acronym/alias expansion → (rare) LLM disambiguation.
- Expose `gate_summary` in diagnostics; keep deterministic & auditable.

3) **Contextual Bandit (Agentic RL v1)**
- Observations = extractor stats + mapper diagnostics + gap summary + tokens/time.
- Actions = `{q, floor, topk, lexical_guard ∈ {0,1}, search_recipe ∈ {'default','task_first'}, clarify ∈ {0,1}}`.
- Reward (proxy) = `+precision_guard +coverage -hot_missing_rate -max(0, mean_level_gap - grace) -normalized_cost`.
- Run **shadow** first; promote once canary metrics beat baseline. Log to a lightweight `run_log` (optional table) or reuse your existing logging.

4) **Clarify‑or‑Proceed Micro‑Policy**
- Trigger on low margin/low p90/stack ambiguity (Angular vs React).
- Actions: `{ask_user, stricter_guard, switch_recipe, bump_topk}` with small latency penalty in reward.

5) **GraphRAG Sidecar (“RoleGraph”)**
- Standalone tool for **role recommendations** & **learning paths** (does **not** change core scoring).
- Inputs = cached mapped resume skills/levels.
- Retrieval = Personalized PageRank over a small role↔skill graph (+ optional text rerank).
- Output = {role, score, matched/missing, shortest paths for missing, suggested courses, explanation blurb}.
- Wire into: chat (intent = roles/paths) and optional report section (“Suggested roles” / “Learning path”).

6) **Consistency Fix (tiny) - CORRECTED**
- `config.extraction.mode` currently defaults to `"all_in_one"` in config.py (line 89). This is correct; no fix needed. CareerEngine properly uses this default when initializing `_extractor_mode`.

---

## C) Concrete Tasks & Diffs

### C.1 CareerEngine: request‑scoped overrides & richer diagnostics - **IMPLEMENTATION DETAILS ADDED**
- **Add param** `policy_overrides: Optional[Dict[str, Any]] = None` to `analyze_resume_vs_job()` method signature (line 28).
- **CRITICAL**: Implement `CareerEngineConfig.copy()` and `.with_overrides(overrides)` methods in `config.py`. These don't exist yet.
- **At start of analyze**: Create effective config: `effective_config = config.copy().with_overrides(policy_overrides)` 
- **Reinitialize components**: Thread `effective_config` through to `LLMExtractor(self.llm, config=effective_config)`, `OnetMapper(self.chroma, config=effective_config)`, `GapAnalyzer(self.llm, config=effective_config)` initializations. **CRITICAL**: These components must accept optional `config` param with backward-compatible defaults (e.g., `config=None` → use global config) to avoid breaking existing calls.
- **Before mapping**: Log effective thresholds: `floor`, `quantile`, `lexical_guard` (already done at line 499-503).
- **After mapping**: Attach `mapper.get_last_mapping_diagnostics()` to result payload (already calls this at line 243, but needs to be in returned payload).
- **Persist** effective config to `ProcessingRun.params_json` via `_persist_strategy_config()` method (line 621-650). Currently persists post-mapping.

### C.2 OnetMapper: confidence gate (feature only) - **IMPLEMENTATION DETAILS ADDED**
- Keep strategies as‑is in `_filter_hits()` method (line 178).
- Insert gate logic: Create `_filter_hits_with_gate()` wrapper around existing `_filter_hits()`.
- Progressive trigger table inside `map_tokens()` loop (lines 66-122):
  1. Initial search with `k=topk` (line 67)
  2. Apply `_filter_hits()` to get diagnostics
  3. Check gate conditions: `hit_count < H1` → increase `topk`; `margin < M1` → switch recipe; etc.
  4. Re-query ChromaDB if topk increased (bounded to max 3 retries, cap `topk` at 20)
- Return action from gate: `{"gate_action": "accept|increase_topk|switch_recipe|tighten_floor|...", "topk_increased": N}`
- Expose `gate_summary` in diagnostics: aggregate all gate actions across tokens.

### C.3 Bandit runner (service or job) - **INTEGRATION DETAILS ADDED**
- Create new module: `jobmate_agent/services/bandit/` with:
  - `__init__.py` - exports
  - `policy.py` - ε‑greedy or LinUCB selection
  - `rewards.py` - reward computation from diagnostics
  - `observations.py` - feature extraction from CareerEngine result
- **Integration point**: Modify `gap_agent.py` `run_career_engine()` node (line 74):
  - Check `os.getenv("ENABLE_BANDIT", "0") == "1"`
  - Extract observations: `obs = extract_observations(state)` from diagnostics
  - Get policy: `policy_overrides = get_policy_overrides(obs)`
  - Pass to engine: `engine.analyze_resume_vs_job(..., policy_overrides=policy_overrides)`
  - Compute reward: `reward = compute_reward(result)`
  - Update bandit: `update_bandit(obs, policy_overrides, reward)`
- Record `{obs, act, reward, diagnostics}` to `ProcessingRun.params_json` under key `bandit_run` or create optional `run_log` table for shadow mode.

### C.4 RoleGraph sidecar - **NO CHANGES NEEDED**
- Offline builder script to ingest skills/roles/edges (snapshot monthly).
- Serve `role_graph_suggest(resume_id, target_role?, k=5)` as an internal tool.
- Add a report section behind a flag; add chat router rule for role/learning intents.

---

## D) Data, Caching & Invalidation - **ARCHITECTURAL DECISION ADDED**

- **Resume extraction cache** already exists via `Resume.parsed_json` using key `extracted_json_with_levels` (not `extracted_json`). Cache validation based on `extractor_version` field.
- **JD extraction cache**: Currently **NO JD cache exists**. Every comparison re-extracts job skills. **Recommendation**: Add `parsed_json` column to `JobListing` (or separate `JOB_EXTRACT_CACHE` table keyed by `job_id, text_sha256, extractor_mode, extractor_version`) to cache JD extraction results.
- **Mapping cache**: Currently **NO mapping cache exists**. Every request recomputes O*NET mapping via ChromaDB vector search (~200-500ms per job).
- **Snapshot reproducibility**: Persist `onet_snapshot` (e.g., "2025-10") with each `ProcessingRun` and surface in `analysis_json.meta` for reproducibility tracking.
  
**Decision Required**: Choose caching strategy:

**Option 1: No Cache (Recommendation for MVP)**
- ✅ Simplest implementation, no invalidation complexity
- ✅ Always uses latest thresholds for bandit tuning
- ❌ Repeated ChromaDB queries add latency
- ❌ Cannot replay A/B tests without re-extraction

**Option 2: Baseline Cache**
- ✅ Fast cache hits for repeat analyses
- ✅ Supports A/B testing (baseline vs bandit policy)
- ⚠️ Adds complexity: cache invalidation, versioning
- Suggested: Add `baseline_mapping_cache_id` FK to `SkillGapReport`

**Recommendation**: Start with **Option 1** (no cache) for Phase 1-3. Add baseline cache in Phase 4 after proving bandit value.

---

## E) Evaluation & Guardrails

- Canary metrics: lexical precision (guard pass‑rate), coverage, hot‑miss rate, mean level gap vs grace, valid‑JSON rate, tokens/time.
- Shadow deploy for bandit; promote when all canaries improve at ≤5% cost delta.
- Hard floors: never ship when guard precision drops below the current baseline; rollback on invalid JSON spikes.

---

## F) Environment & Config Keys (aligned to repo) - **COMPLETE INVENTORY**

```
# Extraction
EXTRACTOR_MODEL=gpt-4o-mini
EXTRACTOR_MODE=all_in_one|current
PARSE_NICE_TO_HAVE=1
CAP_NICE_TO_HAVE=1
SKILL_EXTRACTOR_TEST=0
STRICT_JSON=1
MAX_SPANS_PER_SKILL=2

# Mapping (O*NET)
ONET_MATCH_STRATEGY=quantile|static
ONET_TOPK=10
ONET_JD_Q=0.85
ONET_RESUME_Q=0.85
ONET_TASK_Q=0.85
ONET_JD_FLOOR=0.40
ONET_RESUME_FLOOR=0.30
ONET_TASK_FLOOR=0.40
ONET_LEXICAL_GUARD=1

# Legacy Mapping (backward compatibility)
ONET_MIN_SCORE=0.50
ONET_MARGIN=0.15
ONET_MATCH_THRESHOLD=0.55

# Scoring (Gap Engine)
GE_MISS_W=0.20
GE_HOT_W=0.70
GE_IN_W=0.40
GE_LEVEL_W=0.90
GE_LEVEL_GRACE=0.25

# Bandit (future)
ENABLE_BANDIT=0
```

---

## G) Acceptance Criteria - **ENHANCED**

**Core Functionality**:
- ✅ Overrides applied per request, persisted to ProcessingRun; diagnostics attached.
- ✅ Cache hit rate: Resume extraction cache ≥95% on repeat analyses (no LLM calls).
- ✅ Extraction consistency: Same resume → same skills 95% of the time (within same version).
- ✅ Mapping stability: Quantile cutoff variance <10% for same job content.

**CRAG Gate Performance**:
- ✅ CRAG gate reduces guard‑failed mappings ≥30% at same or better coverage.

**Bandit Performance**:
- ✅ Bandit improves coverage@precision or reduces hot‑miss rate in A/B with ≤5% cost overhead.
- ✅ Shadow mode logs all decisions without affecting user experience.

**GraphRAG Sidecar**:
- ✅ GraphRAG returns <400ms P95 for top‑5 roles (with snapshot & precomputed PPR).

---

## H) Implementation Phases & Critical Path

### Phase 0: Foundation (Day 1-2) ⚠️ **BLOCKER**
- **Must Do First**: Implement `CareerEngineConfig.copy()` and `.with_overrides()` in `config.py`
- Add `from dataclasses import replace` for deep copying
- Test config copy/override isolation (no global mutation)

### Phase 1: Request-Scoped Overrides (Day 2-5)
- Modify `CareerEngine.__init__()` to accept `config` parameter
- Add `policy_overrides` param to `analyze_resume_vs_job()` signature
- Thread effective config through to `OnetMapper`, `LLMExtractor`, `GapAnalyzer` (with backward-compatible defaults)
- Update `_persist_strategy_config()` to capture effective config and `onet_snapshot`
- Persist `onet_snapshot` to `ProcessingRun.params_json` and surface in `analysis_json.meta`
- Return mapping diagnostics in result payload
- Implement version-aware Pydantic serialization (use `.dict()` for v1, `.model_dump()` for v2)

### Phase 2: CRAG Gate (Day 5-10)
- Implement `_filter_hits_with_gate()` in `OnetMapper`
- Add progressive trigger table with bounded retry loop (max 3, cap topk=20)
- Expose `gate_summary` in diagnostics
- Test with real JDs (ensure no infinite loops)

### Phase 3: Bandit Integration (Day 10-17)
- Create `services/bandit/` module structure
- Implement ε‑greedy policy in `policy.py`
- Add `extract_observations()` and `compute_reward()` helpers
- Integrate into `gap_agent.py` `run_career_engine()` node
- Add shadow mode logging to `ProcessingRun.params_json`

### Phase 4: Shadow Deploy & Evaluation (Ongoing)
- Run bandit in shadow mode (log decisions only)
- Collect 100+ analyses with baseline vs. bandit configs
- Compare canary metrics (coverage, precision, hot-miss rate)
- Promote if guardrails pass, iterate if not

### Phase 5: GraphRAG Sidecar (Day 17-30, Optional)
- Build offline graph construction pipeline
- Implement PPR and hybrid reranking
- Create `role_graph_suggest()` tool
- Integrate into chat router and optional report section

---

## I) Critical Implementation Details

### Config Copy Mechanism
```python
# In config.py
from dataclasses import replace
from typing import Dict, Any

class CareerEngineConfig:
    def copy(self) -> 'CareerEngineConfig':
        """Deep copy the configuration."""
        return replace(
            self,
            match_strategy=replace(self.match_strategy),
            score_weights=replace(self.score_weights),
            extraction=replace(self.extraction),
        )
    
    def with_overrides(self, overrides: Dict[str, Any]) -> 'CareerEngineConfig':
        """Apply policy overrides and return new config."""
        # Handle nested overrides like {"match_strategy": {"q": 0.90}}
        # Update appropriate sub-config objects
        pass
```

### Component Initialization Pattern
```python
# In llm_extractor.py, onet_mapper.py, gap_analyzer.py
# CRITICAL: Accept optional config param with backward-compatible defaults
class LLMExtractor:
    def __init__(self, llm, config: CareerEngineConfig = None):
        self.config = config or global_config  # backward-compatible default
        # ... rest of init

# In career_engine.py __init__
def __init__(self, onet_chroma, llm, config: CareerEngineConfig = None):
    cfg = config or global_config
    self.extractor = LLMExtractor(llm, config=cfg)
    self.mapper = OnetMapper(onet_chroma, config=cfg)
    self.analyzer = GapAnalyzer(llm, config=cfg)
```

### Bandit Integration Hook
```python
# In gap_agent.py run_career_engine()
def run_career_engine(state: GapState) -> GapState:
    # NEW: Bandit integration
    policy_overrides = None
    if os.getenv("ENABLE_BANDIT", "0") == "1":
        from services.bandit import get_policy_overrides, compute_reward, update_bandit
        obs = extract_observations(state)
        policy_overrides = get_policy_overrides(obs)
    
    # Pass to engine
    result = engine.analyze_resume_vs_job(
        resume_id=resume_id,
        job_id=job_id,
        policy_overrides=policy_overrides  # NEW
    )
    
    # Update bandit
    if policy_overrides:
        reward = compute_reward(result)
        update_bandit(obs, policy_overrides, reward)
```

---

## J) Summary of Changes Required

| Component | Changes | Priority | Effort | Status |
|-----------|---------|----------|--------|--------|
| `config.py` | Add `copy()`, `with_overrides()` | **CRITICAL** | 4 hours | ⏳ Not Started |
| `career_engine.py` | Add `policy_overrides` param, thread config, persist `onet_snapshot` | **HIGH** | 8 hours | ⏳ Not Started |
| `onet_mapper.py` | Add CRAG gate logic, bounded retries | **HIGH** | 12 hours | ⏳ Not Started |
| `llm_extractor.py` | Accept `config` param in `__init__` (backward-compatible) | Medium | 1 hour | ⏳ Not Started |
| `gap_analyzer.py` | Accept `config` param in `__init__` (backward-compatible) | Medium | 1 hour | ⏳ Not Started |
| `models.py` | Add `JobListing.parsed_json` for JD cache (optional) | Low | 2 hours | ⏳ Not Started |
| `schemas.py` | Version-aware Pydantic serialization (v1 vs v2) | Medium | 1 hour | ⏳ Not Started |
| `services/bandit/` | New module (policy, rewards, observations) | **HIGH** | 16 hours | ⏳ Not Started |
| `gap_agent.py` | Integrate bandit in run_career_engine node | **HIGH** | 4 hours | ⏳ Not Started |
| `services/role_graph/` | GraphRAG sidecar (optional Phase 5) | Low | 40 hours | ⏳ Not Started |

**Total Effort**: ~52 hours (6-7 working days) excluding GraphRAG and optional JD cache

**Risk Assessment**: Medium
- Config override mechanism is well-understood
- CRAG gate needs careful testing to avoid infinite loops
- Bandit requires domain expertise in RL (start with simple ε‑greedy)

---
