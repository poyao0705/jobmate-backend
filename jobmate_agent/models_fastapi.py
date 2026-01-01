# models_fastapi.py
"""
SQLModel models for FastAPI.
Clean, type-safe ORM models with integrated Pydantic validation.
"""

from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, JSON, DateTime, String as SQLString, Text as SQLText
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(max_length=80, unique=True, nullable=False, index=True)
    email: str = Field(max_length=120, unique=True, nullable=False, index=True)
    password_hash: str = Field(max_length=200, nullable=False)
    is_premium: bool = Field(default=False, nullable=False)
    membership_plan: str = Field(default="free", max_length=50)
    membership_renewal_date: Optional[date] = None
    email_notifications: bool = Field(default=True)

    def __repr__(self):
        return f"<User {self.username}>"


class Goal(SQLModel, table=True):
    __tablename__ = "goals"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(nullable=False)
    title: str = Field(max_length=200, nullable=False)
    description: Optional[str] = Field(default=None, sa_column=Column(SQLText))
    created_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime))

    tasks: List["Task"] = Relationship(back_populates="goal", sa_relationship_kwargs={"cascade": "all, delete-orphan"})

    def __repr__(self):
        return f"<Goal {self.id} - {self.title}>"


class Task(SQLModel, table=True):
    __tablename__ = "tasks"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(nullable=False)
    goal_id: Optional[int] = Field(default=None, foreign_key="goals.id")
    title: str = Field(max_length=200, nullable=False)
    description: Optional[str] = Field(default=None, sa_column=Column(SQLText))
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    done: bool = Field(default=False, nullable=False)
    priority: Optional[int] = None
    learning_item_id: Optional[int] = None
    created_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime))

    goal: Optional["Goal"] = Relationship(back_populates="tasks")
    notes: List["Note"] = Relationship(back_populates="task", sa_relationship_kwargs={"cascade": "all, delete-orphan"})

    def __repr__(self):
        status = "Done" if self.done else "Pending"
        return f"<Task {self.id} - {self.title} ({status})>"


class Note(SQLModel, table=True):
    __tablename__ = "notes"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: Optional[int] = Field(default=None, foreign_key="tasks.id")
    user_id: int = Field(nullable=False)
    content: Optional[str] = Field(default="", sa_column=Column(SQLText))
    created_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime))

    task: Optional["Task"] = Relationship(back_populates="notes")

    def __repr__(self):
        return f"<Note {self.id}>"


class Chat(SQLModel, table=True):
    __tablename__ = "chats"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    title: Optional[str] = Field(default=None, max_length=255)
    timestamp: Optional[datetime] = Field(default=None, sa_column=Column(DateTime))
    user_id: Optional[str] = Field(default=None, foreign_key="user_profiles.id")
    model: Optional[str] = Field(default=None, max_length=50)
    
    messages: List["Message"] = Relationship(back_populates="chat", sa_relationship_kwargs={"cascade": "all, delete-orphan"})

    def __repr__(self):
        return f"<Chat {self.id} - {self.title}>"


class Message(SQLModel, table=True):
    __tablename__ = "messages"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    chat_id: int = Field(foreign_key="chats.id", nullable=False)
    role: str = Field(max_length=50, nullable=False)
    content: str = Field(sa_column=Column(SQLText, nullable=False))
    timestamp: Optional[datetime] = Field(default=None, sa_column=Column(DateTime))

    chat: Optional["Chat"] = Relationship(back_populates="messages")

    def __repr__(self):
        return f"<Message {self.id} - {self.role}>"


class UserProfile(SQLModel, table=True):
    __tablename__ = "user_profiles"
    
    id: str = Field(primary_key=True)  # Auth0 sub
    email: Optional[str] = None
    email_verified: Optional[bool] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone_number: Optional[str] = None
    contact_location: Optional[str] = None

    resumes: List["Resume"] = Relationship(back_populates="user")
    skill_gap_reports: List["SkillGapReport"] = Relationship(back_populates="user")

    def __repr__(self):
        return f"<UserProfile {self.id} - {self.email}>"


class ProcessingRun(SQLModel, table=True):
    """Legacy model from Flask for backward compatibility."""
    __tablename__ = "processing_runs"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime))
    llm_model: Optional[str] = Field(default=None, max_length=100)
    embed_model: Optional[str] = Field(default=None, max_length=100)
    code_version_hash: Optional[str] = Field(default=None, max_length=100)
    params_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    def __repr__(self):
        return f"<ProcessingRun {self.id}>"


class Resume(SQLModel, table=True):
    __tablename__ = "resumes"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user_profiles.id", nullable=False, index=True)
    file_url: Optional[str] = None
    s3_bucket: Optional[str] = None
    s3_key: Optional[str] = None
    original_filename: Optional[str] = None
    file_size: Optional[int] = None
    content_type: Optional[str] = None
    parsed_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    vector_doc_id: Optional[str] = None
    processing_run_id: int = Field(foreign_key="processing_runs.id", nullable=False)
    is_default: bool = Field(default=False, nullable=False)
    created_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    status: str = Field(default="processing", nullable=False)
    
    # Backward compatibility properties
    @property
    def filename(self):
        return self.original_filename
    
    @property
    def bucket(self):
        return self.s3_bucket

    user: Optional["UserProfile"] = Relationship(back_populates="resumes")
    skill_gap_reports: List["SkillGapReport"] = Relationship(back_populates="resume")

    def __repr__(self):
        return f"<Resume {self.id} - {self.filename}>"


class JobListing(SQLModel, table=True):
    __tablename__ = "job_listings"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(max_length=200, nullable=False)
    company: str = Field(max_length=200, nullable=False)
    location: Optional[str] = Field(default=None, max_length=200)
    job_type: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = Field(default=None, sa_column=Column(SQLText))
    requirements: Optional[str] = Field(default=None, sa_column=Column(SQLText))
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = Field(default=None, max_length=10)
    external_url: Optional[str] = Field(default=None, max_length=500)
    external_id: Optional[str] = Field(default=None, max_length=200)
    source: Optional[str] = Field(default=None, max_length=100)
    company_logo_url: Optional[str] = Field(default=None, max_length=500)
    company_website: Optional[str] = Field(default=None, max_length=200)
    required_skills: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    preferred_skills: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    is_active: bool = Field(default=True, nullable=False)
    is_remote: bool = Field(default=False, nullable=False)
    date_posted: Optional[datetime] = Field(default=None, sa_column=Column(DateTime))
    date_expires: Optional[datetime] = Field(default=None, sa_column=Column(DateTime))
    created_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime))
    updated_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime))
    vector_doc_id: Optional[str] = Field(default=None, max_length=200)
    
    # Backward compatibility aliases
    @property
    def url(self):
        return self.external_url
    
    @property
    def posted_date(self):
        return self.date_posted
    
    @property
    def experience_level(self):
        # Could be extracted from requirements if needed
        return None

    def __repr__(self):
        return f"<JobListing {self.id} - {self.title}>"


class Skill(SQLModel, table=True):
    __tablename__ = "skills"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    skill_id: str = Field(nullable=False)  # stable slug
    name: str = Field(nullable=False)
    taxonomy_path: str = Field(nullable=False)
    vector_doc_id: str = Field(nullable=False)
    framework: str = Field(default="ONET", nullable=False)
    external_id: Optional[str] = None
    meta_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime))
    onet_soc_code: Optional[str] = Field(default=None, max_length=10)
    occupation_title: Optional[str] = Field(default=None, max_length=150)
    commodity_title: Optional[str] = Field(default=None, max_length=150)
    hot_tech: bool = Field(default=False, nullable=False)
    in_demand: bool = Field(default=False, nullable=False)
    skill_type: Optional[str] = Field(default="skill", max_length=50)

    def __repr__(self):
        return f"<Skill {self.id} - {self.name}>"


class SkillGapReport(SQLModel, table=True):
    __tablename__ = "skill_gap_reports"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    resume_id: int = Field(foreign_key="resumes.id", nullable=False)
    job_listing_id: int = Field(foreign_key="job_listings.id", nullable=False)
    matched_skills_json: Dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    missing_skills_json: Dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    weak_skills_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    score: float = Field(nullable=False)
    report_note_id: Optional[int] = None
    processing_run_id: int = Field(foreign_key="processing_runs.id", nullable=False)
    created_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    user_id: str = Field(foreign_key="user_profiles.id", nullable=False)
    resume_skills_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    analysis_version: Optional[str] = None
    analysis_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    user: Optional["UserProfile"] = Relationship(back_populates="skill_gap_reports")
    resume: Optional["Resume"] = Relationship(back_populates="skill_gap_reports")

    def __repr__(self):
        return f"<SkillGapReport {self.id}>"


class JobCollection(SQLModel, table=True):
    __tablename__ = "job_collections"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user_profiles.id", nullable=False)
    job_listing_id: int = Field(foreign_key="job_listings.id", nullable=False)
    added_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))

    def __repr__(self):
        return f"<JobCollection {self.id} - User:{self.user_id} Job:{self.job_listing_id}>"
