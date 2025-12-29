# models_fastapi.py
"""
SQLAlchemy models compatible with FastAPI.
These models use SQLAlchemy Core with declarative_base instead of Flask-SQLAlchemy.
"""

from jobmate_agent.extensions_fastapi import Base
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, Integer, String, Text, Boolean, Date, DateTime, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship, Mapped, mapped_column
from pgvector.sqlalchemy import Vector


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    is_premium = Column(Boolean, default=False, nullable=False)
    membership_plan = Column(String(50), default="free")
    membership_renewal_date = Column(Date)
    email_notifications = Column(Boolean, default=True)

    def __repr__(self):
        return f"<User {self.username}>"


class Goal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=True)

    tasks = relationship("Task", back_populates="goal", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Goal {self.id} - {self.title}>"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    done = Column(Boolean, default=False, nullable=False)
    priority = Column(Integer, nullable=True)
    learning_item_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=True)

    goal = relationship("Goal", back_populates="tasks")
    notes = relationship("Note", back_populates="task", cascade="all, delete-orphan")

    def __repr__(self):
        status = "Done" if self.done else "Pending"
        return f"<Task {self.id} - {self.title} ({status})>"


class Note(Base):
    __tablename__ = "notes"
    
    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    user_id = Column(Integer, nullable=False)
    content = Column(Text, default="", nullable=True)
    created_at = Column(DateTime, nullable=True)

    task = relationship("Task", back_populates="notes")

    def __repr__(self):
        return f"<Note {self.id}>"


class Chat(Base):
    __tablename__ = "chats"
    
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=True)
    timestamp = Column(DateTime, nullable=True)
    user_id = Column(String, ForeignKey("user_profiles.id"), nullable=True)
    model = Column(String(50), nullable=True)
    
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Chat {self.id} - {self.title}>"


class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)
    role = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=True)

    chat = relationship("Chat", back_populates="messages")

    def __repr__(self):
        return f"<Message {self.id} - {self.role}>"


class UserProfile(Base):
    __tablename__ = "user_profiles"
    
    id = Column(String, primary_key=True)  # Auth0 sub
    email = Column(String, nullable=True)
    email_verified = Column(Boolean, nullable=True)
    name = Column(String, nullable=True)
    picture = Column(String, nullable=True)
    contact_name = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    contact_phone_number = Column(String, nullable=True)
    contact_location = Column(String, nullable=True)

    resumes = relationship("Resume", back_populates="user")
    skill_gap_reports = relationship("SkillGapReport", back_populates="user")

    def __repr__(self):
        return f"<UserProfile {self.id} - {self.email}>"


class ProcessingRun(Base):
    """Legacy model from Flask for backward compatibility."""
    __tablename__ = "processing_runs"
    
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    llm_model = Column(String(100), nullable=True)
    embed_model = Column(String(100), nullable=True)
    code_version_hash = Column(String(100), nullable=True)
    params_json = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<ProcessingRun {self.id}>"


class Resume(Base):
    __tablename__ = "resumes"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey("user_profiles.id"), nullable=False)
    file_url = Column(String, nullable=True)
    s3_bucket = Column(String, nullable=True)
    s3_key = Column(String, nullable=True)
    original_filename = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)  # BigInt in PostgreSQL but Integer works
    content_type = Column(String, nullable=True)
    parsed_json = Column(JSON, nullable=True)
    vector_doc_id = Column(String, nullable=True)
    processing_run_id = Column(Integer, ForeignKey("processing_runs.id"), nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, nullable=False, default="processing")
    
    # Backward compatibility properties
    @property
    def filename(self):
        return self.original_filename
    
    @property
    def bucket(self):
        return self.s3_bucket

    user = relationship("UserProfile", back_populates="resumes")
    skill_gap_reports = relationship("SkillGapReport", back_populates="resume")

    def __repr__(self):
        return f"<Resume {self.id} - {self.filename}>"


class JobListing(Base):
    __tablename__ = "job_listings"
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    company = Column(String(200), nullable=False)
    location = Column(String(200), nullable=True)
    job_type = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    requirements = Column(Text, nullable=True)
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    salary_currency = Column(String(10), nullable=True)
    external_url = Column(String(500), nullable=True)
    external_id = Column(String(200), nullable=True)
    source = Column(String(100), nullable=True)
    company_logo_url = Column(String(500), nullable=True)
    company_website = Column(String(200), nullable=True)
    required_skills = Column(JSON, nullable=True)
    preferred_skills = Column(JSON, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_remote = Column(Boolean, nullable=False, default=False)
    date_posted = Column(DateTime, nullable=True)
    date_expires = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    vector_doc_id = Column(String(200), nullable=True)
    
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


class Skill(Base):
    __tablename__ = "skills"
    
    id = Column(Integer, primary_key=True)
    skill_id = Column(String, nullable=False)  # stable slug
    name = Column(String, nullable=False)
    taxonomy_path = Column(String, nullable=False)
    vector_doc_id = Column(String, nullable=False)
    framework = Column(String, nullable=False, default="ONET")
    external_id = Column(String, nullable=True)
    meta_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=True)
    onet_soc_code = Column(String(10), nullable=True)
    occupation_title = Column(String(150), nullable=True)
    commodity_title = Column(String(150), nullable=True)
    hot_tech = Column(Boolean, nullable=False, default=False)
    in_demand = Column(Boolean, nullable=False, default=False)
    skill_type = Column(String(50), nullable=True, default="skill")

    def __repr__(self):
        return f"<Skill {self.id} - {self.name}>"


class SkillGapReport(Base):
    __tablename__ = "skill_gap_reports"
    
    id = Column(Integer, primary_key=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False)
    job_listing_id = Column(Integer, ForeignKey("job_listings.id"), nullable=False)
    matched_skills_json = Column(JSON, nullable=False)
    missing_skills_json = Column(JSON, nullable=False)
    weak_skills_json = Column(JSON, nullable=True)
    score = Column(Float, nullable=False)
    report_note_id = Column(Integer, nullable=True)
    processing_run_id = Column(Integer, ForeignKey("processing_runs.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=True)
    user_id = Column(String, ForeignKey("user_profiles.id"), nullable=False)
    resume_skills_json = Column(JSON, nullable=True)
    analysis_version = Column(String, nullable=True)
    analysis_json = Column(JSON, nullable=True)

    user = relationship("UserProfile", back_populates="skill_gap_reports")
    resume = relationship("Resume", back_populates="skill_gap_reports")

    def __repr__(self):
        return f"<SkillGapReport {self.id}>"


class JobCollection(Base):
    __tablename__ = "job_collections"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey("user_profiles.id"), nullable=False)
    job_listing_id = Column(Integer, ForeignKey("job_listings.id"), nullable=False)
    added_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<JobCollection {self.id} - User:{self.user_id} Job:{self.job_id}>"
