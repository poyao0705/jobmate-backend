from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings


class ChromaClient:
    def __init__(
        self, collection_name: str = "skills_ontology", embeddings: Optional[Any] = None
    ):
        # Prefer provided embeddings, otherwise choose based on environment.
        # In test/offline mode (no OPENAI_API_KEY or SKILL_EXTRACTOR_TEST=1),
        # use deterministic fake embeddings to avoid network calls while keeping
        # dimensions compatible with the persisted collection.
        if embeddings is not None:
            self.embeddings = embeddings
        else:
            openai_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY_BETA")
            test_mode = (os.getenv("SKILL_EXTRACTOR_TEST") or "0") == "1" or os.getenv(
                "CHROMA_OFFLINE"
            ) == "1"
            if not openai_key or test_mode:
                try:
                    # LangChain's FakeEmbeddings allows us to set a fixed output size.
                    from langchain.embeddings.fake import FakeEmbeddings

                    # Match the embedding size used elsewhere (text-embedding-3-large -> 3072)
                    self.embeddings = FakeEmbeddings(size=3072)
                except Exception:
                    # As a last resort, fall back to OpenAIEmbeddings (may attempt network)
                    self.embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
            else:
                self.embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
        self.collection_name = collection_name

        # Use the same persist directory as DocumentProcessor
        persist_directory = os.getenv("CHROMA_PERSIST_DIR", "./instance/chroma")
        self.persist_directory = persist_directory

        self.store = Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings,
            persist_directory=persist_directory,
        )

    def search(
        self, text: str, k: int, where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        if not text:
            return []
        results = self.store.similarity_search_with_score(
            query=text, k=k, filter=where or None
        )
        out: List[Dict[str, Any]] = []
        for doc, score in results:
            out.append(
                {
                    "document": doc.page_content,
                    "metadata": getattr(doc, "metadata", {}) or {},
                    "score": 1.0 - float(score),  # normalize to higher-is-better
                }
            )
        return out

    def health_check(self) -> Dict[str, Any]:
        """Return basic diagnostics about the underlying Chroma collection."""

        info: Dict[str, Any] = {
            "collection": self.collection_name,
            "persist_directory": self.persist_directory,
        }

        collection = getattr(self.store, "_collection", None)
        if collection is None:
            info["status"] = "no_collection_handle"
            return info

        try:
            count = collection.count() if hasattr(collection, "count") else None
            info["document_count"] = count
            info["status"] = "ok" if count and count > 0 else "empty"
            metadata = getattr(collection, "metadata", None)
            if callable(metadata):
                try:
                    info["metadata"] = metadata()
                except Exception:
                    pass
            elif metadata is not None:
                info["metadata"] = metadata
        except Exception as exc:  # pragma: no cover - defensive
            info["status"] = "error"
            info["error"] = str(exc)
        return info
