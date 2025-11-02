"""
Resume service for handling file uploads and S3 operations.
Separated from API layer for better responsibility separation.
Handles S3 operations, presigned URLs, and database operations for resumes.
"""

import os
import uuid
import boto3
import logging
from botocore.exceptions import ClientError
from datetime import datetime
from jobmate_agent.models import db, Resume, ProcessingRun

logger = logging.getLogger(__name__)


class ResumeStorageService:
    """Service class for handling resume file storage and S3 operations."""

    def __init__(self):
        self.s3_bucket = os.getenv("S3_BUCKET_NAME", "jobmate-agent-bucket")
        self.aws_region = os.getenv("AWS_REGION", "ap-southeast-2")
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=self.aws_region,
        )

    def upload_file_to_s3(self, file, user_id: str) -> dict:
        """
        Upload file directly to S3 through backend.

        Args:
            file: Flask file object
            user_id: User ID for organizing files

        Returns:
            dict: Contains resume_id, s3_key, bucket, and success message
        """
        try:
            # Generate unique filename
            file_extension = os.path.splitext(file.filename)[1]
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            s3_key = f"resumes/{user_id}/{unique_filename}"

            # Upload file to S3
            self.s3_client.upload_fileobj(
                file,
                self.s3_bucket,
                s3_key,
                ExtraArgs={
                    "ContentType": file.content_type or "application/octet-stream"
                },
            )

            # Create a minimal processing run (required by schema)
            processing_run = ProcessingRun(
                created_at=datetime.utcnow(),
                llm_model="not-set",
                embed_model="not-set",
                code_version_hash="upload-only",
                params_json={"note": "Upload only - no processing yet"},
            )
            db.session.add(processing_run)
            db.session.flush()  # Get the ID

            # First, unset any existing default resume for this user
            Resume.query.filter_by(user_id=user_id).update({"is_default": False})

            # Create resume record (automatically set as default)
            resume = Resume(
                user_id=user_id,
                original_filename=file.filename,
                s3_key=s3_key,
                s3_bucket=self.s3_bucket,
                file_size=file.content_length or 0,
                content_type=file.content_type or "application/octet-stream",
                processing_run_id=processing_run.id,
                is_default=True,  # Every new upload becomes the default
            )
            db.session.add(resume)
            db.session.commit()

            return {
                "resume_id": resume.id,
                "message": "Resume uploaded successfully",
                "s3_key": s3_key,
                "bucket": self.s3_bucket,
            }

        except ClientError as e:
            raise Exception(f"Failed to upload to S3: {str(e)}")

    def save_upload_completion(
        self,
        user_id: str,
        s3_key: str,
        s3_bucket: str,
        original_filename: str,
        file_size: int,
        content_type: str,
    ) -> dict:
        """
        Handle file upload completion and save to database.

        Args:
            user_id: User ID
            s3_key: S3 object key
            s3_bucket: S3 bucket name
            original_filename: Original filename
            file_size: File size in bytes
            content_type: MIME type

        Returns:
            dict: Contains resume_id, s3_key, bucket, and success message
        """
        try:
            # Create processing run
            processing_run = ProcessingRun(
                created_at=datetime.utcnow(),
                llm_model="gpt-4",
                embed_model="text-embedding-ada-002",
                code_version_hash="v1.0.0",
                params_json={"max_tokens": 1000},
            )
            db.session.add(processing_run)
            db.session.flush()  # Get the ID

            # Create resume record with S3 metadata
            resume = Resume(
                user_id=user_id,
                s3_bucket=s3_bucket,
                s3_key=s3_key,
                original_filename=original_filename,
                file_size=file_size,
                content_type=content_type,
                file_url=f"s3://{s3_bucket}/{s3_key}",  # Legacy field for compatibility
                parsed_json={"status": "uploaded", "filename": original_filename},
                vector_doc_id=str(uuid.uuid4()),
                processing_run_id=processing_run.id,
                is_default=False,  # Will be set to True if this is the first resume
            )
            db.session.add(resume)
            db.session.flush()  # Get the ID

            # If this is the user's first resume, make it default
            existing_resumes = Resume.query.filter_by(user_id=user_id).count()
            if existing_resumes == 1:  # This is the first resume
                resume.is_default = True

            db.session.commit()

            return {
                "resume_id": resume.id,
                "message": "File uploaded and saved successfully",
                "s3_key": s3_key,
                "bucket": s3_bucket,
            }

        except Exception as e:
            db.session.rollback()
            raise Exception(f"Failed to save upload: {str(e)}")

    def generate_download_url(self, resume: Resume) -> dict:
        """
        Generate a presigned URL for downloading/viewing a resume file.

        Args:
            resume: Resume model instance

        Returns:
            dict: Contains download_url, filename, file_size, content_type, and expires_in
        """
        try:
            if not resume.s3_bucket or not resume.s3_key:
                raise Exception("Resume file not found in S3")

            # Generate presigned URL for GET operation
            presigned_url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": resume.s3_bucket,
                    "Key": resume.s3_key,
                },
                ExpiresIn=3600,  # URL expires in 1 hour
            )

            return {
                "download_url": presigned_url,
                "filename": resume.original_filename,
                "file_size": resume.file_size,
                "content_type": resume.content_type,
                "expires_in": 3600,
            }

        except ClientError as e:
            raise Exception(f"Failed to generate download URL: {str(e)}")

    def delete_resume_from_s3(self, s3_bucket: str, s3_key: str) -> bool:
        """
        Delete a resume file from S3.

        Args:
            s3_bucket: S3 bucket name
            s3_key: S3 object key

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not s3_bucket or not s3_key:
                return False

            self.s3_client.delete_object(Bucket=s3_bucket, Key=s3_key)
            logger.info(f"Deleted file from S3: s3://{s3_bucket}/{s3_key}")
            return True

        except ClientError as e:
            logger.warning(f"Failed to delete file from S3: {str(e)}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error deleting from S3: {str(e)}")
            return False
