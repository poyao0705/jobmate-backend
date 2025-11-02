"""move text_preview to raw_text in resumes.parsed_json

Revision ID: 3c1a0d0e9a2b
Revises: f2898435a60e
Create Date: 2025-10-29 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
import json


# revision identifiers, used by Alembic.
revision = "3c1a0d0e9a2b"
down_revision = "f2898435a60e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    # Ensure parsed_json is not NULL
    op.execute(text("UPDATE resumes SET parsed_json = '{}' WHERE parsed_json IS NULL"))

    if dialect_name == "postgresql":
        # Use JSON operators (not JSONB) to move key
        op.execute(
            text(
                """
                UPDATE resumes
                SET parsed_json = 
                    jsonb_set(
                        (parsed_json::jsonb - 'text_preview'),
                        '{raw_text}',
                        to_jsonb(parsed_json->>'text_preview')
                    )::json
                WHERE parsed_json::jsonb ? 'text_preview' 
                AND NOT (parsed_json::jsonb ? 'raw_text');
                """
            )
        )
        # Skip index creation for JSON column as it doesn't support ? operator
    else:
        # SQLite or others: do Python-side backfill
        result = bind.execute(text("SELECT id, parsed_json FROM resumes"))
        rows = result.fetchall()
        for row in rows:
            rid = row[0]
            pj_raw = row[1]
            try:
                data = (
                    pj_raw
                    if isinstance(pj_raw, dict)
                    else (json.loads(pj_raw) if pj_raw else {})
                )
            except Exception:
                data = {}
            changed = False
            if isinstance(data, dict):
                if "raw_text" not in data and "text_preview" in data:
                    data["raw_text"] = data.get("text_preview")
                    data.pop("text_preview", None)
                    changed = True
            if changed:
                bind.execute(
                    text("UPDATE resumes SET parsed_json = :pj WHERE id = :id"),
                    {"pj": json.dumps(data), "id": rid},
                )


def downgrade() -> None:
    # No-op: do not reintroduce text_preview. Optionally copy raw_text back to text_preview.
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    if dialect_name == "postgresql":
        op.execute(
            text(
                """
                UPDATE resumes
                SET parsed_json =
                    (parsed_json - 'raw_text') ||
                    jsonb_build_object('text_preview', parsed_json->>'raw_text')
                WHERE parsed_json ? 'raw_text' AND NOT (parsed_json ? 'text_preview');
                """
            )
        )
    else:
        result = bind.execute(text("SELECT id, parsed_json FROM resumes"))
        rows = result.fetchall()
        for row in rows:
            rid = row[0]
            pj_raw = row[1]
            try:
                data = (
                    pj_raw
                    if isinstance(pj_raw, dict)
                    else (json.loads(pj_raw) if pj_raw else {})
                )
            except Exception:
                data = {}
            changed = False
            if isinstance(data, dict):
                if "text_preview" not in data and "raw_text" in data:
                    data["text_preview"] = data.get("raw_text")
                    changed = True
            if changed:
                bind.execute(
                    text("UPDATE resumes SET parsed_json = :pj WHERE id = :id"),
                    {"pj": json.dumps(data), "id": rid},
                )
