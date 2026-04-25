import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


def new_uuid():
    return str(uuid.uuid4())


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(String, primary_key=True, default=new_uuid)
    title = Column(String, nullable=False)
    role = Column(String, nullable=False)
    experience_years = Column(Integer, nullable=False)
    status = Column(String, default="created")  # created|invited|in_progress|completed|assessed
    teams_meeting_link = Column(String, nullable=True)
    teams_meeting_id = Column(String, nullable=True)
    interview_token = Column(String, unique=True, default=new_uuid)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    candidates = relationship("Candidate", back_populates="interview")
    questions = relationship("Question", back_populates="interview", order_by="Question.order_index")


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(String, primary_key=True, default=new_uuid)
    interview_id = Column(String, ForeignKey("interviews.id"), nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    resume_path = Column(String, nullable=True)
    photo_path = Column(String, nullable=True)
    extracted_skills = Column(JSON, default=list)
    extracted_projects = Column(JSON, default=list)
    proctoring_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    interview = relationship("Interview", back_populates="candidates")
    answers = relationship("Answer", back_populates="candidate")
    proctoring_events = relationship("ProctoringEvent", back_populates="candidate")
    report = relationship("Report", back_populates="candidate", uselist=False)


class Question(Base):
    __tablename__ = "questions"

    id = Column(String, primary_key=True, default=new_uuid)
    interview_id = Column(String, ForeignKey("interviews.id"), nullable=False)
    order_index = Column(Integer, nullable=False)
    type = Column(String, nullable=False)  # technical|project|behavioral|coding
    category = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    expected_answer_points = Column(JSON, default=list)
    time_limit_seconds = Column(Integer, default=180)
    starter_code = Column(Text, default="")
    test_cases = Column(JSON, default=list)

    interview = relationship("Interview", back_populates="questions")
    answers = relationship("Answer", back_populates="question")


class Answer(Base):
    __tablename__ = "answers"

    id = Column(String, primary_key=True, default=new_uuid)
    question_id = Column(String, ForeignKey("questions.id"), nullable=False)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    recording_path = Column(String, nullable=True)
    transcript = Column(Text, nullable=True)
    code_submission = Column(Text, nullable=True)
    score = Column(Float, nullable=True)
    communication_clarity = Column(Float, nullable=True)
    feedback = Column(Text, nullable=True)
    key_points_covered = Column(JSON, default=list)
    key_points_missed = Column(JSON, default=list)
    submitted_at = Column(DateTime, default=datetime.utcnow)

    question = relationship("Question", back_populates="answers")
    candidate = relationship("Candidate", back_populates="answers")


class ProctoringEvent(Base):
    __tablename__ = "proctoring_events"

    id = Column(String, primary_key=True, default=new_uuid)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    event_type = Column(String, nullable=False)
    # look_away|rapid_eye_movement|lip_sync_mismatch|face_not_detected|multiple_faces|tab_switch
    timestamp = Column(DateTime, default=datetime.utcnow)
    duration_seconds = Column(Float, default=0.0)
    severity = Column(String, default="low")  # low|medium|high
    details = Column(JSON, default=dict)
    screenshot_path = Column(String, nullable=True)

    candidate = relationship("Candidate", back_populates="proctoring_events")


class Report(Base):
    __tablename__ = "reports"

    id = Column(String, primary_key=True, default=new_uuid)
    interview_id = Column(String, ForeignKey("interviews.id"), nullable=False)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    pdf_path = Column(String, nullable=True)
    overall_score = Column(Float, nullable=True)
    technical_score = Column(Float, nullable=True)
    communication_score = Column(Float, nullable=True)
    integrity_score = Column(Float, nullable=True)
    final_decision = Column(String, nullable=True)  # selected|rejected|hold
    decision_reason = Column(Text, nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)

    candidate = relationship("Candidate", back_populates="report")
