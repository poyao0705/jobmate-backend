"""change chats user_id to varchar

Revision ID: change_chats_user_id
Revises:
Create Date: 2025-11-01 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "change_chats_user_id"
down_revision = "bc577da832b5"
branch_labels = None
depends_on = None


def upgrade():
    """
    Change chats.user_id from Integer to String (VARCHAR) to support Auth0 user IDs.
    Also updates the foreign key to reference user_profiles.id instead of users.id.

    WARNING: This migration will:
    1. Drop existing data in user_id column (if it contains integer IDs)
    2. Change the column type to VARCHAR
    3. Update foreign key constraint

    You may need to manually migrate data from old integer user_ids to Auth0 string IDs first.
    """

    # For PostgreSQL, use DROP CONSTRAINT IF EXISTS
    # Check if we're using PostgreSQL
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE chats DROP CONSTRAINT IF EXISTS chats_user_id_fkey")
        # Change column type with USING clause for PostgreSQL
        op.execute(
            "ALTER TABLE chats ALTER COLUMN user_id TYPE VARCHAR USING user_id::text"
        )
        # Clear invalid user_ids (integers that don't exist in user_profiles) before adding constraint
        op.execute(
            """
            UPDATE chats 
            SET user_id = NULL 
            WHERE user_id IS NOT NULL 
            AND user_id NOT IN (SELECT id::text FROM user_profiles)
        """
        )
        # Add new foreign key constraint (allowing NULL for orphaned records)
        op.execute(
            """
            ALTER TABLE chats 
            ADD CONSTRAINT chats_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES user_profiles(id)
        """
        )
    else:
        # For SQLite, use batch_alter_table
        with op.batch_alter_table("chats", schema=None) as batch_op:
            batch_op.alter_column(
                "user_id",
                existing_type=sa.Integer(),
                type_=sa.String(),
                existing_nullable=True,
            )
            # Try to drop existing FK if it exists
            try:
                batch_op.drop_constraint("chats_user_id_fkey", type_="foreignkey")
            except:
                pass
            # Add new foreign key constraint
            batch_op.create_foreign_key(
                "chats_user_id_fkey", "user_profiles", ["user_id"], ["id"]
            )


def downgrade():
    """
    Revert chats.user_id back to Integer type.
    WARNING: This will lose data if you have Auth0 string IDs!
    """

    # Drop the foreign key to user_profiles
    with op.batch_alter_table("chats", schema=None) as batch_op:
        try:
            batch_op.drop_constraint("chats_user_id_fkey", type_="foreignkey")
        except:
            pass

    # Change back to Integer
    with op.batch_alter_table("chats", schema=None) as batch_op:
        batch_op.alter_column(
            "user_id",
            existing_type=sa.String(),
            type_=sa.Integer(),
            existing_nullable=True,
        )

    # Restore foreign key to users.id
    with op.batch_alter_table("chats", schema=None) as batch_op:
        batch_op.create_foreign_key("chats_user_id_fkey", "users", ["user_id"], ["id"])
