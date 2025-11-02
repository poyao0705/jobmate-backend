"""
Resume processing pipeline for skill-only mode.

This file handles complete resume processing:
1. Upload resume file to S3 (ResumeService)
2. Parse and extract text (ingest utilities)
3. Store raw text in database (no vectorization in skill-only mode)
"""

import logging
from typing import Dict, Any, Optional
from werkzeug.datastructures import FileStorage
import hashlib

from .resume_storage_service import ResumeStorageService
from .ingest import (
    parse_resume_file,
    ResumeParsingError,
    prepare_resume_bytes,
    parse_resume_bytes,
)
from jobmate_agent.models import db, Resume

logger = logging.getLogger(__name__)


class ResumePipeline:
    """
    Complete resume processing pipeline that combines file handling,
    text extraction, and storage (no vectorization in skill-only mode).
    """

    def __init__(self):
        self.resume_service = ResumeStorageService()

    def process_uploaded_file(
        self, file: FileStorage, user_id: str, extract_sections: bool = True
    ) -> Dict[str, Any]:
        """
        Process an uploaded resume file through the complete pipeline.

        Args:
            file: Uploaded file object
            user_id: User ID
            extract_sections: Whether to extract resume sections

        Returns:
            Dictionary with processing results
        """
        try:
            # Single, centralized read with validation
            # TODO: Add validation to check if the file is a valid DOCX file
            if not file.filename.endswith(".docx"):
                raise ResumeParsingError(
                    "Invalid file type. Only DOCX files are allowed."
                )

            file_content, normalized_name, content_type = prepare_resume_bytes(file)
            logger.debug(f"Upload bytes={len(file_content)} (centralized read)")

            # Create new file object for S3 upload only
            from io import BytesIO
            from werkzeug.datastructures import FileStorage

            s3_file = FileStorage(
                stream=BytesIO(file_content),
                filename=normalized_name,
                content_type=content_type,
                content_length=len(file_content),
            )

            # Step 1: Upload file to S3 and create database record
            upload_result = self.resume_service.upload_file_to_s3(s3_file, user_id)
            resume_id = upload_result["resume_id"]

            logger.info(f"Uploaded resume_id=%s to S3", resume_id)

            # Step 2: Parse file to extract text
            try:
                parsed_result = parse_resume_bytes(
                    raw_bytes=file_content,
                    filename=normalized_name,
                    content_type=content_type,
                )
                extracted_text = parsed_result.parsed_json["raw_text"]
                warnings = parsed_result.warnings

                logger.debug(
                    f"Extracted text length for resume_id={resume_id}: {len(extracted_text)}"
                )

                # Store minimal parsed metadata (no full raw text) in SQL
                try:
                    parsed_payload = dict(parsed_result.parsed_json or {})
                    parsed_payload["raw_text"] = extracted_text
                    parsed_payload["text_preview"] = extracted_text[:1000]
                    parsed_payload["raw_text_sha256"] = hashlib.sha256(
                        extracted_text.encode("utf-8")
                    ).hexdigest()
                    if warnings:
                        parsed_payload["warnings"] = list(warnings)
                    else:
                        parsed_payload["warnings"] = list(
                            parsed_payload.get("warnings", [])
                        )
                    parsed_payload["page_count"] = parsed_payload.get("page_count", 0)
                    parsed_payload["word_count"] = parsed_payload.get("word_count", 0)

                    resume = Resume.query.get(resume_id)
                    if resume:
                        resume.parsed_json = parsed_payload
                        db.session.commit()
                except Exception as db_exc:
                    logger.warning(
                        f"Failed to persist minimal parsed_json for resume_id={resume_id}: {db_exc}"
                    )

            except ResumeParsingError as e:
                logger.error(f"Parse failed for resume_id={resume_id}: {str(e)}")
                return {
                    "success": False,
                    "error": f"File parsing failed: {str(e)}",
                    "resume_id": resume_id,
                }

            # Mark processing as completed after successful ingest
            try:
                resume = Resume.query.get(resume_id)
                if resume:
                    resume.status = "completed"
                    db.session.commit()
            except Exception as db_exc:
                logger.warning(
                    f"Failed to mark resume_id={resume_id} as completed: {db_exc}"
                )

            # Step 3: Return success result (no vectorization in skill-only mode)
            return {
                "success": True,
                "resume_id": resume_id,
                "text_length": len(extracted_text),
                "warnings": warnings,
                "s3_key": upload_result["s3_key"],
                "bucket": upload_result["bucket"],
            }

        except Exception as e:
            logger.error(f"Resume pipeline failed: {str(e)}")
            return {"success": False, "error": f"Processing pipeline failed: {str(e)}"}

    def _extract_resume_sections(self, text: str) -> Dict[str, str]:
        """
        Extract resume sections (experience, education, skills, etc.).

        This is a placeholder - you'd implement this based on your specific needs.
        You might use regex patterns, NLP libraries, or even LLM-based extraction.
        """
        # Simple section extraction based on common headers
        sections = {}

        # Common resume section headers
        section_headers = [
            "experience",
            "work experience",
            "employment",
            "education",
            "academic background",
            "skills",
            "technical skills",
            "core competencies",
            "projects",
            "personal projects",
            "certifications",
            "certificates",
            "summary",
            "objective",
            "profile",
        ]

        lines = text.split("\n")
        current_section = "other"
        current_content = []

        for line in lines:
            line_lower = line.lower().strip()

            # Check if this line is a section header
            is_header = any(header in line_lower for header in section_headers)

            if is_header and current_content:
                # Save previous section
                sections[current_section] = "\n".join(current_content).strip()
                current_content = []
                current_section = line.strip()
            else:
                current_content.append(line)

        # Add the last section
        if current_content:
            sections[current_section] = "\n".join(current_content).strip()

        return sections

    def search_resume_content(
        self, query: str, user_id: str, resume_id: Optional[int] = None, k: int = 10
    ) -> Dict[str, Any]:
        """
        Search through resume content using vector similarity.

        Args:
            query: Search query
            user_id: User ID to filter results
            resume_id: Specific resume ID (optional)
            k: Number of results to return

        Returns:
            Search results with metadata
        """
        try:
            # Build filter for user's resumes
            filter_dict = {"user_id": user_id}
            if resume_id:
                filter_dict["resume_id"] = resume_id

            # Search for similar content with automatic user isolation and relevance scores
            results_with_scores = self.document_processor.search_with_relevance(
                query=query, k=k, user_id=user_id
            )

            # Format results with relevance scores
            formatted_results = []
            for doc, relevance_score in results_with_scores:
                formatted_results.append(
                    {
                        "content": doc.page_content,
                        "metadata": doc.metadata,
                        "section": doc.metadata.get("section", "unknown"),
                        "chunk_id": doc.metadata.get("chunk_id", 0),
                        "relevance_score": round(
                            relevance_score, 3
                        ),  # Round to 3 decimal places
                    }
                )

            return {
                "success": True,
                "query": query,
                "results": formatted_results,
                "total_results": len(formatted_results),
            }

        except Exception as e:
            logger.error(f"Resume search failed: {str(e)}")
            return {"success": False, "error": f"Search failed: {str(e)}"}

    def get_resume_stats(self, resume_id: int) -> Dict[str, Any]:
        """
        Get statistics for a resume.

        Args:
            resume_id: Resume ID

        Returns:
            Resume statistics
        """
        try:
            stats = self.document_processor.get_document_stats(f"resume:{resume_id}")
            return {"success": True, "resume_id": resume_id, "stats": stats}
        except Exception as e:
            logger.error(f"Failed to get resume stats: {str(e)}")
            return {"success": False, "error": f"Stats retrieval failed: {str(e)}"}


# Convenience function for quick processing
def process_resume_file_complete(file: FileStorage, user_id: str) -> Dict[str, Any]:
    """
    Convenience function to process a resume file through the complete pipeline.

    Args:
        file: Uploaded file object
        user_id: User ID

    Returns:
        Processing results
    """
    pipeline = ResumePipeline()
    return pipeline.process_uploaded_file(file, user_id)
