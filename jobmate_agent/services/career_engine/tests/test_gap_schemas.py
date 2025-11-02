from __future__ import annotations

import pytest

from jobmate_agent.services.career_engine.report_renderer import ReportRenderer
from jobmate_agent.services.career_engine.schemas import (
    ANALYSIS_SCHEMA_VERSION,
    GapAnalysisResult,
    analysis_to_transport_payload,
    build_analysis_from_legacy,
    load_analysis_from_storage,
)


def _sample_matched_skill(status: str = "meets_or_exceeds") -> dict:
    return {
        "match": {
            "skill_id": "skill.python",
            "name": "Python",
            "skill_type": "skill",
        },
        "candidate_level": {"label": "advanced", "score": 3.5},
        "required_level": {"label": "advanced", "score": 3.5},
        "level_delta": 0.0,
        "status": status,
        "is_required": True,
    }


def _sample_missing_skill(is_required: bool = True) -> dict:
    return {
        "match": {
            "skill_id": "skill.react",
            "name": "React",
            "skill_type": "skill",
            "hot_tech": True,
        },
        "is_required": is_required,
    }


def test_build_analysis_from_legacy_produces_metrics() -> None:
    analysis = build_analysis_from_legacy(
        overall_score=6.2,
        matched_skills=[
            _sample_matched_skill(),
            _sample_matched_skill("underqualified"),
        ],
        missing_skills=[_sample_missing_skill()],
        resume_skills=[_sample_matched_skill()],
        context_overrides={"resume_id": 1, "job_id": 2},
        analysis_id=99,
    )

    assert isinstance(analysis, GapAnalysisResult)
    assert analysis.analysis_id == 99
    assert analysis.metrics.overall_score == 6.2
    assert analysis.metrics.matched_skill_count == 2
    assert analysis.metrics.missing_skill_count == 1
    assert analysis.metrics.resume_skill_count == 1
    assert analysis.metrics.underqualified_skill_count == 1


def test_analysis_to_transport_payload_serializes_datetime() -> None:
    analysis = build_analysis_from_legacy(
        overall_score=7.1,
        matched_skills=[_sample_matched_skill()],
        missing_skills=[],
        resume_skills=[],
        context_overrides={"resume_id": 42, "job_id": 24},
    )
    analysis.report_markdown = "# Report"  # ensure markdown is present

    payload = analysis_to_transport_payload(analysis)

    assert payload["version"] == ANALYSIS_SCHEMA_VERSION
    assert payload["metrics"]["overall_score"] == pytest.approx(7.1)
    assert isinstance(payload["context"].get("generated_at"), str)
    assert payload["report_markdown"] == "# Report"


def test_load_analysis_prefers_versioned_payload() -> None:
    source = build_analysis_from_legacy(
        overall_score=5.0,
        matched_skills=[_sample_matched_skill()],
        missing_skills=[_sample_missing_skill()],
        resume_skills=[],
        context_overrides={"resume_id": 11, "job_id": 22},
        analysis_id=777,
    )
    payload = analysis_to_transport_payload(source)

    restored = load_analysis_from_storage(
        analysis_json=payload,
        analysis_version=payload["version"],
        score=None,
        matched_skills=None,
        missing_skills=None,
        resume_skills=None,
        context=None,
        analysis_id=777,
    )

    assert restored.analysis_id == 777
    assert restored.metrics.overall_score == pytest.approx(5.0)
    assert restored.version == ANALYSIS_SCHEMA_VERSION


def test_load_analysis_from_legacy_columns() -> None:
    restored = load_analysis_from_storage(
        analysis_json=None,
        analysis_version=None,
        score=4.5,
        matched_skills=[_sample_matched_skill()],
        missing_skills=[_sample_missing_skill()],
        resume_skills=[],
        context={"resume_id": 5, "job_id": 6},
        analysis_id=888,
    )

    assert restored.analysis_id == 888
    assert restored.metrics.overall_score == pytest.approx(4.5)
    assert restored.metrics.missing_skill_count == 1
    assert restored.version == ANALYSIS_SCHEMA_VERSION


def test_report_renderer_accepts_canonical_analysis() -> None:
    analysis = build_analysis_from_legacy(
        overall_score=8.0,
        matched_skills=[_sample_matched_skill()],
        missing_skills=[_sample_missing_skill()],
        resume_skills=[_sample_matched_skill()],
        context_overrides={},
    )
    analysis.report_markdown = None

    renderer = ReportRenderer()
    markdown = renderer.render(analysis)

    assert isinstance(markdown, str)
    assert "Overall Match" in markdown
