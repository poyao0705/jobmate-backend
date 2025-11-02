"""
Vector store initialization and helpers for ChromaDB.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection


REQUIRED_COLLECTIONS = ("skills_ontology",)


def get_client() -> ClientAPI:
    """Create or return a Chroma PersistentClient configured via env."""
    persist_path = str(
        Path(os.getenv("CHROMA_PERSIST_DIR", "./instance/chroma"))
        .expanduser()
        .resolve()
    )
    client = chromadb.PersistentClient(path=persist_path)
    return client


def get_or_create_collection(name: str) -> Collection:
    """Get or create a collection by name."""
    client = get_client()
    return client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})


def get_collections() -> List[str]:
    """List existing collection names."""
    client = get_client()
    cols = client.list_collections()
    return [c.name for c in cols]


def init_collections() -> None:
    """Idempotently ensure all required collections exist."""
    for name in REQUIRED_COLLECTIONS:
        get_or_create_collection(name)


def resumes() -> Collection:
    raise NotImplementedError(
        "'resumes' collection is no longer supported. Use skills_ontology only."
    )


def jobs() -> Collection:
    raise NotImplementedError(
        "'jobs' collection is no longer supported. Use skills_ontology only."
    )


def skills_ontology() -> Collection:
    return get_or_create_collection("skills_ontology")


def learning_corpus() -> Collection:
    raise NotImplementedError(
        "'learning_corpus' collection is no longer supported in skill-only mode."
    )


def add_docs(
    collection: Collection,
    ids: Iterable[str],
    documents: Optional[Iterable[str]] = None,
    metadatas: Optional[Iterable[Dict[str, Any]]] = None,
    embeddings: Optional[Iterable[Iterable[float]]] = None,
) -> None:
    """Add documents to a collection."""
    collection.add(
        ids=list(ids),
        documents=list(documents) if documents else None,
        metadatas=list(metadatas) if metadatas else None,
        embeddings=list(embeddings) if embeddings else None,
    )


def get_by_ids(collection: Collection, ids: Iterable[str]) -> Dict[str, Any]:
    """Fetch items by IDs using Chroma's get API."""
    return collection.get(ids=list(ids))


def query_by_metadata(
    collection: Collection,
    where: Dict[str, Any],
    limit: int = 10,
) -> Dict[str, Any]:
    """Query documents using metadata filters only."""
    return collection.get(where=where, limit=limit)
