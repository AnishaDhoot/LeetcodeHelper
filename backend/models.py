from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional
from backend.database import Base

# ==========================================
# SQLAlchemy Models
# ==========================================

class Problem(Base):
    __tablename__ = "problems"

    id = Column(String, primary_key=True, index=True) # e.g. "two-sum" or "1"
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    difficulty = Column(String, nullable=False) # Easy, Medium, Hard
    topics = Column(String, nullable=False) # Comma-separated list of topics, e.g. "Arrays,Two Pointers"
    is_solved = Column(Boolean, default=False, nullable=False) # True once synced from LeetCode history

    attempts = relationship("Attempt", back_populates="problem")


class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    problem_id = Column(String, ForeignKey("problems.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    verdict = Column(String, nullable=False) # e.g., Wrong Answer, Accepted, etc.
    root_cause_category = Column(String, nullable=True) # wrong_approach, implementation_bug, etc.
    explanation_text = Column(Text, nullable=True)
    time_taken_seconds = Column(Integer, nullable=True)

    problem = relationship("Problem", back_populates="attempts")


class TopicMastery(Base):
    __tablename__ = "topic_mastery"

    topic = Column(String, primary_key=True, index=True) # e.g., "Arrays", "Two Pointers"
    mastery_score = Column(Float, default=0.0, nullable=False) # 0.0 to 1.0
    attempts_count = Column(Integer, default=0, nullable=False)
    success_rate = Column(Float, default=0.0, nullable=False)
    last_attempted = Column(DateTime, nullable=True)
    next_due_date = Column(DateTime, nullable=True)


class UserConfig(Base):
    """Simple key/value store for user preferences (e.g. focus topic)."""
    __tablename__ = "user_config"

    key = Column(String, primary_key=True, index=True)
    value = Column(String, nullable=True)


# ==========================================
# Pydantic Schemas
# ==========================================

class ProblemBase(BaseModel):
    id: str
    title: str
    url: str
    difficulty: str
    topics: str

class ProblemSchema(ProblemBase):
    class Config:
        from_attributes = True

class AttemptBase(BaseModel):
    problem_id: str
    verdict: str
    root_cause_category: Optional[str] = None
    explanation_text: Optional[str] = None
    time_taken_seconds: Optional[int] = None

class AttemptCreate(AttemptBase):
    pass

class AttemptSchema(AttemptBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class TopicMasterySchema(BaseModel):
    topic: str
    mastery_score: float
    attempts_count: int
    success_rate: float
    last_attempted: Optional[datetime] = None
    next_due_date: Optional[datetime] = None

    class Config:
        from_attributes = True

class SubmissionAnalyzeRequest(BaseModel):
    problem_id: str
    problem_title: str
    code: str
    language: str
    verdict: str
    error_details: Optional[str] = None
    test_cases: Optional[List[dict]] = None
    time_taken_seconds: Optional[int] = None

class SubmissionAnalyzeResponse(BaseModel):
    root_cause_category: str
    explanation: str
    suggested_action: str

class ProblemRecommendResponse(BaseModel):
    problem_id: str
    title: str
    url: str
    difficulty: str
    reason: str


class SolvedProblemSyncSchema(BaseModel):
    problem_id: str
    title: str
    difficulty: str
    topics: List[str]


class SyncSolvedRequest(BaseModel):
    problems: List[SolvedProblemSyncSchema]


class TopicStatItem(BaseModel):
    topic: str
    solved_count: int
    mastery_score: float


class TopicAnalysisResponse(BaseModel):
    total_solved: int
    difficulty_breakdown: dict
    top_topics: List[TopicStatItem]
    weak_topics: List[TopicStatItem]


class FocusResponse(BaseModel):
    focus_topic: Optional[str] = None


class SetFocusRequest(BaseModel):
    topic: Optional[str] = None  # None / empty clears the focus


class CheckApproachRequest(BaseModel):
    problem_id: str
    problem_title: str
    code: str
    language: str
    constraints: Optional[List[str]] = None


class CheckApproachResponse(BaseModel):
    is_optimal: bool
    current_complexity: str
    optimal_complexity: str
    feedback: str
    alternative_approach: str


class GetHintRequest(BaseModel):
    problem_id: str
    problem_title: str
    code: str
    language: str
    constraints: Optional[List[str]] = None


class GetHintResponse(BaseModel):
    hint: str


class EdgeCaseItem(BaseModel):
    case: str
    handled: bool
    suggestion: str


class GetEdgeCasesRequest(BaseModel):
    problem_id: str
    problem_title: str
    code: str
    language: str
    constraints: Optional[List[str]] = None


class GetEdgeCasesResponse(BaseModel):
    edge_cases: List[EdgeCaseItem]
    constraints_critique: str


class AskHelpRequest(BaseModel):
    problem_id: str
    problem_title: str
    code: str
    language: str
    question: str
    constraints: Optional[List[str]] = None


class AskHelpResponse(BaseModel):
    answer: str

