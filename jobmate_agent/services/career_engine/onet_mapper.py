from __future__ import annotations

import logging
import os
import numpy as np
from typing import Any, Dict, List, Set

from .config import config

logger = logging.getLogger(__name__)


class OnetMapper:
    def __init__(self, onet_chroma: Any):
        self.chroma = onet_chroma

        # Use centralized configuration
        self.config = config.match_strategy
        self.strategy = self.config.strategy
        self.topk = self.config.topk
        self.min_score = self.config.min_score
        self.margin = self.config.margin
        self.static_threshold = self.config.static_threshold

        # Log strategy initialization
        logger.info(
            f"OnetMapper initialized with strategy='{self.strategy}', "
            f"topk={self.topk}, jd_q={self.config.jd_q}, resume_q={self.config.resume_q}, "
            f"jd_floor={self.config.jd_floor}, resume_floor={self.config.resume_floor}, "
            f"lexical_guard={self.config.lexical_guard}"
        )

        # One-time warning for static strategy users
        if self.strategy == "static":
            logger.warning(
                "Using 'static' strategy with fixed threshold. Consider migrating to "
                "'quantile' strategy for better per-JD adaptation. Set ONET_MATCH_STRATEGY=quantile"
            )

    def map_tokens(
        self,
        tokens: List[str],
        k: int = None,
        source_type: str = "jd",
        source_text: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Map skill tokens to O*NET skills using adaptive filtering.

        Args:
            tokens: List of skill tokens to map
            k: Number of top results to retrieve (overrides self.topk if provided)
            source_type: "jd" or "resume" to determine threshold floor
            source_text: Original text for literal-text validation

        Returns:
            List of mapped skills with metadata and scores
        """
        out: List[Dict[str, Any]] = []
        seen: Set[str] = set()
        diagnostics: List[Dict[str, Any]] = []

        # Use provided k or default to configured topk
        search_k = k if k is not None else self.topk

        for t in self._normalize(tokens):
            hits = self.chroma.search(t, k=search_k, where={"skill_type": "skill"})

            if hits:
                logger.debug(
                    f"Token '{t}': {len(hits)} raw hits, top score: {hits[0].get('score')}"
                )

            # Apply adaptive filtering with source-specific thresholds
            filter_result = self._filter_hits(hits, t, source_type, source_text)
            diagnostics.append(filter_result["diagnostics"])

            diag = filter_result["diagnostics"]
            if diag["accepted_count"] > 0:
                logger.debug(
                    f"  Accepted {diag['accepted_count']} hits (cutoff: {diag['cutoff_used']})"
                )
            if diag["dropped_count"] > 0:
                logger.debug(f"  Dropped {diag['dropped_count']} hits")
            if diag["ambiguous_count"] > 0:
                logger.debug(f"  Marked {diag['ambiguous_count']} as ambiguous")

            # Process accepted hits with literal-text guard
            literal_rejected = 0
            for h in filter_result["accepted"]:
                meta = h.get("metadata") or {}
                sid = meta.get("skill_id")
                if sid and sid not in seen:
                    # Apply literal-text guard to block phantom O*NET examples
                    if self._passes_literal_text_guard(
                        t, meta.get("name", ""), source_text
                    ):
                        seen.add(sid)
                        out.append({"token": t, "match": meta, "score": h["score"]})
                    else:
                        logger.debug(
                            f"  Rejected '{meta.get('name')}' - not found in source text"
                        )
                        literal_rejected += 1

            # Update diagnostics with literal-text rejection count
            if literal_rejected > 0:
                filter_result["diagnostics"]["literal_text_rejected"] = literal_rejected

        # Store diagnostics for later retrieval
        self._last_mapping_diagnostics = diagnostics

        # Log summary of literal-text guard rejections
        total_rejected = sum(
            1 for d in diagnostics if d.get("literal_text_rejected", 0) > 0
        )
        if total_rejected > 0:
            logger.debug(
                f"Literal-text guard rejected {total_rejected} phantom matches for {source_type} tokens"
            )

        return out

    def map_tasks(
        self, responsibilities: List[str], k: int = None, source_text: str = None
    ) -> List[Dict[str, Any]]:
        """
        Map responsibility text to O*NET skills using adaptive filtering.

        Args:
            responsibilities: List of responsibility texts to map
            k: Number of top results to retrieve (overrides self.topk if provided)
            source_text: Original text for literal-text validation

        Returns:
            List of mapped skills with metadata and scores
        """
        out: List[Dict[str, Any]] = []
        seen: Set[str] = set()
        diagnostics: List[Dict[str, Any]] = []

        # Use provided k or default to configured topk
        search_k = k if k is not None else self.topk

        for r in self._normalize(responsibilities):
            hits = self.chroma.search(r, k=search_k, where={"skill_type": "skill"})

            # Apply adaptive filtering with task-specific thresholds
            filter_result = self._filter_hits(hits, r, "task", source_text)
            diagnostics.append(filter_result["diagnostics"])

            # Process accepted hits with literal-text guard
            literal_rejected = 0
            for h in filter_result["accepted"]:
                meta = h.get("metadata") or {}
                sid = meta.get("skill_id")
                if sid and sid not in seen:
                    # Apply literal-text guard to block phantom O*NET examples
                    if self._passes_literal_text_guard(
                        r, meta.get("name", ""), source_text
                    ):
                        seen.add(sid)
                        out.append({"text": r, "match": meta, "score": h["score"]})
                    else:
                        logger.debug(
                            f"  Rejected '{meta.get('name')}' - not found in source text"
                        )
                        literal_rejected += 1

            # Update diagnostics with literal-text rejection count
            if literal_rejected > 0:
                filter_result["diagnostics"]["literal_text_rejected"] = literal_rejected

        # Store diagnostics for later retrieval
        self._last_task_mapping_diagnostics = diagnostics
        return out

    def _filter_hits(
        self,
        hits: List[Dict[str, Any]],
        token: str,
        source_type: str = "jd",
        source_text: str = None,
    ) -> Dict[str, Any]:
        """
        Filter hits based on the configured strategy with adaptive thresholds and literal-text guard.

        Args:
            hits: List of search hits to filter
            token: Original token being mapped
            source_type: "jd", "resume", or "task" to determine threshold floor
            source_text: Original text for literal-text validation

        Returns:
            Dict with 'accepted', 'dropped', 'ambiguous' lists and diagnostics
        """
        if not hits:
            return {
                "accepted": [],
                "dropped": [],
                "ambiguous": [],
                "diagnostics": {
                    "token": token,
                    "total_hits": 0,
                    "accepted_count": 0,
                    "dropped_count": 0,
                    "ambiguous_count": 0,
                    "cutoff_used": None,
                    "strategy": self.strategy,
                },
            }

        # Sort hits by score (descending)
        sorted_hits = sorted(hits, key=lambda h: h.get("score", 0), reverse=True)
        scores = [h["score"] for h in sorted_hits]

        if self.strategy == "static":
            # Use fixed threshold
            cutoff = self.static_threshold
            accepted = [h for h in sorted_hits if h["score"] >= cutoff]
            dropped = [h for h in sorted_hits if h["score"] < cutoff]
            ambiguous = []

        elif self.strategy == "margin":
            # Margin test: require gap between top-1 and top-2
            if len(sorted_hits) < 2:
                accepted = (
                    sorted_hits
                    if sorted_hits and sorted_hits[0]["score"] >= self.min_score
                    else []
                )
                dropped = [h for h in sorted_hits if h not in accepted]
                ambiguous = []
            else:
                s1, s2 = sorted_hits[0]["score"], sorted_hits[1]["score"]
                if (s1 - s2) >= self.margin and s1 >= self.min_score:
                    accepted = [sorted_hits[0]]
                    dropped = sorted_hits[1:]
                    ambiguous = []
                else:
                    accepted = []
                    dropped = []
                    ambiguous = sorted_hits  # All hits are ambiguous
            cutoff = self.min_score

        else:  # quantile strategy (default)
            # Calculate adaptive quantile-based cutoff with source-specific floors
            floor = self._get_floor_for_source_type(source_type)
            quantile_q = self._get_quantile_for_source_type(source_type)

            if len(scores) == 0:
                cutoff = floor
            else:
                # Use numpy quantile for robust calculation
                quantile_cutoff = np.quantile(scores, quantile_q)
                cutoff = max(floor, quantile_cutoff)

                logger.debug(
                    f"  Adaptive quantile: source={source_type}, q={quantile_q}, floor={floor}, "
                    f"n_scores={len(scores)}, quantile_cutoff={quantile_cutoff}, final_cutoff={cutoff}"
                )

            # Apply normal filtering based on cutoff (margin test disabled for now)
            accepted = [h for h in sorted_hits if h["score"] >= cutoff]
            dropped = [h for h in sorted_hits if h["score"] < cutoff]
            ambiguous = []

        return {
            "accepted": accepted,
            "dropped": dropped,
            "ambiguous": ambiguous,
            "diagnostics": {
                "token": token,
                "total_hits": len(hits),
                "accepted_count": len(accepted),
                "dropped_count": len(dropped),
                "ambiguous_count": len(ambiguous),
                "cutoff_used": cutoff,
                "strategy": self.strategy,
                "top_scores": scores[:3] if scores else [],
            },
        }

    def get_strategy_params(self) -> Dict[str, Any]:
        """Return current strategy configuration for persistence."""
        return {
            "onet_match_strategy": self.strategy,
            "topk": self.topk,
            "q": self.q,
            "min_score": self.min_score,
            "margin": self.margin,
            "static_threshold": self.static_threshold,
            "ambiguity_policy": "alias_then_context_then_llm",
        }

    def get_last_mapping_diagnostics(self) -> Dict[str, Any]:
        """Return diagnostics from the last mapping operation."""
        skill_diagnostics = getattr(self, "_last_mapping_diagnostics", [])
        task_diagnostics = getattr(self, "_last_task_mapping_diagnostics", [])

        # Aggregate diagnostics
        total_tokens = len(skill_diagnostics)
        total_tasks = len(task_diagnostics)
        total_accepted = sum(
            d.get("accepted_count", 0) for d in skill_diagnostics + task_diagnostics
        )
        total_dropped = sum(
            d.get("dropped_count", 0) for d in skill_diagnostics + task_diagnostics
        )
        total_ambiguous = sum(
            d.get("ambiguous_count", 0) for d in skill_diagnostics + task_diagnostics
        )

        # Calculate average cutoff
        cutoffs = [
            d.get("cutoff_used")
            for d in skill_diagnostics + task_diagnostics
            if d.get("cutoff_used") is not None
        ]
        avg_cutoff = sum(cutoffs) / len(cutoffs) if cutoffs else None

        return {
            "total_tokens_processed": total_tokens,
            "total_tasks_processed": total_tasks,
            "total_accepted": total_accepted,
            "total_dropped": total_dropped,
            "total_ambiguous": total_ambiguous,
            "average_cutoff": avg_cutoff,
            "strategy": self.strategy,
            "skill_diagnostics": skill_diagnostics,
            "task_diagnostics": task_diagnostics,
        }

    def _normalize(self, arr: List[str]) -> List[str]:
        return [a.strip() for a in (arr or []) if a and a.strip()]

    def _get_floor_for_source_type(self, source_type: str) -> float:
        """Get the minimum threshold floor for the given source type."""
        return self.config.get_floor_for_source_type(source_type)

    def _get_quantile_for_source_type(self, source_type: str) -> float:
        """Get the quantile parameter for the given source type."""
        return self.config.get_quantile_for_source_type(source_type)

    def _passes_literal_text_guard(
        self, token: str, match_name: str, source_text: str
    ) -> bool:
        """
        Check if either the original token or matched name appears literally in source text.
        This prevents phantom O*NET technology examples from being accepted.
        """
        if not self.config.lexical_guard or not source_text:
            return True  # No guard if disabled or no source text provided

        text_lc = source_text.lower()
        token_lc = token.lower()
        match_lc = match_name.lower()

        # Accept if either the original token or matched name appears in source text
        return (token_lc in text_lc) or (match_lc in text_lc)
