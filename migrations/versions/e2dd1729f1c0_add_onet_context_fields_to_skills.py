"""add_onet_context_fields_to_skills

Revision ID: e2dd1729f1c0
Revises: 1be586e34bc8
Create Date: 2025-10-29 12:00:07.661518

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e2dd1729f1c0"
down_revision = "1be586e34bc8"
branch_labels = None
depends_on = None


def upgrade():
    # Add O*NET context fields to skills table
    op.add_column("skills", sa.Column("onet_soc_code", sa.String(10), nullable=True))
    op.add_column(
        "skills", sa.Column("occupation_title", sa.String(150), nullable=True)
    )
    op.add_column("skills", sa.Column("commodity_title", sa.String(150), nullable=True))
    op.add_column(
        "skills",
        sa.Column("hot_tech", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "skills",
        sa.Column("in_demand", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "skills",
        sa.Column("skill_type", sa.String(50), nullable=True, server_default="skill"),
    )

    # Create indexes for performance
    op.create_index("ix_skills_onet_soc_code", "skills", ["onet_soc_code"])
    op.create_index("ix_skills_skill_type", "skills", ["skill_type"])
    op.create_index("ix_skills_hot_tech", "skills", ["hot_tech"])
    op.create_index("ix_skills_in_demand", "skills", ["in_demand"])


def downgrade():
    # Remove indexes
    op.drop_index("ix_skills_in_demand", table_name="skills")
    op.drop_index("ix_skills_hot_tech", table_name="skills")
    op.drop_index("ix_skills_skill_type", table_name="skills")
    op.drop_index("ix_skills_onet_soc_code", table_name="skills")

    # Remove columns
    op.drop_column("skills", "skill_type")
    op.drop_column("skills", "in_demand")
    op.drop_column("skills", "hot_tech")
    op.drop_column("skills", "commodity_title")
    op.drop_column("skills", "occupation_title")
    op.drop_column("skills", "onet_soc_code")
