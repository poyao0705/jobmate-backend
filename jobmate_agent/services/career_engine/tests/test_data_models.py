"""
Tests for clean data models and converters.

These tests verify that the data structure is properly organized,
has low coupling, and is easy to test.
"""

from __future__ import annotations

import pytest

from jobmate_agent.services.career_engine.data_models import (
    LevelInfo,
    SkillMatch,
    AnalyzedSkill,
    SkillGapReport,
    build_gap_report,
)
from jobmate_agent.services.career_engine.report_converter import (
    convert_legacy_to_clean,
    convert_clean_to_legacy,
    convert_db_to_clean,
    convert_clean_to_db,
)


class TestLevelInfo:
    """Test LevelInfo data model."""

    def test_from_dict_with_full_data(self):
        """Test creating LevelInfo from complete dictionary."""
        data = {
            "label": "advanced",
            "score": 3.5,
            "years": 5.0,
            "confidence": 0.9,
            "evidence": ["Built production system", "Led team"],
            "signals": ["senior", "leadership"],
        }
        level = LevelInfo.from_dict(data)

        assert level.label == "advanced"
        assert level.score == 3.5
        assert level.years == 5.0
        assert level.confidence == 0.9
        assert len(level.evidence) == 2
        assert len(level.signals) == 2

    def test_from_dict_with_minimal_data(self):
        """Test creating LevelInfo with minimal required fields."""
        data = {"label": "working", "score": 2.0}
        level = LevelInfo.from_dict(data)

        assert level.label == "working"
        assert level.score == 2.0
        assert level.years is None
        assert level.confidence is None
        assert level.evidence == []
        assert level.signals == []

    def test_from_dict_with_empty_data(self):
        """Test creating LevelInfo from empty/None data."""
        level = LevelInfo.from_dict({})
        assert level is None

    def test_to_dict(self):
        """Test converting LevelInfo to dictionary."""
        level = LevelInfo(
            label="proficient", score=3.0, years=4.0, evidence=["Good evidence"]
        )
        data = level.to_dict()

        assert data["label"] == "proficient"
        assert data["score"] == 3.0
        assert data["years"] == 4.0
        assert data["evidence"] == ["Good evidence"]
        assert "confidence" not in data  # Optional field not included


class TestSkillMatch:
    """Test SkillMatch data model."""

    def test_from_dict_with_full_data(self):
        """Test creating SkillMatch from complete dictionary."""
        data = {
            "skill_id": "2.B.1.1",
            "name": "Python Programming",
            "skill_type": "skill",
            "score": 0.95,
            "hot_tech": True,
            "in_demand": True,
            "source_url": "https://onetcenter.org/...",
        }
        match = SkillMatch.from_dict(data)

        assert match.skill_id == "2.B.1.1"
        assert match.name == "Python Programming"
        assert match.skill_type == "skill"
        assert match.score == 0.95
        assert match.hot_tech is True
        assert match.in_demand is True
        assert match.source_url == "https://onetcenter.org/..."

    def test_from_dict_with_minimal_data(self):
        """Test creating SkillMatch with minimal required fields."""
        data = {"skill_id": "1.2.3", "name": "Skill Name"}
        match = SkillMatch.from_dict(data)

        assert match.skill_id == "1.2.3"
        assert match.name == "Skill Name"
        assert match.skill_type == "skill"  # default
        assert match.score is None
        assert match.hot_tech is False


class TestAnalyzedSkill:
    """Test AnalyzedSkill data model."""

    def test_from_dict_with_matched_skill(self):
        """Test creating AnalyzedSkill from matched skill data."""
        data = {
            "match": {"skill_id": "2.B.1.1", "name": "Python", "skill_type": "skill"},
            "candidate_level": {"label": "proficient", "score": 3.0},
            "required_level": {"label": "advanced", "score": 3.5},
            "level_delta": 0.5,
            "status": "underqualified",
        }
        skill = AnalyzedSkill.from_dict(data)

        assert skill.match.name == "Python"
        assert skill.candidate_level.score == 3.0
        assert skill.required_level.score == 3.5
        assert skill.level_delta == 0.5
        assert skill.status == "underqualified"

    def test_from_dict_with_missing_skill(self):
        """Test creating AnalyzedSkill from missing skill data."""
        data = {
            "match": {"skill_id": "2.B.1.2", "name": "React", "hot_tech": True},
            "is_required": True,
        }
        skill = AnalyzedSkill.from_dict(data)

        assert skill.match.name == "React"
        assert skill.match.hot_tech is True
        assert skill.is_required is True
        assert skill.level_delta == 0.0


class TestSkillGapReport:
    """Test SkillGapReport data model."""

    def test_build_from_raw_data(self):
        """Test building SkillGapReport from raw analysis results."""
        matched_raw = [
            {
                "match": {"skill_id": "1.1", "name": "Python"},
                "candidate_level": {"label": "advanced", "score": 3.5},
                "required_level": {"label": "advanced", "score": 3.5},
                "level_delta": 0.0,
                "status": "meets_or_exceeds",
                "is_required": True,
            },
            {
                "match": {"skill_id": "1.2", "name": "Java"},
                "candidate_level": {"label": "working", "score": 2.0},
                "required_level": {"label": "advanced", "score": 3.5},
                "level_delta": 1.5,
                "status": "underqualified",
                "is_required": True,
            },
        ]

        missing_raw = [
            {
                "match": {"skill_id": "1.3", "name": "React", "hot_tech": True},
                "is_required": True,
            },
            {"match": {"skill_id": "1.4", "name": "Vue"}, "is_required": False},
        ]

        report = build_gap_report(
            overall_score=6.5,
            matched_skills_raw=matched_raw,
            missing_skills_raw=missing_raw,
            resume_skills_raw=matched_raw,
            analysis_id=123,
        )

        assert report.overall_score == 6.5
        assert report.analysis_id == 123
        assert len(report.matched_skills) == 2
        assert len(report.missing_skills) == 2
        assert len(report.required_matched) == 2
        assert len(report.required_meets) == 1
        assert len(report.required_underqualified) == 1
        assert len(report.hot_tech_missing) == 1

    def test_organize_categories(self):
        """Test automatic category organization."""
        report = SkillGapReport(
            overall_score=7.0,
            matched_skills=[
                AnalyzedSkill(
                    match=SkillMatch(skill_id="1", name="Matched"),
                    status="meets_or_exceeds",
                    is_required=True,
                )
            ],
            missing_skills=[
                AnalyzedSkill(
                    match=SkillMatch(skill_id="2", name="Missing", hot_tech=True),
                    is_required=True,
                )
            ],
        )

        # Trigger organization
        report._organize_categories()

        # Verify categories were auto-organized
        assert len(report.required_matched) == 1
        assert len(report.required_missing) == 1
        assert len(report.hot_tech_missing) == 1

    def test_to_dict_and_from_dict_roundtrip(self):
        """Test roundtrip conversion from dict to report and back."""
        raw_data = {
            "overall_match": 8.0,
            "analysis_id": 456,
            "matched_skills": [
                {
                    "match": {"skill_id": "1", "name": "Skill1"},
                    "candidate_level": {"label": "advanced", "score": 3.5},
                    "required_level": {"label": "advanced", "score": 3.5},
                    "level_delta": 0.0,
                    "status": "meets_or_exceeds",
                    "is_required": True,
                }
            ],
            "missing_skills": [],
            "resume_skills": [],
        }

        original_report = SkillGapReport.from_dict(raw_data)

        # Convert to dict and back
        data = original_report.to_dict()
        restored_report = SkillGapReport.from_dict(data)

        assert restored_report.overall_score == original_report.overall_score
        assert restored_report.analysis_id == original_report.analysis_id
        assert len(restored_report.matched_skills) == len(
            original_report.matched_skills
        )
        assert restored_report.matched_skills[0].match.name == "Skill1"


class TestConverters:
    """Test converter functions between formats."""

    def test_convert_legacy_to_clean(self):
        """Test converting legacy format to clean format."""
        legacy_data = {
            "overall_match": 7.5,
            "matched_skills": [
                {
                    "match": {"skill_id": "1", "name": "Python"},
                    "candidate_level": {"label": "advanced", "score": 3.5},
                    "required_level": {"label": "advanced", "score": 3.5},
                    "level_delta": 0.0,
                    "status": "meets_or_exceeds",
                }
            ],
            "missing_skills": [{"match": {"skill_id": "2", "name": "React"}}],
            "resume_skills": [],
            "analysis_id": 789,
        }

        clean_report = convert_legacy_to_clean(legacy_data)

        assert clean_report.overall_score == 7.5
        assert clean_report.analysis_id == 789
        assert len(clean_report.matched_skills) == 1
        assert len(clean_report.missing_skills) == 1

    def test_convert_clean_to_legacy_roundtrip(self):
        """Test roundtrip conversion between legacy and clean formats."""
        legacy_data = {
            "overall_match": 6.0,
            "matched_skills": [
                {
                    "match": {"skill_id": "1", "name": "Skill1"},
                    "status": "meets_or_exceeds",
                }
            ],
            "missing_skills": [],
            "resume_skills": [],
        }

        # Convert to clean and back
        clean_report = convert_legacy_to_clean(legacy_data)
        legacy_result = convert_clean_to_legacy(clean_report)

        assert legacy_result["overall_match"] == legacy_data["overall_match"]
        assert len(legacy_result["matched_skills"]) == len(
            legacy_data["matched_skills"]
        )

    def test_convert_db_to_clean(self):
        """Test converting database JSON fields to clean format."""
        db_json_fields = {
            "matched_skills_json": [
                {
                    "match": {"skill_id": "1", "name": "Python"},
                    "status": "meets_or_exceeds",
                }
            ],
            "missing_skills_json": [{"match": {"skill_id": "2", "name": "React"}}],
            "resume_skills_json": [],
            "score": 8.0,
        }

        clean_report = convert_db_to_clean(**db_json_fields, analysis_id=999)

        assert clean_report.overall_score == 8.0
        assert clean_report.analysis_id == 999
        assert len(clean_report.matched_skills) == 1
        assert len(clean_report.missing_skills) == 1

    def test_convert_clean_to_db(self):
        """Test converting clean format to database fields."""
        clean_report = build_gap_report(
            overall_score=7.0,
            matched_skills_raw=[
                {
                    "match": {"skill_id": "1", "name": "Skill1"},
                    "status": "underqualified",
                }
            ],
            missing_skills_raw=[],
            resume_skills_raw=[],
        )

        db_fields = convert_clean_to_db(clean_report)

        assert db_fields["score"] == 7.0
        assert "matched_skills_json" in db_fields
        assert "weak_skills_json" in db_fields  # Should extract underqualified skills
        assert len(db_fields["weak_skills_json"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
