"""add analysis json to skill gap reports

Revision ID: d3f7a1c5ea12
Revises: change_chats_user_id
Create Date: 2025-11-02 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session

from jobmate_agent.models import SkillGapReport
from jobmate_agent.services.career_engine.schemas import (
    analysis_to_transport_payload,
    build_analysis_from_legacy,
)


# revision identifiers, used by Alembic.
revision = "d3f7a1c5ea12"
down_revision = "change_chats_user_id"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "skill_gap_reports", sa.Column("analysis_version", sa.String(), nullable=True)
    )
    op.add_column(
        "skill_gap_reports", sa.Column("analysis_json", sa.JSON(), nullable=True)
    )

    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        reports = session.query(SkillGapReport).all()
        for report in reports:
            context = {
                "resume_id": report.resume_id,
                "job_id": report.job_listing_id,
                "processing_run_id": report.processing_run_id,
            }
            analysis = build_analysis_from_legacy(
                overall_score=report.score or 0.0,
                matched_skills=report.matched_skills_json or [],
                missing_skills=report.missing_skills_json or [],
                resume_skills=report.resume_skills_json or [],
                context_overrides=context,
                analysis_id=report.id,
            )
            payload = analysis_to_transport_payload(analysis)
            report.analysis_version = analysis.version
            report.analysis_json = payload

        session.commit()
    finally:
        session.close()


def downgrade():
    op.drop_column("skill_gap_reports", "analysis_json")
    op.drop_column("skill_gap_reports", "analysis_version")
