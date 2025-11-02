from __future__ import annotations

from typing import TypedDict, Optional, Dict, Any
import logging
from langgraph.graph import StateGraph, START, END
from jobmate_agent.models import Resume, JobListing
from jobmate_agent.services.career_engine import get_career_engine
from jobmate_agent.services.career_engine.config import config
from jobmate_agent.services.career_engine.schemas import GapAnalysisResult
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class GapState(TypedDict, total=False):
    user_id: str
    job_id: int
    resume_id: Optional[int]
    result: Dict[str, Any]
    analysis: GapAnalysisResult
    error: str


def get_default_resume(state: GapState) -> GapState:
    user_id = state.get("user_id")
    if not user_id:
        logger.warning("[GAP] get_default_resume: missing user_id in state")
        return {"error": "Missing user_id"}
    res = Resume.get_default_resume(user_id)
    if not res:
        logger.warning(
            f"[GAP] get_default_resume: no default resume for user_id={user_id}"
        )
        return {"error": "No default resume"}
    logger.info(
        f"[GAP] get_default_resume: resolved resume_id={res.id} for user_id={user_id}"
    )
    return {"resume_id": res.id}


def load_job(state: GapState) -> GapState:
    job_id = state.get("job_id")
    if job_id is None:
        logger.warning("[GAP] load_job: missing job_id in state")
        return {"error": "Missing job_id"}
    job = JobListing.query.get(job_id)
    if not job:
        logger.warning(f"[GAP] load_job: job_id={job_id} not found")
        return {"error": "Job not found"}

    description = job.description or ""
    requirements = job.requirements or ""
    combined_preview = (description + "\n\n" + requirements).strip()
    if combined_preview:
        combined_preview = combined_preview.replace("\n", " ")
        if len(combined_preview) > 200:
            combined_preview = combined_preview[:200] + "..."

    logger.info(
        "[GAP] load_job: job_id=%s title=%s company=%s desc_len=%s req_len=%s",
        job_id,
        (job.title or "").strip() or None,
        (job.company or "").strip() or None,
        len(description),
        len(requirements),
    )
    if combined_preview:
        logger.info(
            "[GAP] load_job: job_id=%s text_preview='%s'", job_id, combined_preview
        )
    return {}


def run_career_engine(state: GapState) -> GapState:
    if state.get("error"):
        logger.info(
            f"[GAP] run_career_engine: skipping due to prior error={state.get('error')}"
        )
        return {}
    resume_id = state.get("resume_id")
    job_id = state.get("job_id")
    if not resume_id or job_id is None:
        logger.warning(
            f"[GAP] run_career_engine: missing ids resume_id={resume_id}, job_id={job_id}"
        )
        return {"error": "Missing resume_id or job_id"}
    logger.info(
        f"[GAP] run_career_engine: invoking CareerEngine for resume_id={resume_id}, job_id={job_id}"
    )
    llm_client = None
    try:
        # Initialize real LLM if available; falls back to extractor's internal handling
        llm_client = ChatOpenAI(
            model=config.extraction.extractor_model,
            max_retries=3,
            temperature=0,
            model_kwargs={"response_format": {"type": "json_object"}},
        )
    except Exception:
        logger.warning(
            "[GAP] run_career_engine: ChatOpenAI init failed; falling back to extractor default"
        )
        llm_client = None
    engine = get_career_engine(use_real_llm=llm_client is not None, llm=llm_client)
    result = engine.analyze_resume_vs_job(resume_id=resume_id, job_id=job_id)
    analysis_payload = result.get("analysis")
    analysis_obj: GapAnalysisResult | None = None
    if isinstance(analysis_payload, dict):
        try:
            analysis_obj = GapAnalysisResult(**analysis_payload)
        except Exception:
            logger.exception(
                "[GAP] run_career_engine: failed to hydrate GapAnalysisResult from payload"
            )
    metrics_score = (
        analysis_obj.metrics.overall_score
        if analysis_obj
        else result.get("overall_match")
    )
    logger.info(
        f"[GAP] run_career_engine: analysis finished overall_match={metrics_score} analysis_id={result.get('analysis_id')}"
    )
    state_update: GapState = {"result": result}
    if analysis_obj:
        state_update["analysis"] = analysis_obj
    return state_update


def run_gap_agent(user_id: str, job_id: int) -> Dict[str, Any]:
    logger.info(f"[GAP] run_gap_agent: start user_id={user_id}, job_id={job_id}")
    builder = StateGraph(GapState)
    builder.add_node(get_default_resume)
    builder.add_node(load_job)
    builder.add_node(run_career_engine)
    builder.add_edge(START, "get_default_resume")
    builder.add_edge("get_default_resume", "load_job")
    builder.add_edge("load_job", "run_career_engine")
    builder.add_edge("run_career_engine", END)
    graph = builder.compile()
    out: GapState = graph.invoke({"user_id": user_id, "job_id": job_id})  # type: ignore
    analysis_obj = out.get("analysis")
    if out.get("error"):
        logger.error(
            f"[GAP] run_gap_agent: completed with error for user_id={user_id}, job_id={job_id}, error={out.get('error')}"
        )
    else:
        res = out.get("result", {})
        overall = (
            analysis_obj.metrics.overall_score
            if analysis_obj
            else res.get("overall_match")
        )
        analysis_id = (
            analysis_obj.analysis_id if analysis_obj else res.get("analysis_id")
        )
        logger.info(
            f"[GAP] run_gap_agent: success user_id={user_id}, job_id={job_id}, overall_match={overall}, analysis_id={analysis_id}"
        )
    return out.get("result", {})
