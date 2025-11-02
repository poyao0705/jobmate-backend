"""drop resume_skills and job_skills tables

Revision ID: 7f4f9c1d2e3c
Revises: 3c1a0d0e9a2b
Create Date: 2025-10-29 00:00:10.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7f4f9c1d2e3c"
down_revision = "3c1a0d0e9a2b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop child tables if they exist
    bind = op.get_bind()
    dialect = bind.dialect.name
    # Use TRY pattern per backend
    try:
        op.drop_table("resume_skills")
    except Exception:
        pass
    try:
        op.drop_table("job_skills")
    except Exception:
        pass


def downgrade() -> None:
    # Recreate minimal schemas to allow downgrade
    op.create_table(
        "resume_skills",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("resume_id", sa.Integer(), nullable=False),
        sa.Column("skill_id_fk", sa.Integer(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("level_detected", sa.String(length=50), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"]),
        sa.ForeignKeyConstraint(["skill_id_fk"], ["skills.id"]),
    )

    op.create_table(
        "job_skills",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_listing_id", sa.Integer(), nullable=False),
        sa.Column("skill_id_fk", sa.Integer(), nullable=False),
        sa.Column("required_level", sa.String(length=50), nullable=True),
        sa.Column("weight", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["job_listing_id"], ["job_listings.id"]),
        sa.ForeignKeyConstraint(["skill_id_fk"], ["skills.id"]),
    )
