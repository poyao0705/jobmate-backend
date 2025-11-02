"""Change skill_gap_reports.user_id to reference user_profiles.id (string)

Revision ID: c6f3f1a2d9b1
Revises: f2898435a60e
Create Date: 2025-10-31 02:50:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c6f3f1a2d9b1"
down_revision = "f2898435a60e"
branch_labels = None
depends_on = None


def drop_fk_constraint_dynamically(table: str, column: str) -> None:
    """Drop a FK constraint for a given table/column by looking it up in information_schema."""
    conn = op.get_bind()
    res = conn.execute(
        sa.text(
            """
            SELECT tc.constraint_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_name = :table
              AND kcu.column_name = :column
            LIMIT 1
            """
        ),
        {"table": table, "column": column},
    )
    row = res.fetchone()
    if row and row[0]:
        op.drop_constraint(row[0], table_name=table, type_="foreignkey")


def upgrade() -> None:
    # 1) Add new temporary column referencing user_profiles.id
    op.add_column(
        "skill_gap_reports",
        sa.Column("user_profile_id", sa.String(), nullable=True),
    )
    op.create_foreign_key(
        constraint_name="fk_sgr_user_profile_id_user_profiles",
        source_table="skill_gap_reports",
        referent_table="user_profiles",
        local_cols=["user_profile_id"],
        remote_cols=["id"],
        ondelete=None,
    )

    # 2) Backfill from resumes.user_id via resume_id
    op.execute(
        sa.text(
            """
            UPDATE skill_gap_reports AS sgr
            SET user_profile_id = r.user_id
            FROM resumes AS r
            WHERE r.id = sgr.resume_id
            """
        )
    )

    # 3) Make new column NOT NULL
    op.alter_column(
        "skill_gap_reports",
        "user_profile_id",
        existing_type=sa.String(),
        nullable=False,
    )

    # 4) Drop old FK on user_id and the column, then rename new column to user_id
    drop_fk_constraint_dynamically("skill_gap_reports", "user_id")
    op.drop_column("skill_gap_reports", "user_id")
    op.alter_column(
        "skill_gap_reports",
        "user_profile_id",
        new_column_name="user_id",
        existing_type=sa.String(),
        nullable=False,
    )

    # 5) Create new FK constraint to user_profiles.id on the renamed column
    op.create_foreign_key(
        constraint_name="fk_sgr_user_id_user_profiles",
        source_table="skill_gap_reports",
        referent_table="user_profiles",
        local_cols=["user_id"],
        remote_cols=["id"],
        ondelete=None,
    )


def downgrade() -> None:
    # Best-effort downgrade: add integer user_id back (nullable), drop new FK, then drop string user_id
    op.drop_constraint(
        "fk_sgr_user_id_user_profiles", "skill_gap_reports", type_="foreignkey"
    )

    op.add_column(
        "skill_gap_reports",
        sa.Column("user_id_int", sa.Integer(), nullable=True),
    )

    # Drop string user_id and rename user_id_int back to user_id
    op.drop_column("skill_gap_reports", "user_id")
    op.alter_column(
        "skill_gap_reports",
        "user_id_int",
        new_column_name="user_id",
        existing_type=sa.Integer(),
        nullable=True,
    )

    # Note: Original FK to users.id is not restored automatically
