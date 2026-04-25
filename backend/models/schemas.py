from pydantic import BaseModel, EmailStr
from typing import List, Optional, Any, Dict
from datetime import datetime


class InterviewCreate(BaseModel):
    title: str
    role: str
    experience_years: int


class InterviewResponse(BaseModel):
    id: str
    title: str
    role: str
    experience_years: int
    status: str
    teams_meeting_link: Optional[str]
    interview_token: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CandidateCreate(BaseModel):
    interview_id: str
    name: str
    email: EmailStr
    phone: Optional[str] = None


class CandidateResponse(BaseModel):
    id: str
    interview_id: str
    name: str
    email: str
    phone: Optional[str]
    photo_path: Optional[str]
    extracted_skills: List[str]
    extracted_projects: List[Any]
    proctoring_score: Optional[float]
    created_at: datetime

    model_config = {"from_attributes": True}


class QuestionResponse(BaseModel):
    id: str
    order_index: int
    type: str
    category: str
    text: str
    time_limit_seconds: int
    starter_code: str
    test_cases: List[Any]

    model_config = {"from_attributes": True}


class AnswerSubmit(BaseModel):
    question_id: str
    candidate_id: str
    transcript: Optional[str] = None
    code_submission: Optional[str] = None


class AnswerResponse(BaseModel):
    id: str
    question_id: str
    transcript: Optional[str]
    code_submission: Optional[str]
    score: Optional[float]
    communication_clarity: Optional[float]
    feedback: Optional[str]
    key_points_covered: List[str]
    key_points_missed: List[str]

    model_config = {"from_attributes": True}


class ProctoringEventCreate(BaseModel):
    candidate_id: str
    event_type: str
    duration_seconds: float = 0.0
    severity: str = "low"
    details: Dict[str, Any] = {}
    screenshot_base64: Optional[str] = None


class ProctoringEventResponse(BaseModel):
    id: str
    event_type: str
    timestamp: datetime
    duration_seconds: float
    severity: str
    details: Dict[str, Any]

    model_config = {"from_attributes": True}


class ReportResponse(BaseModel):
    id: str
    interview_id: str
    candidate_id: str
    overall_score: Optional[float]
    technical_score: Optional[float]
    communication_score: Optional[float]
    integrity_score: Optional[float]
    final_decision: Optional[str]
    decision_reason: Optional[str]
    generated_at: datetime

    model_config = {"from_attributes": True}


class PhotoUpload(BaseModel):
    candidate_id: str
    image_base64: str
