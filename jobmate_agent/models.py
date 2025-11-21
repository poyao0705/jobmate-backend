# models.py

from jobmate_agent.extensions import db
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, String, Text
from pgvector.sqlalchemy import Vector  # Requires 'pip install pgvector'


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    is_premium = db.Column(db.Boolean, default=False, nullable=False)

    # Membership fields
    membership_plan = db.Column(db.String(50), default="free")
    membership_renewal_date = db.Column(db.Date)

    # Settings fields
    email_notifications = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f"<User {self.username}>"


class Goal(db.Model):
    __tablename__ = "goals"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)  # 新增描述字段
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tasks = db.relationship(
        "Task", backref="goal", cascade="all, delete-orphan", lazy=True
    )

    def __repr__(self):
        return f"<Goal {self.id} - {self.title}>"


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    goal_id = db.Column(db.Integer, db.ForeignKey("goals.id"), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)  # 新增描述字段
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    done = db.Column(db.Boolean, default=False, nullable=False)
    priority = db.Column(db.Integer, default=0)
    learning_item_id = db.Column(
        db.Integer, db.ForeignKey("learning_items.id"), nullable=True
    )  # AI integration
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    notes = db.relationship(
        "Note", backref="task", cascade="all, delete-orphan", lazy=True
    )
    learning_item = db.relationship(
        "LearningItem", backref=db.backref("tasks", lazy="dynamic")
    )

    def __repr__(self):
        status = "Done" if self.done else "Pending"
        return f"<Task {self.id} - {self.title} ({status})>"


class Note(db.Model):
    __tablename__ = "notes"
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )  # 必须提供
    content = db.Column(db.Text, default="", nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Note {self.id}>"


# models.py 修改Chat模型
class Chat(db.Model):
    __tablename__ = "chats"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), default="New Chat")
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.String, db.ForeignKey("user_profiles.id"), nullable=True)
    model = db.Column(
        db.String(50), default="deepseek-chat"
    )  # 新增模型字段（统一默认值）
    messages = db.relationship(
        "ChatMessage", backref="chat", cascade="all, delete-orphan", lazy=True
    )


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(50))
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    chat_id = db.Column(db.Integer, db.ForeignKey("chats.id"), nullable=False)

    def __repr__(self):
        return f"<ChatMessage {self.id} - {self.role}>"


class Membership(db.Model):
    __tablename__ = "memberships"
    id = db.Column(db.Integer, primary_key=True)
    plan = db.Column(db.String(50), default="free")
    renewal_date = db.Column(db.Date, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True)

    user = db.relationship("User", backref=db.backref("membership", uselist=False))

    def __repr__(self):
        return f"<Membership {self.plan} for user {self.user_id}>"


class UserSettings(db.Model):
    __tablename__ = "user_settings"
    id = db.Column(db.Integer, primary_key=True)
    language = db.Column(db.String(10), default="en")  # 新增语言字段
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True)
    user = db.relationship("User", backref=db.backref("settings", uselist=False))

    def __repr__(self):
        return f"<UserSettings notifications: {self.email_notifications} for user {self.user_id}>"


class UserProfile(db.Model):
    __tablename__ = "user_profiles"
    id = db.Column(db.String, primary_key=True)  # sub
    email = db.Column(db.String, index=True)
    email_verified = db.Column(db.Boolean, default=False)
    name = db.Column(db.String)
    picture = db.Column(db.String)

    # Contact information
    contact_name = db.Column(db.String, nullable=True)
    contact_email = db.Column(db.String, nullable=True)
    contact_phone_number = db.Column(db.String, nullable=True)
    contact_location = db.Column(db.String, nullable=True)


class ProcessingRun(db.Model):
    __tablename__ = "processing_runs"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    llm_model = db.Column(db.String)
    embed_model = db.Column(db.String)
    code_version_hash = db.Column(db.String)
    params_json = db.Column(db.JSON)


class Resume(db.Model):
    __tablename__ = "resumes"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey("user_profiles.id"), nullable=False)
    file_url = db.Column(db.String)  # Legacy field - keeping for backward compatibility
    s3_bucket = db.Column(db.String)  # S3 bucket name
    s3_key = db.Column(db.String)  # S3 object key
    original_filename = db.Column(db.String)  # Original filename from user
    file_size = db.Column(db.BigInteger)  # File size in bytes
    content_type = db.Column(db.String)  # MIME type
    parsed_json = db.Column(db.JSON)
    vector_doc_id = db.Column(db.String)
    processing_run_id = db.Column(
        db.Integer, db.ForeignKey("processing_runs.id"), nullable=False
    )
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String, nullable=False, default="processing")
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    user = db.relationship("UserProfile", backref=db.backref("resumes", lazy="dynamic"))

    @staticmethod
    def set_default_resume(user_id: str, resume_id: int):
        """Set a resume as default for a user. Unsets all other resumes for that user."""
        # First, unset all other resumes for this user
        Resume.query.filter_by(user_id=user_id).update({"is_default": False})

        # Set the specified resume as default
        resume = Resume.query.filter_by(id=resume_id, user_id=user_id).first()
        if resume:
            resume.is_default = True
            db.session.commit()
            return True
        return False

    @staticmethod
    def get_default_resume(user_id: str):
        """Get the default resume for a user."""
        return Resume.query.filter_by(user_id=user_id, is_default=True).first()


class Skill(db.Model):
    __tablename__ = "skills"
    """Ontology node with O*NET/ESCO framework support.

    Columns:
    - id: PK
    - skill_id: stable slug (e.g., "fe.react", "onet.2.B.1.1")
    - name: canonical display name
    - taxonomy_path: e.g., "ENGINEERING/FRONTEND/REACT" or "ONET/SKILLS/2.B.1.1"
    - vector_doc_id: Chroma doc id in `skills_ontology`
    - framework: 'Custom' | 'ONET' | 'ESCO' (default: 'Custom')
    - external_id: External taxonomy ID (O*NET element ID, ESCO URI, etc.)
    - meta_json: Framework-specific metadata (SOC codes, importance, level, etc.)
    - onet_soc_code: O*NET SOC code for occupation context
    - occupation_title: Occupation title for context
    - commodity_title: Technology commodity category
    - hot_tech: Whether this is a hot technology
    - in_demand: Whether this skill is in high demand
    - skill_type: Type of skill ('skill', 'task', 'job_profile')
    """
    id = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.String, unique=True, nullable=False, index=True)
    name = db.Column(db.String, nullable=False)
    taxonomy_path = db.Column(db.String, nullable=False)
    vector_doc_id = db.Column(db.String, nullable=False)
    framework = db.Column(db.String, nullable=False, default="ONET", index=True)
    external_id = db.Column(db.String, nullable=True, index=True)
    meta_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # O*NET context fields
    onet_soc_code = db.Column(db.String(10), nullable=True, index=True)
    occupation_title = db.Column(db.String(150), nullable=True)
    commodity_title = db.Column(db.String(150), nullable=True)
    hot_tech = db.Column(db.Boolean, nullable=False, default=False, index=True)
    in_demand = db.Column(db.Boolean, nullable=False, default=False, index=True)
    skill_type = db.Column(db.String(50), nullable=True, default="skill", index=True)

    # Relationships
    aliases = db.relationship(
        "SkillAlias",
        backref="skill",
        cascade="all, delete-orphan",
        lazy=True,
    )

    def __repr__(self):
        return f"<Skill {self.id} - {self.name} ({self.framework})>"


class SkillAlias(db.Model):
    __tablename__ = "skill_aliases"
    """Alias mapping with provenance tracking for imported taxonomies."""
    id = db.Column(db.Integer, primary_key=True)
    skill_id_fk = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False)
    alias = db.Column(db.String, nullable=False)
    meta_json = db.Column(db.JSON, nullable=True)

    def __repr__(self):
        return f"<SkillAlias {self.id} - {self.alias}>"

# TODO: to be implemented later, uncomment when ready
# class Skill(db.Model):
#     __tablename__ = 'skills'

#     # --- CORE IDENTITY ---
#     id: Mapped[int] = mapped_column(primary_key=True)
    
#     # The official, display-ready name (e.g., "React.js", "Python")
#     # Indexed for fast 'Exact Match' lookups
#     name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

#     # --- SEMANTIC CONTEXT (For AI) ---
#     # Used to generate the embedding. 
#     # "A JavaScript library for building user interfaces."
#     # Nullable for Phase 1, but essential for Phase 2.
#     description: Mapped[str] = mapped_column(Text, nullable=True)

#     # --- CATEGORIZATION (For Filtering) ---
#     # Helps you filter search results. 
#     # Values: 'language', 'framework', 'tool', 'soft_skill'
#     category: Mapped[str] = mapped_column(String(50), default="general", index=True)

#     # --- VECTOR SEARCH (The AI Brain) ---
#     # 3072 dimensions (Standard OpenAI size for text-embedding-3-large).
#     # Nullable=True so you can run exact match logic without calculating vectors yet.
#     embedding: Mapped[list[float]] = mapped_column(Vector(3072), nullable=True)

#     # --- METADATA & RANKING ---
#     # Verified: True = Added by Admin/O*NET. False = Auto-added by AI (needs review).
#     is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    
#     # Popularity: How many users have this skill? 
#     # Used for tie-breaking: If fuzzy match finds "Java" (pop:1000) vs "Javva" (pop:1), pick Java.
#     usage_count: Mapped[int] = mapped_column(Integer, default=0)

#     # Future-proofing: Store O*NET codes, alternative IDs, or raw JSON data here
#     metadata_json: Mapped[dict] = mapped_column(JSONB, default={})

#     # --- RELATIONSHIPS ---
#     # One Skill has Many Aliases
#     aliases = relationship("SkillAlias", back_populates="skill", cascade="all, delete-orphan")

#     def __repr__(self):
#         return f"<Skill {self.name} (Verified: {self.is_verified})>"

# class SkillAlias(db.Model):
#     __tablename__ = 'skill_aliases'

#     id: Mapped[int] = mapped_column(primary_key=True)
    
#     # The common variation (e.g., "ReactJS", "RJS", "React JS")
#     # Indexed because this is your most frequently searched column.
#     name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    
#     # Pointer to the Real Skill
#     skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), nullable=False)
    
#     skill = relationship("Skill", back_populates="aliases")

#     def __repr__(self):
#         return f"<Alias '{self.name}' -> Skill ID {self.skill_id}>"


class JobListing(db.Model):
    __tablename__ = "job_listings"
    """Job listings table to store scraped or manually added job postings."""

    id = db.Column(db.Integer, primary_key=True)

    # Basic job information
    title = db.Column(db.String(200), nullable=False)
    company = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(200), nullable=True)
    job_type = db.Column(
        db.String(50), nullable=True
    )  # Full-time, Part-time, Contract, etc.

    # Job details
    description = db.Column(db.Text, nullable=True)
    requirements = db.Column(db.Text, nullable=True)
    salary_min = db.Column(db.Integer, nullable=True)
    salary_max = db.Column(db.Integer, nullable=True)
    salary_currency = db.Column(db.String(10), default="USD", nullable=True)

    # External links and metadata
    external_url = db.Column(db.String(500), nullable=True)
    external_id = db.Column(db.String(200), nullable=True)  # ID from job board
    source = db.Column(db.String(100), nullable=True)  # LinkedIn, Indeed, etc.

    # Company information
    company_logo_url = db.Column(db.String(500), nullable=True)
    company_website = db.Column(db.String(200), nullable=True)

    # Skills (JSON array for flexibility)
    required_skills = db.Column(db.JSON, nullable=True)  # ["Python", "React", "SQL"]
    preferred_skills = db.Column(db.JSON, nullable=True)

    # Status and timestamps
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_remote = db.Column(db.Boolean, default=False, nullable=False)
    date_posted = db.Column(db.DateTime, nullable=True)
    date_expires = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Vector store reference (for AI features)
    vector_doc_id = db.Column(db.String(200), nullable=True)

    def __repr__(self):
        return f"<JobListing {self.id} - {self.title} at {self.company}>"

    def to_dict(self):
        """Convert model to dictionary for JSON serialization."""
        import json

        # Helper function to parse JSON fields that might be strings
        def parse_json_field(field_value):
            if field_value is None:
                return []
            if isinstance(field_value, list):
                return field_value
            if isinstance(field_value, str):
                try:
                    return json.loads(field_value)
                except (json.JSONDecodeError, ValueError):
                    return []
            return []

        return {
            "id": self.id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "job_type": self.job_type,
            "description": self.description,
            "requirements": self.requirements,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "salary_currency": self.salary_currency,
            "external_url": self.external_url,
            "external_id": self.external_id,
            "source": self.source,
            "company_logo_url": self.company_logo_url,
            "company_website": self.company_website,
            "required_skills": parse_json_field(self.required_skills),
            "preferred_skills": parse_json_field(self.preferred_skills),
            "is_active": self.is_active,
            "is_remote": self.is_remote,
            "date_posted": self.date_posted.isoformat() if self.date_posted else None,
            "date_expires": (
                self.date_expires.isoformat() if self.date_expires else None
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "vector_doc_id": self.vector_doc_id,
        }


class JobCollection(db.Model):
    __tablename__ = "job_collections"
    __table_args__ = (
        db.UniqueConstraint("user_id", "job_listing_id", name="uix_user_job_listing"),
    )
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey("user_profiles.id"), nullable=False)
    job_listing_id = db.Column(
        db.Integer, db.ForeignKey("job_listings.id"), nullable=False
    )
    added_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    user = db.relationship(
        "UserProfile", backref=db.backref("job_collections", lazy="dynamic")
    )
    job_listing = db.relationship(
        "JobListing", backref=db.backref("saved_by", lazy="dynamic")
    )


# AI Features Models (Phase 1 Implementation)


## Removed ResumeSkill model (skill-only mode)


## Removed JobSkill model (skill-only mode)


class SkillGapReport(db.Model):
    """Skill gap analysis report comparing resume vs job requirements."""

    __tablename__ = "skill_gap_reports"

    id = db.Column(db.Integer, primary_key=True)
    # Now references user_profiles.id (string) after migration
    user_id = db.Column(db.String, db.ForeignKey("user_profiles.id"), nullable=False)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id"), nullable=False)
    job_listing_id = db.Column(
        db.Integer, db.ForeignKey("job_listings.id"), nullable=False
    )

    # JSON fields for structured gap analysis results
    matched_skills_json = db.Column(
        db.JSON, nullable=False
    )  # [{skill_id, evidence, level, confidence}]
    missing_skills_json = db.Column(
        db.JSON, nullable=False
    )  # [{skill_id, required_level, rationale}]
    weak_skills_json = db.Column(
        db.JSON, nullable=True
    )  # [{skill_id, current_level, required_level, gap}]
    resume_skills_json = db.Column(
        db.JSON, nullable=True
    )  # [{skill_id, match, candidate_level, score}] - all detected resume skills with levels

    score = db.Column(db.Float, nullable=False)  # 0-100 overall match score
    analysis_version = db.Column(db.String, nullable=True)
    analysis_json = db.Column(db.JSON, nullable=True)
    report_note_id = db.Column(db.Integer, db.ForeignKey("notes.id"), nullable=True)
    processing_run_id = db.Column(
        db.Integer, db.ForeignKey("processing_runs.id"), nullable=False
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship(
        "UserProfile", backref=db.backref("skill_gap_reports", lazy="dynamic")
    )
    resume = db.relationship(
        "Resume", backref=db.backref("skill_gap_reports", lazy="dynamic")
    )
    job_listing = db.relationship(
        "JobListing", backref=db.backref("skill_gap_reports", lazy="dynamic")
    )
    report_note = db.relationship(
        "Note", backref=db.backref("skill_gap_reports", lazy="dynamic")
    )
    processing_run = db.relationship(
        "ProcessingRun", backref=db.backref("skill_gap_reports", lazy="dynamic")
    )

    def __repr__(self):
        return f"<SkillGapReport {self.id} - Score: {self.score:.1f}%>"


class SkillGapStatus(db.Model):
    """Tracks per-user job gap generation status for quick lookups."""

    __tablename__ = "skill_gap_statuses"
    __table_args__ = (
        db.UniqueConstraint(
            "user_id", "job_listing_id", name="uix_gap_status_user_job"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.String, db.ForeignKey("user_profiles.id"), nullable=False, index=True
    )
    job_listing_id = db.Column(
        db.Integer, db.ForeignKey("job_listings.id"), nullable=False, index=True
    )
    status = db.Column(db.String(32), nullable=False, default="generating", index=True)
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    VALID_STATES = {"ready", "generating"}

    def __repr__(self):
        return f"<SkillGapStatus user={self.user_id} job={self.job_listing_id} status={self.status}>"

    @classmethod
    def set_status(
        cls, user_id: str, job_listing_id: int, status: str, commit: bool = True
    ) -> "SkillGapStatus":
        if status not in cls.VALID_STATES:
            raise ValueError(
                f"Invalid gap status '{status}'. Expected one of {cls.VALID_STATES}."
            )

        record = cls.query.filter_by(
            user_id=user_id, job_listing_id=job_listing_id
        ).first()
        if record:
            record.status = status
            record.updated_at = datetime.now(timezone.utc)
        else:
            record = cls(user_id=user_id, job_listing_id=job_listing_id, status=status)
            db.session.add(record)

        if commit:
            try:
                db.session.commit()
            except Exception:  # pragma: no cover - propagate but ensure clean session
                db.session.rollback()
                raise

        return record

    @classmethod
    def clear_status(
        cls, user_id: str, job_listing_id: int, commit: bool = True
    ) -> None:
        record = cls.query.filter_by(
            user_id=user_id, job_listing_id=job_listing_id
        ).first()
        if not record:
            return
        db.session.delete(record)
        if commit:
            try:
                db.session.commit()
            except Exception:  # pragma: no cover
                db.session.rollback()
                raise

    @classmethod
    def get_status(cls, user_id: str, job_listing_id: int) -> Optional[str]:
        record = cls.query.filter_by(
            user_id=user_id, job_listing_id=job_listing_id
        ).first()
        return record.status if record else None


class PreloadedContext(db.Model):
    """Stores short precomputed context snippets for user+job to be used as chat system messages.

    This is a lightweight fallback and statusable store used while Chroma-based
    embeddings are built or unavailable.
    """

    __tablename__ = "preloaded_contexts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.String, db.ForeignKey("user_profiles.id"), nullable=False, index=True
    )
    job_listing_id = db.Column(
        db.Integer, db.ForeignKey("job_listings.id"), nullable=True, index=True
    )
    doc_type = db.Column(db.String(50), nullable=False)  # resume|job|gap|profile
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<PreloadedContext {self.id} user={self.user_id} job={self.job_listing_id} type={self.doc_type}>"


class LearningItem(db.Model):
    """AI-generated learning resources for skill development."""

    __tablename__ = "learning_items"

    id = db.Column(db.Integer, primary_key=True)
    skill_id_fk = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    source = db.Column(db.String(100), nullable=False)  # Coursera, Docs, MDN, etc.
    est_time_min = db.Column(db.Integer, nullable=True)  # estimated time in minutes
    difficulty = db.Column(
        db.String(20), nullable=True
    )  # Beginner/Intermediate/Advanced
    meta_json = db.Column(db.JSON, nullable=True)  # additional metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    skill = db.relationship(
        "Skill", backref=db.backref("learning_items", lazy="dynamic")
    )

    def __repr__(self):
        return f"<LearningItem {self.id} - {self.title} ({self.difficulty})>"


class ReportLearningItem(db.Model):
    """Links skill gap reports to learning items with reasoning."""

    __tablename__ = "report_learning_items"

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(
        db.Integer, db.ForeignKey("skill_gap_reports.id"), nullable=False
    )
    learning_item_id = db.Column(
        db.Integer, db.ForeignKey("learning_items.id"), nullable=False
    )
    reason = db.Column(db.Text, nullable=True)  # why this learning item was recommended
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    report = db.relationship(
        "SkillGapReport", backref=db.backref("report_learning_items", lazy="dynamic")
    )
    learning_item = db.relationship(
        "LearningItem", backref=db.backref("report_learning_items", lazy="dynamic")
    )

    def __repr__(self):
        return f"<ReportLearningItem {self.id} - Report {self.report_id} -> Learning {self.learning_item_id}>"
