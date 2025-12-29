"""
Pydantic schemas for request/response validation in FastAPI.
"""
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, date


# User schemas
class UserBase(BaseModel):
    username: str
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: int
    is_premium: bool
    membership_plan: str
    email_notifications: bool

    model_config = ConfigDict(from_attributes=True)


# UserProfile schemas
class UserProfileBase(BaseModel):
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    current_title: Optional[str] = None
    years_experience: Optional[int] = None
    location: Optional[str] = None
    skills: Optional[List[str]] = None
    interests: Optional[List[str]] = None


class UserProfileUpdate(UserProfileBase):
    pass


class UserProfileResponse(UserProfileBase):
    id: str
    email_verified: bool
    provider: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Resume schemas
class ResumeUploadResponse(BaseModel):
    resume_id: int
    message: str
    chunks_created: int = 0
    text_length: int = 0
    s3_key: Optional[str] = None
    bucket: Optional[str] = None


class ResumeResponse(BaseModel):
    id: int
    user_id: str
    filename: str
    s3_key: Optional[str] = None
    bucket: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResumeListResponse(BaseModel):
    resumes: List[ResumeResponse]


class DownloadURLResponse(BaseModel):
    download_url: str
    expires_in: int = 3600


# Chat schemas
class MessageCreate(BaseModel):
    role: str
    content: str


class MessageResponse(BaseModel):
    id: int
    chat_id: int
    role: str
    content: str
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatCreate(BaseModel):
    title: Optional[str] = "New Chat"
    model: Optional[str] = "deepseek-chat"


class ChatResponse(BaseModel):
    id: int
    title: str
    timestamp: datetime
    user_id: Optional[str] = None
    model: str
    messages: Optional[List[MessageResponse]] = []

    model_config = ConfigDict(from_attributes=True)


class ChatListResponse(BaseModel):
    chats: List[ChatResponse]


# Job Listing schemas
class JobListingBase(BaseModel):
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    posted_date: Optional[datetime] = None
    source: Optional[str] = None
    external_id: Optional[str] = None


class JobListingCreate(JobListingBase):
    required_skills: Optional[List[str]] = None
    preferred_skills: Optional[List[str]] = None
    experience_level: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None


class JobListingResponse(JobListingBase):
    id: int
    created_at: datetime
    required_skills: Optional[List[str]] = None
    preferred_skills: Optional[List[str]] = None
    experience_level: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class JobListingListResponse(BaseModel):
    jobs: List[JobListingResponse]
    total: int
    page: int
    page_size: int


# Job Collection schemas
class JobCollectionCreate(BaseModel):
    job_id: int
    status: Optional[str] = "saved"
    notes: Optional[str] = None


class JobCollectionUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


class JobCollectionResponse(BaseModel):
    id: int
    user_id: str
    job_id: int
    status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Skill Gap Report schemas
class SkillGapReportCreate(BaseModel):
    resume_id: Optional[int] = None
    job_id: Optional[int] = None


class SkillGapReportResponse(BaseModel):
    id: int
    user_id: str
    resume_id: Optional[int] = None
    job_id: Optional[int] = None
    missing_skills: Optional[List[str]] = None
    matching_skills: Optional[List[str]] = None
    resume_skills_json: Optional[Dict[str, Any]] = None
    recommendations: Optional[List[Dict[str, Any]]] = None
    match_score: Optional[float] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Task schemas
class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    priority: int = 0
    goal_id: Optional[int] = None
    learning_item_id: Optional[int] = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    done: Optional[bool] = None
    priority: Optional[int] = None


class TaskResponse(TaskBase):
    id: int
    user_id: int
    done: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Goal schemas
class GoalBase(BaseModel):
    title: str
    description: Optional[str] = None


class GoalCreate(GoalBase):
    pass


class GoalResponse(GoalBase):
    id: int
    user_id: int
    created_at: datetime
    tasks: Optional[List[TaskResponse]] = []

    model_config = ConfigDict(from_attributes=True)


# Learning Item schemas
class LearningItemBase(BaseModel):
    skill_name: str
    resource_type: Optional[str] = None
    resource_title: Optional[str] = None
    resource_url: Optional[str] = None
    resource_provider: Optional[str] = None
    duration: Optional[str] = None
    difficulty: Optional[str] = None


class LearningItemCreate(LearningItemBase):
    pass


class LearningItemResponse(LearningItemBase):
    id: int
    user_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Generic response schemas
class SuccessResponse(BaseModel):
    ok: bool = True
    message: str


class ErrorResponse(BaseModel):
    ok: bool = False
    error: str
