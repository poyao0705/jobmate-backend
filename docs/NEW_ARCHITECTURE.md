# NEW ARCHITECHTURE

```
/jobmate_backend/
├── app/
│   ├── __init__.py             # App Factory (create_app)
│   ├── extensions.py           # DB, Migrate, Cors, OpenAI Client init
│   ├── config.py               # Env vars (API Keys, Database URL)
│   │
│   ├── models.py               # DATABASE SCHEMAS
│   │                           # (Skill, SkillAlias, Resume, JobListing, Report)
│   │
│   ├── dtos.py                 # DATA CLASSES (New!)
│   │                           # (SkillMatchResult, ExtractedSkillItem)
│   │
│   ├── api/                    # INTERFACE LAYER (Flask Blueprints)
│   │   ├── __init__.py
│   │   ├── resumes.py          # Endpoints: Upload & Parse
│   │   ├── jobs.py             # Endpoints: Search & Save
│   │   └── chat.py             # Endpoints: Stream Chat
│   │
│   ├── services/               # BUSINESS LOGIC LAYER
│   │   ├── __init__.py
│   │   ├── skill_service.py    # <--- CORE: Hybrid Search, Embedding, Normalization
│   │   ├── resume_service.py   # Orchestrator: Calls Parser -> Chain -> SkillService
│   │   ├── report_service.py   # Logic: Gap Analysis, Math, Markdown generation
│   │   └── job_service.py      # Logic: Job fetching, saving
│   │
│   ├── chains/                 # LLM LOGIC (Prompts & Extractors)
│   │   ├── __init__.py
│   │   └── extraction.py       # LangChain definitions for Skill Extraction
│   │
│   ├── utils/                  # HELPERS
│   │   ├── __init__.py
│   │   └── pdf_parser.py       # Pure text extraction (PyPDF/Unstructured)
│   │
│   ├── agent/                  # THE "BRAIN" (LangGraph)
│   │   ├── __init__.py
│   │   ├── state.py            # AgentState (resume_id, job_id, messages)
│   │   ├── graph.py            # The StateGraph Definition
│   │   └── nodes/
│   │       ├── agent_node.py   # The LLM decision maker
│   │       └── tool_node.py    # Prebuilt ToolNode
│   │
│   └── tools/                  # THE "HANDS" (Agent Tools)
│       ├── __init__.py
│       ├── report_tools.py     # Tool: get_or_create_gap_report
│       └── profile_tools.py    # Tool: add_skills_from_chat
│
├── data/                       # Local storage for temp uploads
├── run.py                      # Entry point
└── requirements.txt
```