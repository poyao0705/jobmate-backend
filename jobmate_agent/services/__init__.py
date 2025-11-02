"""
Services package for Jobmate Agent.

This package contains all business logic services organized by domain:
- document_processor: Core AI services (chunking, embeddings, vector operations)
- resume_management: Resume-specific operations (storage, pipelines, parsing)
"""

# Core AI services
from .document_processor import (
    DocumentProcessor,
    process_job_description,
)

# Resume management services
from .resume_management import (
    ResumeStorageService,
    ResumePipeline,
    parse_resume_file,
    ResumeIngestResult,
    ResumeParsingError,
)

__all__ = [
    # Core AI services
    "DocumentProcessor",
    "process_job_description",
    # Resume management services
    "ResumeStorageService",
    "ResumePipeline",
    "parse_resume_file",
    "ResumeIngestResult",
    "ResumeParsingError",
]
