"""
Services for seeding the Skills Ontology into SQL (Skill, SkillAlias) and Chroma.

This module provides:
- Strict JSON loader/validator for the ontology file
- Fail-fast guard when SQL tables are missing (no migrations in this change)
- Idempotent upserts for SQL (when tables exist) and Chroma (always available)

Constraints:
- No new dependencies; use existing SQLAlchemy/Flask setup and vector_store
- Keep DB schema as defined in DATA_MODEL.md

Usage is orchestrated by scripts/seed_skills.py
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import MetaData, Table, and_, select, update, insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from jobmate_agent.services.vector_store import vector_store


SKILL_ID_PATTERN = re.compile(r"^[a-z0-9]+(\.[a-z0-9]+)*$")


@dataclass
class SkillRecord:
    skill_id: str
    name: str
    category: str
    aliases: List[str]
    meta: Dict[str, Any]
    framework: str = "Custom"  # Default to Custom for backward compatibility
    external_id: Optional[str] = None


@dataclass
class UpsertStats:
    inserted_skills: int
    updated_skills: int
    inserted_aliases: int
    skipped_aliases: int


class SkillsSeedError(Exception):
    """Domain error for skills seeding failures."""


def _normalize_aliases(name: str, aliases: Iterable[str]) -> List[str]:
    """Normalize aliases: trim, dedupe case-insensitively, exclude the canonical name.

    Returns a stable list with original casing of first-seen entries.
    """
    seen_lower = set([name.strip().lower()])
    deduped: List[str] = []
    for a in aliases or []:
        if not isinstance(a, str):
            continue
        s = a.strip()
        if not s:
            continue
        low = s.lower()
        if low in seen_lower:
            continue
        seen_lower.add(low)
        deduped.append(s)
    return deduped


def _normalize_skill_id(raw: str) -> str:
    """Normalize a provided skill_id into a canonical slug using dot separators.

    Rules:
    - Lowercase all characters
    - Replace any non [a-z0-9.] characters with a dot
    - Collapse multiple consecutive dots
    - Strip leading/trailing dots
    """
    s = raw.strip().lower()
    # Replace invalid chars with dot
    s = re.sub(r"[^a-z0-9\.]+", ".", s)
    # Collapse multiple dots
    s = re.sub(r"\.\.+", ".", s)
    # Strip dots at ends
    s = s.strip(".")
    return s


def load_and_validate(path: str) -> List[SkillRecord]:
    """Load ontology JSON and validate into a list of SkillRecord.

    Requirements:
    - JSON must be an array of objects
    - Each object has required fields: skill_id, name, category
    - aliases is optional list[str]; meta is optional object
    - skill_id must match slug pattern SKILL_ID_PATTERN
    - No duplicate skill_id across records
    - At least 200 records
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"invalid skills_ontology.json: {e}") from e

    if not isinstance(data, list):
        raise ValueError("invalid skills_ontology.json: root must be a list")

    records: List[SkillRecord] = []
    seen_ids = set()
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"record {idx} is not an object")
        skill_id = item.get("skill_id")
        name = item.get("name")
        category = item.get("category")
        if (
            not isinstance(skill_id, str)
            or not isinstance(name, str)
            or not isinstance(category, str)
        ):
            raise ValueError(
                f"record {idx} missing required fields: skill_id/name/category"
            )
        # Normalize skill_id then validate
        norm_skill_id = _normalize_skill_id(skill_id)
        if not SKILL_ID_PATTERN.match(norm_skill_id):
            raise ValueError(
                f"record {idx} invalid skill_id slug: {skill_id} -> {norm_skill_id}"
            )
        if norm_skill_id in seen_ids:
            raise ValueError(f"duplicate skill_id: {norm_skill_id}")
        seen_ids.add(norm_skill_id)

        aliases_raw = item.get("aliases", [])
        if aliases_raw is None:
            aliases_raw = []
        if not isinstance(aliases_raw, list):
            raise ValueError(f"record {idx} aliases must be a list")
        aliases = _normalize_aliases(name, aliases_raw)

        meta = item.get("meta") or {}
        if not isinstance(meta, dict):
            raise ValueError(f"record {idx} meta must be an object if provided")

        # Extract framework and external_id from meta if present
        framework = meta.get("framework", "Custom")
        external_id = meta.get("external_id")

        records.append(
            SkillRecord(
                skill_id=norm_skill_id,
                name=name.strip(),
                category=category.strip(),
                aliases=aliases,
                meta=meta,
                framework=framework,
                external_id=external_id,
            )
        )

    if len(records) < 200:
        raise ValueError("skills_ontology.json must contain at least 200 skills")

    return records


def _reflect_tables(engine: Engine) -> Tuple[Optional[Table], Optional[Table]]:
    """Reflect skills and skill_aliases tables if present."""
    md = MetaData()
    try:
        md.reflect(bind=engine, only=["skills", "skill_aliases"])
    except SQLAlchemyError:
        # Reflection may fail; treat as missing
        return None, None
    skills_tbl = md.tables.get("skills")
    alias_tbl = md.tables.get("skill_aliases")
    return skills_tbl, alias_tbl


def ensure_sql_tables_exist_or_fail(db_module) -> None:
    """Fail fast if skills tables are missing.

    Raises RuntimeError with a clear message. Does not create tables.
    """
    engine: Engine = db_module.engine  # type: ignore[attr-defined]
    skills_tbl, alias_tbl = _reflect_tables(engine)
    if skills_tbl is None or alias_tbl is None:
        raise RuntimeError(
            "skills tables missing; run migrations to add Skill/SkillAlias before seeding"
        )


def upsert_sql(
    session: Session, records: List[SkillRecord], seed_version: str
) -> UpsertStats:
    """Idempotently upsert into SQL tables using reflection.

    This function requires that `skills` and `skill_aliases` tables exist with columns
    as defined in DATA_MODEL.md. It does not manage embeddings; only writes
    `vector_doc_id` as a stable Chroma ID placeholder (skill:skill_id).
    """
    engine = session.get_bind()
    assert engine is not None
    skills_tbl, alias_tbl = _reflect_tables(engine)
    if skills_tbl is None or alias_tbl is None:
        raise RuntimeError(
            "skills tables missing; run migrations to add Skill/SkillAlias before seeding"
        )

    inserted_skills = 0
    updated_skills = 0
    inserted_aliases = 0
    skipped_aliases = 0

    for rec in records:
        chroma_id = f"skill:{rec.skill_id}"

        # Find existing skill by skill_id first, then by name as fallback
        existing = (
            session.execute(
                select(skills_tbl).where(skills_tbl.c.skill_id == rec.skill_id)
            )
            .mappings()
            .first()
        )
        if existing is None:
            existing = (
                session.execute(select(skills_tbl).where(skills_tbl.c.name == rec.name))
                .mappings()
                .first()
            )

        if existing is None:
            # Insert new skill
            result = session.execute(
                insert(skills_tbl).values(
                    skill_id=rec.skill_id,
                    name=rec.name,
                    taxonomy_path=rec.category,
                    vector_doc_id=chroma_id,
                    framework=rec.framework,
                    external_id=rec.external_id,
                    meta_json=rec.meta,
                )
            )
            skill_pk = result.inserted_primary_key[0]
            inserted_skills += 1
        else:
            # Update existing skill
            skill_pk = existing["id"]
            session.execute(
                update(skills_tbl)
                .where(skills_tbl.c.id == skill_pk)
                .values(
                    name=rec.name,
                    taxonomy_path=rec.category,
                    vector_doc_id=chroma_id,
                    framework=rec.framework,
                    external_id=rec.external_id,
                    meta_json=rec.meta,
                )
            )
            updated_skills += 1

        # Upsert aliases idempotently by (skill_id_fk, alias)
        for alias in rec.aliases:
            exists = session.execute(
                select(alias_tbl.c.id).where(
                    and_(
                        alias_tbl.c.skill_id_fk == skill_pk, alias_tbl.c.alias == alias
                    )
                )
            ).first()
            if exists is None:
                session.execute(
                    insert(alias_tbl).values(skill_id_fk=skill_pk, alias=alias)
                )
                inserted_aliases += 1
            else:
                skipped_aliases += 1

    session.commit()
    return UpsertStats(
        inserted_skills=inserted_skills,
        updated_skills=updated_skills,
        inserted_aliases=inserted_aliases,
        skipped_aliases=skipped_aliases,
    )


def upsert_chroma(records: List[SkillRecord], seed_version: str) -> None:
    """Idempotently upsert skills into Chroma `skills_ontology` collection.

    - Stable IDs: skill:{skill_id}
    - Metadata includes: skill_id, category, aliases, version
    - Document text: "{name} | Aliases: a1, a2, ..." (simple for now)
    """
    col = vector_store.skills_ontology()

    ids: List[str] = []
    documents: List[str] = []
    metadatas: List[Dict[str, Any]] = []
    # Provide dummy embeddings to avoid Chroma attempting to compute embeddings via ONNX/network.
    # Use a common small model dimension (384 for MiniLM). This satisfies storage without inference.
    embeddings: List[List[float]] = []

    for rec in records:
        sid = f"skill:{rec.skill_id}"
        ids.append(sid)
        alias_str = ", ".join(rec.aliases) if rec.aliases else ""
        doc = rec.name if not alias_str else f"{rec.name} | Aliases: {alias_str}"
        documents.append(doc)
        metadatas.append(
            {
                "skill_id": rec.skill_id,
                "category": rec.category,
                "framework": rec.framework,
                "external_id": rec.external_id or "",
                # Chroma metadata values must be scalar; store aliases as CSV string
                "aliases": alias_str,
                "version": seed_version,
            }
        )
        embeddings.append([0.0] * 384)

    # Prefer upsert if available; fallback to add+update pattern
    if hasattr(col, "upsert"):
        col.upsert(
            ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings
        )
    else:
        # Try add, if duplicates exist, update those
        try:
            vector_store.add_docs(
                col,
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings,
            )
        except Exception:
            # Update per-record to be conservative
            for i, sid in enumerate(ids):
                try:
                    col.add(
                        ids=[sid],
                        documents=[documents[i]],
                        metadatas=[metadatas[i]],
                        embeddings=[embeddings[i]],
                    )
                except Exception:
                    col.update(
                        ids=[sid],
                        documents=[documents[i]],
                        metadatas=[metadatas[i]],
                        embeddings=[embeddings[i]],
                    )
