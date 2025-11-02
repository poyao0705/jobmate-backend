from __future__ import annotations

from typing import Any


def get_resume_text(resume_row: Any) -> str:
    parsed = resume_row.parsed_json or {}
    # Prefer full raw_text when available; fall back to preview for demo/older rows
    raw = (parsed.get("raw_text") or "").strip()
    if raw:
        return raw
    preview = (parsed.get("text_preview") or "").strip()
    if preview:
        return preview
    raise ValueError(
        f"Resume {getattr(resume_row, 'id', '?')} missing raw_text and text_preview"
    )
