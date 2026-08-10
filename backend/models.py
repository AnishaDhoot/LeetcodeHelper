from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict

def get_utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
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
    companies = Column(String, nullable=True)  # Comma-separated company names, e.g. "Google,Amazon"
    is_solved = Column(Boolean, default=False, nullable=False) # True once synced from LeetCode history
    user_notes = Column(Text, nullable=True)
    personal_difficulty = Column(String, nullable=True) # e.g. "Hard for me", "Tricky Edge Cases", "Medium", "Easy"

    attempts = relationship("Attempt", back_populates="problem")


class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    problem_id = Column(String, ForeignKey("problems.id"), nullable=False)
    timestamp = Column(DateTime, default=get_utc_now, nullable=False)
    verdict = Column(String, nullable=False) # e.g., Wrong Answer, Accepted, etc.
    root_cause_category = Column(String, nullable=True) # wrong_approach, implementation_bug, etc.
    explanation_text = Column(Text, nullable=True)
    time_taken_seconds = Column(Integer, nullable=True)
    time_spent_seconds = Column(Integer, nullable=True)
    hints_used = Column(Integer, default=0, nullable=False)  # progressive hint reveal count (Tier 3.1)

    problem = relationship("Problem", back_populates="attempts")


class TopicMastery(Base):
    __tablename__ = "topic_mastery"

    topic = Column(String, primary_key=True, index=True) # e.g., "Arrays", "Two Pointers"
    rating = Column(Float, default=1200.0, nullable=False)
    attempts_count = Column(Integer, default=0, nullable=False)
    success_count = Column(Integer, default=0, nullable=False)
    level = Column(Integer, default=0, nullable=False)
    last_updated = Column(DateTime, default=get_utc_now, nullable=False)
    next_review_date = Column(DateTime, nullable=True)

    @property
    def badge(self) -> str:
        badges = {
            0: "None",
            1: "Bronze",
            2: "Silver",
            3: "Gold",
            4: "Platinum",
            5: "Diamond"
        }
        return badges.get(self.level or 0, "None")

    @property
    def mastery_score(self) -> float:
        return (self.level or 0) / 5.0

    @property
    def success_rate(self) -> float:
        if self.attempts_count <= 0:
            return 0.0
        return self.success_count / self.attempts_count

    @property
    def last_attempted(self) -> Optional[datetime]:
        return self.last_updated

    @property
    def next_due_date(self) -> Optional[datetime]:
        return self.next_review_date


class BadgeTest(Base):
    __tablename__ = "badge_tests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic = Column(String, nullable=False)
    level = Column(Integer, nullable=False) # level being tested for (1-5)
    status = Column(String, default="active") # "active", "passed", "abandoned"
    problem1_id = Column(String, nullable=False)
    problem2_id = Column(String, nullable=False)
    problem1_solved = Column(Boolean, default=False, nullable=False)
    problem2_solved = Column(Boolean, default=False, nullable=False)
    start_time = Column(DateTime, default=get_utc_now, nullable=False)
    end_time = Column(DateTime, nullable=True)


class UserConfig(Base):
    """Simple key/value store for user preferences (e.g. focus topic, critique estimates)."""
    __tablename__ = "user_config"

    key = Column(String, primary_key=True, index=True)
    value = Column(String, nullable=True)


class SpacedRepetition(Base):
    __tablename__ = "spaced_repetition"

    problem_id = Column(String, ForeignKey("problems.id"), primary_key=True, index=True)
    stage = Column(Integer, default=1, nullable=False) # 1: 3 days, 2: 7 days, 3: 14 days, 4: complete
    last_solved = Column(DateTime, default=get_utc_now, nullable=False)
    next_due = Column(DateTime, nullable=False)

    problem = relationship("Problem")


class DailyActivity(Base):
    """Tracks per-day attempt/solve counts for streak calculation (Tier 1.4)."""
    __tablename__ = "daily_activity"

    date = Column(String, primary_key=True)  # ISO date string "YYYY-MM-DD"
    problems_attempted = Column(Integer, default=0, nullable=False)
    problems_solved = Column(Integer, default=0, nullable=False)


class MockInterviewSession(Base):
    """Records mock interview sessions including approach gating and timing (Tier 4.1)."""
    __tablename__ = "mock_interview_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    problem_id = Column(String, ForeignKey("problems.id"), nullable=False)
    start_time = Column(DateTime, default=get_utc_now, nullable=False)
    time_limit_seconds = Column(Integer, default=2700, nullable=False)  # 45 min default
    company = Column(String, nullable=True)
    approach_submitted_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    time_taken_seconds = Column(Integer, nullable=True)

    # Added columns for 3-question mock interviews
    problem_ids = Column(String, nullable=True)  # Comma-separated list of 3 problem IDs
    current_question_index = Column(Integer, default=0, nullable=False)
    approaches_submitted = Column(String, default="0,0,0", nullable=False)  # Comma-separated "0" or "1"
    approaches_text = Column(Text, nullable=True)  # JSON-serialized list of approach texts

    problem = relationship("Problem")


class CompanyMetadata(Base):
    """Stores company-specific focus notes and metadata."""
    __tablename__ = "company_metadata"

    name = Column(String, primary_key=True, index=True)
    focus_note = Column(Text, nullable=True)


# ==========================================================
# Pydantic Schemas
# ==========================================

class ProblemBase(BaseModel):
    id: str
    title: str
    url: str
    difficulty: str
    topics: str
    companies: Optional[str] = None
    user_notes: Optional[str] = None
    personal_difficulty: Optional[str] = None

class SaveProblemNotesRequest(BaseModel):
    user_notes: Optional[str] = None
    personal_difficulty: Optional[str] = None

class ProblemSchema(ProblemBase):
    model_config = ConfigDict(from_attributes=True)

class AttemptBase(BaseModel):
    problem_id: str
    verdict: str
    root_cause_category: Optional[str] = None
    explanation_text: Optional[str] = None
    time_taken_seconds: Optional[int] = None
    hints_used: int = 0

class AttemptCreate(AttemptBase):
    pass

class AttemptSchema(AttemptBase):
    id: int
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)

class BadgeTestProblemSchema(BaseModel):
    id: str
    title: str
    url: str
    difficulty: str


class TopicMasterySchema(BaseModel):
    topic: str
    mastery_score: float
    attempts_count: int
    success_rate: float
    rating: float
    level: int
    badge: str
    next_questions: List[BadgeTestProblemSchema] = []
    last_attempted: Optional[datetime] = None
    next_due_date: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class BadgeTestStartRequest(BaseModel):
    topic: str


class BadgeTestSchema(BaseModel):
    id: int
    topic: str
    level: int
    status: str
    problem1: BadgeTestProblemSchema
    problem2: BadgeTestProblemSchema
    problem1_solved: bool
    problem2_solved: bool
    start_time: datetime
    end_time: Optional[datetime] = None

class SubmissionAnalyzeRequest(BaseModel):
    problem_id: str
    problem_title: str
    code: str
    language: str
    verdict: str
    error_details: Optional[str] = None
    test_cases: Optional[List[dict]] = None
    time_taken_seconds: Optional[int] = None
    hints_used: int = 0  # passed from extension after progressive hint use

class SubmissionAnalyzeResponse(BaseModel):
    root_cause_category: str
    explanation: str
    suggested_action: str

class RecommendationItem(BaseModel):
    problem_id: str
    title: str
    url: str
    difficulty: str
    reason: str


class ReviewItem(BaseModel):
    problem_id: str
    title: str
    url: str
    difficulty: str
    due_date: datetime
    stage: int


class ProblemRecommendResponse(BaseModel):
    recommendations: List[RecommendationItem]
    reviews: List[ReviewItem]


class SolvedProblemSyncSchema(BaseModel):
    problem_id: str
    title: str
    difficulty: str
    topics: List[str]
    company: Optional[str] = None  # 1.1: optional company tag from sync source


class SyncSolvedRequest(BaseModel):
    problems: List[SolvedProblemSyncSchema]


class TopicStatItem(BaseModel):
    topic: str
    solved_count: int
    mastery_score: float
    badge: Optional[str] = None


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


# --- Levelled hint schemas (Tier 3.1) ---

class GetHintRequest(BaseModel):
    problem_id: str
    problem_title: str
    code: str
    language: str
    constraints: Optional[List[str]] = None


class GetHintResponse(BaseModel):
    hint: str


class HintRevealRequest(BaseModel):
    problem_id: str
    problem_title: str
    code: str
    language: str
    level: int  # 1, 2, or 3
    constraints: Optional[List[str]] = None


class HintRevealResponse(BaseModel):
    hint: str
    level: int
    has_next: bool  # False when level == 3


class GetEdgeCasesRequest(BaseModel):
    problem_id: str
    problem_title: str
    code: str
    language: str
    constraints: Optional[List[str]] = None


class GetEdgeCasesResponse(BaseModel):
    edge_cases: List[dict]
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


# --- Explain-back schemas (Tier 3.2) ---

class ExplainBackRequest(BaseModel):
    problem_id: str
    code: str
    language: str
    user_explanation: str


class ExplainBackResponse(BaseModel):
    matches: bool
    discrepancy_note: Optional[str] = None


# --- Complexity self-estimate schemas (Tier 3.3) ---

class ComplexityEstimateRequest(BaseModel):
    problem_id: str
    time_complexity: str   # e.g. "O(N log N)"
    space_complexity: str  # e.g. "O(1)"


class ComplexityRevealRequest(BaseModel):
    problem_id: str
    problem_title: str
    code: str
    language: str
    constraints: Optional[List[str]] = None


class ComplexityRevealResponse(BaseModel):
    estimate: Optional[dict]  # stored guess: {time_complexity, space_complexity}
    is_optimal: bool
    current_complexity: str
    optimal_complexity: str
    feedback: str
    alternative_approach: str


# --- Activity / streak schemas (Tier 1.4) ---

class StreakResponse(BaseModel):
    current_streak_days: int
    problems_today: int
    solved_today: int


# --- Weekly journal schema (Tier 5.1) ---

class WeeklyJournalResponse(BaseModel):
    period_start: str
    period_end: str
    total_attempts: int
    total_solved: int
    by_category: dict          # { category: count }
    example_problems: List[str]
    markdown_text: str


# --- Mock interview schemas (Tier 4.1) ---

class MockStartRequest(BaseModel):
    company: Optional[str] = None
    time_limit_seconds: int = 2700  # 45 min default


class MockStartResponse(BaseModel):
    session_id: int
    problem_id: str
    problem_title: str
    problem_url: str
    difficulty: str
    topics: str
    time_limit_seconds: int
    approach_submitted: bool = False
    
    # 3-problem support fields
    current_question_index: int = 0
    problem_ids: List[str] = []
    problem_titles: List[str] = []
    problem_urls: List[str] = []
    difficulties: List[str] = []
    approaches_submitted_list: List[bool] = []


class MockApproachRequest(BaseModel):
    session_id: int
    approach_text: str


class MockSubmitRequest(BaseModel):
    session_id: int
    problem_id: str
    problem_title: str
    code: str
    language: str


# --- Weak pairs (Tier 2.1) ---

class WeakPairItem(BaseModel):
    topic_a: str
    topic_b: str
    co_occurrence: int
