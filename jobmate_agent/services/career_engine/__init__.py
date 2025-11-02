"""
Career Engine Package

This package contains all services related to the skill-only Career Engine system:
- career_engine.py: Main orchestrator
- chroma_client.py: ChromaDB wrapper for O*NET skills
- gap_analyzer.py: Skill gap analysis and scoring
- llm_extractor.py: LLM-based skill extraction
- onet_mapper.py: O*NET skill mapping
- report_renderer.py: Markdown report generation
"""

from typing import Any, Optional
from .career_engine import CareerEngine
from .chroma_client import ChromaClient
from .gap_analyzer import GapAnalyzer
from .llm_extractor import LLMExtractor
from .onet_mapper import OnetMapper
from .report_renderer import ReportRenderer


def get_career_engine(
    collection_name: str = "skills_ontology", llm: Any = None, use_real_llm: bool = True
) -> CareerEngine:
    """
    Factory function to create a CareerEngine with sensible defaults.

    By default, creates a real LLM using ChatOpenAI if OPENAI_API_KEY is set.
    This gives you proper skill level extraction instead of test mode defaults.

    Args:
        collection_name: ChromaDB collection name (default: "skills_ontology")
        llm: Explicit LLM to use (overrides all defaults)
        use_real_llm: If True and llm=None, attempt to create real LLM (default: True)
                      If False, uses test mode with keyword extraction only

    Returns:
        Configured CareerEngine instance

    Examples:
        # Using defaults (real LLM if OPENAI_API_KEY is set)
        engine = get_career_engine()

        # Explicitly use real LLM
        engine = get_career_engine(use_real_llm=True)

        # Test mode (no real LLM, keyword extraction only)
        engine = get_career_engine(use_real_llm=False)

        # Custom LLM
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model="gpt-4o")
        engine = get_career_engine(llm=llm)
    """
    from .config import config
    from langchain_openai import ChatOpenAI

    # Create Chroma client
    try:
        onet_chroma = ChromaClient(collection_name)
    except Exception:
        onet_chroma = None

    # Handle LLM creation
    if llm is not None:
        # Use provided LLM directly
        pass
    elif not use_real_llm or config.extraction.test_mode:
        # Explicitly disable real LLM for test mode
        llm = None
    else:
        # Try to create a real LLM if API key is available
        if config.extraction.openai_api_key:
            llm = ChatOpenAI(
                model=config.extraction.extractor_model,
                max_retries=3,
                model_kwargs={"response_format": {"type": "json_object"}},
            )
        else:
            llm = None

    return CareerEngine(onet_chroma=onet_chroma, llm=llm)


__all__ = [
    "CareerEngine",
    "ChromaClient",
    "GapAnalyzer",
    "LLMExtractor",
    "OnetMapper",
    "ReportRenderer",
    "get_career_engine",  # New factory function
]
