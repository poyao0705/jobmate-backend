# Career Engine - Quick Start

## Using the Factory Function (Recommended)

The easiest way to create a CareerEngine is using the factory function:

```python
from jobmate_agent.services.career_engine import get_career_engine

# Default: Uses real LLM if OPENAI_API_KEY is set
engine = get_career_engine()

# Analyze a resume vs job (using job text)
result = engine.analyze_resume_vs_job(
    resume_id=1,
    job_text="We need Python, React.js, AWS, Docker. Nice to have: Kubernetes.",
    job_title="Senior Software Engineer",
    company="TechCorp"
)

# OR analyze using job_id from database
result = engine.analyze_resume_vs_job(
    resume_id=1,
    job_id=42  # Uses job from job_listings table
)

print(result["report_md"])
```

## Configuration

The factory function automatically:
1. ✅ Creates ChromaClient for O*NET skills (`skills_ontology` collection)
2. ✅ Creates real LLM if `OPENAI_API_KEY` environment variable is set
3. ✅ Falls back to test mode if no API key (keyword extraction only)
4. ✅ Handles errors gracefully

## Options

```python
# Test mode (no real LLM, faster for development)
engine = get_career_engine(use_real_llm=False)

# Custom LLM
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model="gpt-4o", temperature=0)
engine = get_career_engine(llm=llm)

# Custom collection
engine = get_career_engine(collection_name="custom_skills")
```

## Environment Variables

Set these in your `.env` file:

```bash
# Required for real LLM extraction
OPENAI_API_KEY=sk-...

# Optional: Configure extraction model
EXTRACTOR_MODEL=gpt-4o-mini

# Optional: Test mode (no API calls)
SKILL_EXTRACTOR_TEST=0  # Set to 1 for test mode
```

## See Also

- `docs/CAREER_ENGINE_GUIDE.md` - Comprehensive guide
- `docs/methodology/CAREER_ENGINE.md` - Technical details

