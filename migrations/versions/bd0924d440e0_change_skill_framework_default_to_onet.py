"""change_skill_framework_default_to_onet

Revision ID: bd0924d440e0
Revises: f2898435a60e
Create Date: 2025-10-28 13:06:26.945475

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "bd0924d440e0"
down_revision = "f2898435a60e"
branch_labels = None
depends_on = None


def upgrade():
    # Change the default value
    op.alter_column("skills", "framework", server_default="ONET")
    # Update existing records that are 'Custom' to 'ONET' if needed
    op.execute("UPDATE skills SET framework = 'ONET' WHERE framework = 'Custom'")


def downgrade():
    pass
