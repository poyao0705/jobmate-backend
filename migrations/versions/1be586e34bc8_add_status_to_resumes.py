"""add_status_to_resumes

Revision ID: 1be586e34bc8
Revises: bd0924d440e0
Create Date: 2025-10-28 13:20:07.021932

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1be586e34bc8"
down_revision = "bd0924d440e0"
branch_labels = None
depends_on = None


def upgrade():
    # Add status column with default value
    op.add_column(
        "resumes",
        sa.Column("status", sa.String(), nullable=False, server_default="processing"),
    )

    # Create index for performance
    op.create_index("ix_resumes_status", "resumes", ["status"])


def downgrade():
    # Remove index
    op.drop_index("ix_resumes_status", table_name="resumes")

    # Remove column
    op.drop_column("resumes", "status")
