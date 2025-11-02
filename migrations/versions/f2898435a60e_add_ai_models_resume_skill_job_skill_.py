"""add_ai_models_resume_skill_job_skill_gap_report_learning_item

Revision ID: f2898435a60e
Revises: 2c1293cfd447
Create Date: 2025-10-28 04:25:40.937269

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f2898435a60e"
down_revision = "2c1293cfd447"
branch_labels = None
depends_on = None


def upgrade():
    # Create resume_skills table
    op.create_table(
        "resume_skills",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("resume_id", sa.Integer(), nullable=False),
        sa.Column("skill_id_fk", sa.Integer(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("level_detected", sa.String(length=50), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["resume_id"],
            ["resumes.id"],
        ),
        sa.ForeignKeyConstraint(
            ["skill_id_fk"],
            ["skills.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create job_skills table
    op.create_table(
        "job_skills",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_listing_id", sa.Integer(), nullable=False),
        sa.Column("skill_id_fk", sa.Integer(), nullable=False),
        sa.Column("required_level", sa.String(length=50), nullable=True),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["job_listing_id"],
            ["job_listings.id"],
        ),
        sa.ForeignKeyConstraint(
            ["skill_id_fk"],
            ["skills.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create skill_gap_reports table
    op.create_table(
        "skill_gap_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("resume_id", sa.Integer(), nullable=False),
        sa.Column("job_listing_id", sa.Integer(), nullable=False),
        sa.Column("matched_skills_json", sa.JSON(), nullable=False),
        sa.Column("missing_skills_json", sa.JSON(), nullable=False),
        sa.Column("weak_skills_json", sa.JSON(), nullable=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("report_note_id", sa.Integer(), nullable=True),
        sa.Column("processing_run_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["job_listing_id"],
            ["job_listings.id"],
        ),
        sa.ForeignKeyConstraint(
            ["processing_run_id"],
            ["processing_runs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["report_note_id"],
            ["notes.id"],
        ),
        sa.ForeignKeyConstraint(
            ["resume_id"],
            ["resumes.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create learning_items table
    op.create_table(
        "learning_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("skill_id_fk", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("est_time_min", sa.Integer(), nullable=True),
        sa.Column("difficulty", sa.String(length=20), nullable=True),
        sa.Column("meta_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["skill_id_fk"],
            ["skills.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create report_learning_items table
    op.create_table(
        "report_learning_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("learning_item_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["learning_item_id"],
            ["learning_items.id"],
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["skill_gap_reports.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Add learning_item_id column to tasks table
    op.add_column("tasks", sa.Column("learning_item_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_tasks_learning_item_id",
        "tasks",
        "learning_items",
        ["learning_item_id"],
        ["id"],
    )

    # Create indexes for performance
    op.create_index("ix_resume_skills_resume_id", "resume_skills", ["resume_id"])
    op.create_index("ix_resume_skills_skill_id_fk", "resume_skills", ["skill_id_fk"])
    op.create_index("ix_job_skills_job_listing_id", "job_skills", ["job_listing_id"])
    op.create_index("ix_job_skills_skill_id_fk", "job_skills", ["skill_id_fk"])
    op.create_index("ix_skill_gap_reports_user_id", "skill_gap_reports", ["user_id"])
    op.create_index(
        "ix_skill_gap_reports_resume_id", "skill_gap_reports", ["resume_id"]
    )
    op.create_index(
        "ix_skill_gap_reports_job_listing_id", "skill_gap_reports", ["job_listing_id"]
    )
    op.create_index("ix_learning_items_skill_id_fk", "learning_items", ["skill_id_fk"])
    op.create_index(
        "ix_report_learning_items_report_id", "report_learning_items", ["report_id"]
    )
    op.create_index(
        "ix_report_learning_items_learning_item_id",
        "report_learning_items",
        ["learning_item_id"],
    )
    op.create_index("ix_tasks_learning_item_id", "tasks", ["learning_item_id"])


def downgrade():
    # Drop indexes
    op.drop_index("ix_tasks_learning_item_id", table_name="tasks")
    op.drop_index(
        "ix_report_learning_items_learning_item_id", table_name="report_learning_items"
    )
    op.drop_index(
        "ix_report_learning_items_report_id", table_name="report_learning_items"
    )
    op.drop_index("ix_learning_items_skill_id_fk", table_name="learning_items")
    op.drop_index("ix_skill_gap_reports_job_listing_id", table_name="skill_gap_reports")
    op.drop_index("ix_skill_gap_reports_resume_id", table_name="skill_gap_reports")
    op.drop_index("ix_skill_gap_reports_user_id", table_name="skill_gap_reports")
    op.drop_index("ix_job_skills_skill_id_fk", table_name="job_skills")
    op.drop_index("ix_job_skills_job_listing_id", table_name="job_skills")
    op.drop_index("ix_resume_skills_skill_id_fk", table_name="resume_skills")
    op.drop_index("ix_resume_skills_resume_id", table_name="resume_skills")

    # Drop foreign key constraint and column from tasks
    op.drop_constraint("fk_tasks_learning_item_id", "tasks", type_="foreignkey")
    op.drop_column("tasks", "learning_item_id")

    # Drop tables
    op.drop_table("report_learning_items")
    op.drop_table("learning_items")
    op.drop_table("skill_gap_reports")
    op.drop_table("job_skills")
    op.drop_table("resume_skills")
