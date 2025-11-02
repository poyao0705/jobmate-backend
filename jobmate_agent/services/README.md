# Services Package

This package contains all business logic services organized by domain for the Jobmate Agent application.

## Structure

```
services/
├── __init__.py                 # Main package exports
├── README.md                   # This file
├── document_processor.py       # Core AI services (chunking, embeddings)
└── resume_management/          # Resume-specific operations
    ├── __init__.py
    ├── resume_storage_service.py
    ├── resume_pipeline.py
    └── ingest.py
```

## Services Overview

### Core AI Services

#### DocumentProcessor (`document_processor.py`)
Core AI service for document processing:
- Text chunking with multiple strategies (recursive, markdown)
- Embedding generation using OpenAI models
- Vector storage in ChromaDB
- Semantic search and retrieval
- Document statistics and management
- **Generic service** that works for resumes, jobs, contracts, and any documents

### Resume Management (`resume_management/`)

#### ResumeStorageService (`resume_storage_service.py`)
Handles resume file storage operations:
- Upload files directly to S3
- Save upload completion to database
- Generate download URLs
- Delete files from S3

#### ResumePipeline (`resume_pipeline.py`)
Complete resume processing workflow:
- File upload + parsing + chunking + embedding
- Error handling and rollback
- Search and statistics functionality

#### File Parsing (`ingest.py`)
Utilities for parsing different file formats:
- PDF parsing with pypdf
- DOCX parsing with python-docx
- TXT file handling with encoding detection
- Text normalization and cleaning

## Usage Examples

### Complete Resume Processing (Recommended)

```python
from jobmate_agent.services import ResumePipeline

# Process uploaded file through complete pipeline
pipeline = ResumePipeline()
result = pipeline.process_uploaded_file(file, user_id)

if result["success"]:
    print(f"Created {result['chunks_created']} chunks for resume {result['resume_id']}")
```

### Quick Processing (Convenience Function)

```python
from jobmate_agent.services import process_resume_file_complete

# One-liner for complete processing
result = process_resume_file_complete(file, user_id)
```

### Individual Services (Advanced Usage)

```python
# Storage operations
from jobmate_agent.services import ResumeStorageService
resume_service = ResumeStorageService()
upload_result = resume_service.upload_file_to_s3(file, user_id)

# AI processing (O*NET skills only in skill-only mode)
from jobmate_agent.services import DocumentProcessor
skills_processor = DocumentProcessor("skills_ontology")
chunks_created = skills_processor.process_document(
    doc_id=f"skill:{skill_id}",
    text=skill_description,
    metadata={"skill_id": skill_id, "skill_type": "skill"}
)
```

### Career Analysis (Skill-Only Mode)

```python
# Career gap analysis using O*NET skills
from jobmate_agent.services import CareerEngine, ChromaClient

onet_client = ChromaClient("skills_ontology")
engine = CareerEngine(onet_client, llm_client)
result = engine.analyze_resume_vs_job(
    resume_id=123,
    job_text="Python developer with React experience",
    job_title="Software Engineer",
    company="Tech Corp"
)
```

## Benefits of This Structure

1. **Clear Separation**: AI services vs. business logic
2. **Reusable**: DocumentProcessor can be used anywhere
3. **Flat Structure**: Simpler, easier to navigate
4. **Accurate Naming**: `resume_management` is more descriptive
5. **Scalable**: Easy to add other management modules (e.g., `job_management/`)

## Future Extensions

This structure makes it easy to add new features:

```
services/
├── document_processor.py       # Core AI service (reusable)
├── resume_management/          # Current implementation
├── job_management/             # Future: Job posting management
└── contract_management/        # Future: Contract processing
```