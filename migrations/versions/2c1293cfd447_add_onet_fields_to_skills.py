"""add_onet_fields_to_skills

Revision ID: 2c1293cfd447
Revises: add_s3_fields_to_resumes
Create Date: 2025-10-28 02:48:07.209441

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2c1293cfd447"
down_revision = "add_s3_fields_to_resumes"
branch_labels = None
depends_on = None


def upgrade():
    # Add framework column with default 'Custom' for backward compatibility
    op.add_column(
        "skills",
        sa.Column("framework", sa.String(), nullable=False, server_default="Custom"),
    )

    # Add external_id column (nullable for custom skills)
    op.add_column("skills", sa.Column("external_id", sa.String(), nullable=True))

    # Add meta_json to skill_aliases for provenance tracking
    op.add_column("skill_aliases", sa.Column("meta_json", sa.JSON(), nullable=True))

    # Create indexes for performance
    op.create_index("ix_skills_framework", "skills", ["framework"])
    op.create_index("ix_skills_external_id", "skills", ["external_id"])


def downgrade():
    # Remove indexes
    op.drop_index("ix_skills_external_id", table_name="skills")
    op.drop_index("ix_skills_framework", table_name="skills")

    # Remove columns
    op.drop_column("skill_aliases", "meta_json")
    op.drop_column("skills", "external_id")
    op.drop_column("skills", "framework")
