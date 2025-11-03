"""
Career Engine Configuration

Centralized configuration for all career engine parameters with environment variable support.
This makes the system production-ready by allowing tuning without code changes.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class MatchStrategy:
    """O*NET matching strategy configuration."""

    # Strategy type
    strategy: str = os.getenv("ONET_MATCH_STRATEGY", "quantile")

    # Search parameters
    topk: int = int(os.getenv("ONET_TOPK", "10"))

    # Quantile settings per source type
    jd_q: float = float(os.getenv("ONET_JD_Q", "0.85"))
    resume_q: float = float(os.getenv("ONET_RESUME_Q", "0.85"))
    task_q: float = float(os.getenv("ONET_TASK_Q", "0.85"))

    # Floor thresholds (safety limits)
    jd_floor: float = float(os.getenv("ONET_JD_FLOOR", "0.40"))
    resume_floor: float = float(os.getenv("ONET_RESUME_FLOOR", "0.30"))
    task_floor: float = float(os.getenv("ONET_TASK_FLOOR", "0.40"))

    # Legacy compatibility
    min_score: float = float(os.getenv("ONET_MIN_SCORE", "0.50"))
    margin: float = float(os.getenv("ONET_MARGIN", "0.15"))
    static_threshold: float = float(os.getenv("ONET_MATCH_THRESHOLD", "0.55"))

    # Guards
    lexical_guard: bool = os.getenv("ONET_LEXICAL_GUARD", "1") == "1"

    def get_quantile_for_source_type(self, source_type: str) -> float:
        """Get quantile parameter for source type."""
        if source_type == "resume":
            return self.resume_q
        elif source_type == "task":
            return self.task_q
        else:  # "jd" or default
            return self.jd_q

    def get_floor_for_source_type(self, source_type: str) -> float:
        """Get floor threshold for source type."""
        if source_type == "resume":
            return self.resume_floor
        elif source_type == "task":
            return self.task_floor
        else:  # "jd" or default
            return self.jd_floor


@dataclass
class ScoreWeights:
    """Gap analysis scoring weights."""

    # Missing skill penalties
    miss: float = float(os.getenv("GE_MISS_W", "0.20"))
    hot: float = float(os.getenv("GE_HOT_W", "0.70"))
    ind: float = float(os.getenv("GE_IN_W", "0.40"))

    # Level gap penalties
    level: float = float(os.getenv("GE_LEVEL_W", "0.90"))
    level_grace: float = float(os.getenv("GE_LEVEL_GRACE", "0.25"))


@dataclass
class ExtractionConfig:
    """Skill extraction configuration."""

    # Test mode
    test_mode: bool = os.getenv("SKILL_EXTRACTOR_TEST", "0") == "1"

    # LLM settings
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    extractor_model: str = os.getenv("EXTRACTOR_MODEL", "gpt-4o-mini")

    # Nice-to-have parsing
    parse_nice_to_have: bool = os.getenv("PARSE_NICE_TO_HAVE", "1") == "1"

    # Extractor guardrails
    strict_json: bool = os.getenv("STRICT_JSON", "1") == "1"
    max_spans_per_skill: int = int(os.getenv("MAX_SPANS_PER_SKILL", "2"))
    cap_nice_to_have: bool = os.getenv("CAP_NICE_TO_HAVE", "1") == "1"


@dataclass
class CareerEngineConfig:
    """Complete career engine configuration."""

    match_strategy: MatchStrategy = None
    score_weights: ScoreWeights = None
    extraction: ExtractionConfig = None

    def __post_init__(self):
        if self.match_strategy is None:
            self.match_strategy = MatchStrategy()
        if self.score_weights is None:
            self.score_weights = ScoreWeights()
        if self.extraction is None:
            self.extraction = ExtractionConfig()

    def to_dict(self) -> dict:
        """Convert to dictionary for persistence."""
        return {
            "match_strategy": {
                "strategy": self.match_strategy.strategy,
                "topk": self.match_strategy.topk,
                "jd_q": self.match_strategy.jd_q,
                "resume_q": self.match_strategy.resume_q,
                "task_q": self.match_strategy.task_q,
                "jd_floor": self.match_strategy.jd_floor,
                "resume_floor": self.match_strategy.resume_floor,
                "task_floor": self.match_strategy.task_floor,
                "min_score": self.match_strategy.min_score,
                "margin": self.match_strategy.margin,
                "static_threshold": self.match_strategy.static_threshold,
                "lexical_guard": self.match_strategy.lexical_guard,
            },
            "score_weights": {
                "miss": self.score_weights.miss,
                "hot": self.score_weights.hot,
                "ind": self.score_weights.ind,
                "level": self.score_weights.level,
                "level_grace": self.score_weights.level_grace,
            },
            "extraction": {
                "test_mode": self.extraction.test_mode,
                "extractor_model": self.extraction.extractor_model,
                "parse_nice_to_have": self.extraction.parse_nice_to_have,
                "strict_json": self.extraction.strict_json,
                "max_spans_per_skill": self.extraction.max_spans_per_skill,
                "cap_nice_to_have": self.extraction.cap_nice_to_have,
            },
        }


# Global configuration instance
config = CareerEngineConfig()
