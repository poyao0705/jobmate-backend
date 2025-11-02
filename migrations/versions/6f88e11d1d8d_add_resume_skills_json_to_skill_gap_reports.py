"""add resume_skills_json to skill_gap_reports

Revision ID: 6f88e11d1d8d
Revises: bc577da832b5
Create Date: 2025-01-XX

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "6f88e11d1d8d"
down_revision = "change_chats_user_id"
branch_labels = None
depends_on = None


def upgrade():
    # Add resume_skills_json column to skill_gap_reports table
    # Using JSON type (works for both PostgreSQL and SQLite)
    op.add_column(
        "skill_gap_reports", sa.Column("resume_skills_json", sa.JSON(), nullable=True)
    )


def downgrade():
    # Remove resume_skills_json column
    op.drop_column("skill_gap_reports", "resume_skills_json")
