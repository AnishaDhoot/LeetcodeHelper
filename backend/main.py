from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

AI_DAILY_QUOTA_LIMIT = int(os.getenv("AI_DAILY_QUOTA_LIMIT", "25"))

def get_utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

import math
from collections import Counter

from backend.database import get_db, engine, Base
from backend.models import (
    Problem, Attempt, TopicMastery, UserConfig, SpacedRepetition, DailyActivity, MockInterviewSession,
    BadgeTest, BadgeTestStartRequest, BadgeTestProblemSchema, BadgeTestSchema, CompanyMetadata,
    SubmissionAnalyzeRequest, SubmissionAnalyzeResponse,
    ProblemRecommendResponse, TopicMasterySchema,
    CheckApproachRequest, CheckApproachResponse,
    GetHintRequest, GetHintResponse,
    HintRevealRequest, HintRevealResponse,
    GetEdgeCasesRequest, GetEdgeCasesResponse,
    AskHelpRequest, AskHelpResponse,
    SyncSolvedRequest, SolvedProblemSyncSchema,
    TopicAnalysisResponse, TopicStatItem, FocusResponse, SetFocusRequest,
    ExplainBackRequest, ExplainBackResponse,
    ComplexityEstimateRequest, ComplexityRevealRequest, ComplexityRevealResponse,
    StreakResponse, WeeklyJournalResponse,
    MockStartRequest, MockStartResponse, MockApproachRequest, MockSubmitRequest,
    WeakPairItem
)
from backend.agent import (
    generate_diagnosis,
    generate_approach_critique,
    generate_hint,
    generate_levelled_hint,
    analyze_edge_cases,
    answer_custom_question,
    generate_explain_back_check
)
from backend.recommender import (
    update_mastery_on_submission,
    get_next_problem,
    update_spaced_repetition,
    compute_weak_pairs,
    get_topic_time_trend,
    filter_problems_for_topic
)
from backend.seed import seed_db

# Ensure tables are created (just in case)
Base.metadata.create_all(bind=engine)


# --- Lightweight in-place schema migration ---------------------------------
# Handles two generations of the topic_mastery schema:
#   Old: mastery_score, success_rate, last_attempted, next_due_date  (flat score)
#   New: rating, success_count, last_updated, next_review_date       (Elo)
#
# SQLite doesn't support ALTER COLUMN / DROP COLUMN with constraints, so when
# the old mastery_score NOT NULL column is present we do the rename-recreate-
# copy-drop dance instead.
def _ensure_schema():
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    table_names = insp.get_table_names()

    # -- problems columns --
    if "problems" in table_names:
        prob_cols = [c["name"] for c in insp.get_columns("problems")]
        if "is_solved" not in prob_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE problems ADD COLUMN is_solved BOOLEAN DEFAULT 0 NOT NULL"))
        if "companies" not in prob_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE problems ADD COLUMN companies TEXT"))
        if "user_notes" not in prob_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE problems ADD COLUMN user_notes TEXT"))
        if "personal_difficulty" not in prob_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE problems ADD COLUMN personal_difficulty TEXT"))
        if "solved_live" not in prob_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE problems ADD COLUMN solved_live BOOLEAN DEFAULT 0 NOT NULL"))

    # -- attempts columns --
    if "attempts" in table_names:
        att_cols = [c["name"] for c in insp.get_columns("attempts")]
        if "time_spent_seconds" not in att_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE attempts ADD COLUMN time_spent_seconds INTEGER"))

    # -- topic_mastery Elo migration --
    if "topic_mastery" in table_names:
        tm_cols = {c["name"] for c in insp.get_columns("topic_mastery")}
        if "level" not in tm_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE topic_mastery ADD COLUMN level INTEGER DEFAULT 0 NOT NULL"))

        if "mastery_score" in tm_cols:
            # Old flat-score schema → Elo schema via table reconstruction.
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE topic_mastery RENAME TO _topic_mastery_old"))
                conn.execute(text("""
                    CREATE TABLE topic_mastery (
                        topic            TEXT     PRIMARY KEY NOT NULL,
                        rating           REAL     NOT NULL DEFAULT 1200.0,
                        attempts_count   INTEGER  NOT NULL DEFAULT 0,
                        success_count    INTEGER  NOT NULL DEFAULT 0,
                        level            INTEGER  NOT NULL DEFAULT 0,
                        last_updated     DATETIME,
                        next_review_date DATETIME
                    )
                """))
                conn.execute(text("""
                    INSERT INTO topic_mastery
                        (topic, rating, attempts_count, success_count, level,
                         last_updated, next_review_date)
                    SELECT
                        topic,
                        CASE
                            WHEN rating IS NOT NULL AND rating != 1200.0
                            THEN rating
                            ELSE COALESCE(mastery_score, 0.0) * 1200.0 + 800.0
                        END,
                        COALESCE(attempts_count, 0),
                        COALESCE(
                            success_count,
                            CAST(COALESCE(attempts_count,0)*COALESCE(success_rate,0.0) AS INTEGER)
                        ),
                        0,
                        COALESCE(last_updated, last_attempted, DATETIME('now')),
                        COALESCE(next_review_date, next_due_date)
                    FROM _topic_mastery_old
                """))
                conn.execute(text("DROP TABLE _topic_mastery_old"))

        elif "rating" not in tm_cols:
            # Fresh install lacking all Elo columns — add them individually.
            elo_additions = [
                ("rating",           "ALTER TABLE topic_mastery ADD COLUMN rating REAL DEFAULT 1200.0 NOT NULL"),
                ("success_count",    "ALTER TABLE topic_mastery ADD COLUMN success_count INTEGER DEFAULT 0 NOT NULL"),
                ("level",            "ALTER TABLE topic_mastery ADD COLUMN level INTEGER DEFAULT 0 NOT NULL"),
                ("last_updated",     "ALTER TABLE topic_mastery ADD COLUMN last_updated DATETIME"),
                ("next_review_date", "ALTER TABLE topic_mastery ADD COLUMN next_review_date DATETIME"),
            ]
            for col_name, ddl in elo_additions:
                if col_name not in tm_cols:
                    with engine.begin() as conn:
                        conn.execute(text(ddl))

    # -- problems columns --
    if "problems" in table_names:
        prob_cols = [c["name"] for c in insp.get_columns("problems")]
        if "is_premium" not in prob_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE problems ADD COLUMN is_premium BOOLEAN DEFAULT 0 NOT NULL"))

    # -- mock_interview_sessions columns --
    if "mock_interview_sessions" in table_names:
        mock_cols = [c["name"] for c in insp.get_columns("mock_interview_sessions")]
        if "problem_ids" not in mock_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE mock_interview_sessions ADD COLUMN problem_ids TEXT"))
        if "current_question_index" not in mock_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE mock_interview_sessions ADD COLUMN current_question_index INTEGER DEFAULT 0 NOT NULL"))
        if "approaches_submitted" not in mock_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE mock_interview_sessions ADD COLUMN approaches_submitted TEXT DEFAULT '0,0,0' NOT NULL"))
        if "approaches_text" not in mock_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE mock_interview_sessions ADD COLUMN approaches_text TEXT"))
        if "ai_feedback" not in mock_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE mock_interview_sessions ADD COLUMN ai_feedback TEXT"))
        if "scorecard" not in mock_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE mock_interview_sessions ADD COLUMN scorecard TEXT"))

    # -- badge_tests columns --
    if "badge_tests" in table_names:
        bt_cols = [c["name"] for c in insp.get_columns("badge_tests")]
        if "time_limit_seconds" not in bt_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE badge_tests ADD COLUMN time_limit_seconds INTEGER DEFAULT 5400 NOT NULL"))

    # Check if database is empty and warn developer
    from backend.database import SessionLocal
    db_conn = SessionLocal()
    try:
        if db_conn.query(Problem).count() == 0:
            print("[Warning] Problems table is empty! Please run 'python backend/seed.py' to seed the database.")
    except Exception as e:
        print(f"Database check warning: {e}")
    finally:
        db_conn.close()


_ensure_schema()


# Focus-topic key used inside the UserConfig key/value store.
FOCUS_KEY = "focus_topic"


def _seed_elo_rating(solved_count: int) -> float:
    """Log-scaled Elo seed so synced history yields meaningful ratings.

    rating = 800 + min(1200, 1200 * log(solved + 1) / log(51))
      0  ->  800,  1 ->  ~800,  5 -> ~1136,  10 -> ~1316,
      25 -> ~1556, 50 ->  2000
    """
    if solved_count <= 0:
        return 1200.0  # start at default Elo for new topics
    mastery_fraction = min(1.0, math.log(solved_count + 1) / math.log(51))
    return 800.0 + 1200.0 * mastery_fraction

app = FastAPI(title="Autonomous DSA Tutor Agent Backend")

ALLOWED_ORIGINS = [
    "https://leetcode.com",
    "https://www.leetcode.com",
    "http://localhost:5173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"chrome-extension://.*",
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

def _record_daily_activity(db: Session, is_success: bool):
    today = get_utc_now().strftime("%Y-%m-%d")
    act = db.query(DailyActivity).filter(DailyActivity.date == today).first()
    if not act:
        act = DailyActivity(date=today, problems_attempted=1, problems_solved=1 if is_success else 0)
        db.add(act)
    else:
        act.problems_attempted += 1
        if is_success:
            act.problems_solved += 1


def check_active_test_lock(db: Session, is_contest: bool = False):
    if is_contest:
        raise HTTPException(
            status_code=403,
            detail="AI features and hints are strictly disabled during LeetCode contests to ensure fair play."
        )

    # 1. Check Badge Test lock
    active = db.query(BadgeTest).filter(BadgeTest.status == "active").first()
    if active:
        raise HTTPException(
            status_code=403,
            detail="Hints and AI assistance are locked during an active Badge Test."
        )

    # 2. Check Mock Interview lock
    mock = db.query(MockInterviewSession).filter(MockInterviewSession.submitted_at.is_(None)).order_by(MockInterviewSession.id.desc()).first()
    if mock:
        elapsed = (get_utc_now() - mock.start_time).total_seconds()
        if elapsed <= mock.time_limit_seconds:
            raise HTTPException(
                status_code=403,
                detail="Hints and AI assistance are locked during an active Mock Interview."
            )


def check_and_increment_ai_quota(db: Session, increment: bool = True):
    from sqlalchemy import text
    today_str = get_utc_now().strftime("%Y-%m-%d")
    key = f"ai_limit_{today_str}"
    
    # 1. Ensure the row exists for today (insert 0 if ignore)
    db.execute(
        text("INSERT OR IGNORE INTO user_config (key, value) VALUES (:key, '0')"),
        {"key": key}
    )
    db.commit()
    
    if increment:
        # Atomic update and fetch new value
        res = db.execute(
            text(
                "UPDATE user_config "
                "SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT) "
                "WHERE key = :key AND CAST(value AS INTEGER) < :limit "
                "RETURNING value"
            ),
            {"key": key, "limit": AI_DAILY_QUOTA_LIMIT}
        )
        row = res.fetchone()
        db.commit()
        
        if not row:
            # If no row returned, it means value >= limit
            current_val_res = db.execute(
                text("SELECT value FROM user_config WHERE key = :key"),
                {"key": key}
            )
            val_row = current_val_res.fetchone()
            used = int(val_row[0]) if val_row else AI_DAILY_QUOTA_LIMIT
            raise HTTPException(
                status_code=429,
                detail=f"Daily AI request limit reached ({used}/{AI_DAILY_QUOTA_LIMIT}). Please try again tomorrow to avoid excessive API costs."
            )
    else:
        # Just check current value
        res = db.execute(
            text("SELECT value FROM user_config WHERE key = :key"),
            {"key": key}
        )
        row = res.fetchone()
        used = int(row[0]) if row else 0
        if used >= AI_DAILY_QUOTA_LIMIT:
            raise HTTPException(
                status_code=429,
                detail=f"Daily AI request limit reached ({used}/{AI_DAILY_QUOTA_LIMIT}). Please try again tomorrow to avoid excessive API costs."
            )


@app.get("/ai/quota")
def get_ai_quota(db: Session = Depends(get_db)):
    """Returns the daily AI quota usage and limit."""
    today_str = get_utc_now().strftime("%Y-%m-%d")
    key = f"ai_limit_{today_str}"
    config = db.query(UserConfig).filter(UserConfig.key == key).first()
    used = 0
    if config:
        try:
            used = int(config.value)
        except ValueError:
            used = 0
    return {"used": used, "limit": AI_DAILY_QUOTA_LIMIT}


@app.post("/submissions/analyze", response_model=SubmissionAnalyzeResponse)
def analyze_submission(req: SubmissionAnalyzeRequest, db: Session = Depends(get_db)):
    """
    Analyzes a failed submission or registers a successful one.
    Triggers LLM diagnosis for failures and updates mastery tracking.
    """
    # 1. Fetch or dynamically create the problem in the DB
    problem = db.query(Problem).filter(Problem.id == req.problem_id).first()
    if not problem:
        # Dynamically register the problem if not seeded
        problem = Problem(
            id=req.problem_id,
            title=req.problem_title,
            url=f"https://leetcode.com/problems/{req.problem_id}/",
            difficulty="Medium", # Default
            topics="Arrays & Hashing" # Fallback topic
        )
        db.add(problem)
        db.commit()
        db.refresh(problem)

    is_success = (req.verdict.lower() in ["accepted", "success"])

    # If successful, set is_solved and solved_live in problem
    if is_success:
        problem.is_solved = True
        problem.solved_live = True

    # 2. Update topic mastery & daily streak activity for each individual topic
    topic_list = [t.strip() for t in (problem.topics or "Arrays & Hashing").split(",") if t.strip()]
    if not topic_list:
        topic_list = ["Arrays & Hashing"]
    for t in topic_list:
        # Check badge test progress before modifying TopicMastery rating
        active_test = db.query(BadgeTest).filter(BadgeTest.status == "active").first()
        if active_test and (active_test.problem1_id == problem.id or active_test.problem2_id == problem.id) and is_success:
            updated = False
            if active_test.problem1_id == problem.id and not active_test.problem1_solved:
                active_test.problem1_solved = True
                updated = True
            elif active_test.problem2_id == problem.id and not active_test.problem2_solved:
                active_test.problem2_solved = True
                updated = True

            if updated:
                if active_test.problem1_solved and active_test.problem2_solved:
                    active_test.status = "passed"
                    active_test.end_time = get_utc_now()
                    # Award badge!
                    mastery = db.query(TopicMastery).filter(TopicMastery.topic == active_test.topic).first()
                    if mastery:
                        mastery.level = active_test.level
                        mastery.rating = max(mastery.rating, 800.0 + active_test.level * 240.0)
                    db.flush()

        update_mastery_on_submission(db, t, is_success=is_success, difficulty=problem.difficulty)
    _record_daily_activity(db, is_success=is_success)

    # 3. Deduplicate rapid duplicate submission calls within 15 seconds for the same problem & code
    recent_attempt = db.query(Attempt).filter(
        Attempt.problem_id == problem.id,
        Attempt.verdict == req.verdict
    ).order_by(Attempt.id.desc()).first()

    if recent_attempt and (get_utc_now() - recent_attempt.timestamp).total_seconds() < 15 and (recent_attempt.explanation_text and not req.code):
        return SubmissionAnalyzeResponse(
            root_cause_category=recent_attempt.root_cause_category or "none",
            explanation=recent_attempt.explanation_text or "Submission recorded.",
            suggested_action="Proceed to your next recommended problem."
        )

    # 4. Handle success vs failure
    if is_success:
        # Save success attempt
        attempt = Attempt(
            problem_id=problem.id,
            verdict=req.verdict,
            root_cause_category="none",
            explanation_text="Submission succeeded! No diagnosis required.",
            time_taken_seconds=req.time_taken_seconds,
            time_spent_seconds=req.time_taken_seconds,
            hints_used=req.hints_used
        )
        db.add(attempt)
        update_spaced_repetition(db, problem.id)
        db.commit()
        return SubmissionAnalyzeResponse(
            root_cause_category="none",
            explanation="Submission succeeded! Great job on solving this problem.",
            suggested_action="View the recommendation tab for your next challenge!"
        )

    # For failures, check if an assessment (Badge Test or Mock Interview) is active
    active_test = db.query(BadgeTest).filter(BadgeTest.status == "active").first()
    mock_session = db.query(MockInterviewSession).filter(MockInterviewSession.submitted_at.is_(None)).order_by(MockInterviewSession.id.desc()).first()
    is_mock_active = mock_session and (get_utc_now() - mock_session.start_time).total_seconds() <= mock_session.time_limit_seconds

    if active_test or is_mock_active:
        diagnosis = {
            "root_cause_category": "assessment_locked",
            "explanation": f"AI failure diagnosis is disabled during active {'Badge Tests' if active_test else 'Mock Interviews'} to maintain test integrity.",
            "suggested_action": "Focus on debugging your solution directly in the code editor."
        }
    else:
        # Run the LLM diagnosis if within quota
        has_quota = True
        try:
            check_and_increment_ai_quota(db, increment=True)
        except HTTPException as e:
            if e.status_code == 429:
                has_quota = False
            else:
                raise e

        if has_quota:
            diagnosis = generate_diagnosis(
                problem_title=problem.title,
                code=req.code,
                language=req.language,
                verdict=req.verdict,
                error_details=req.error_details,
                test_cases=req.test_cases
            )
        else:
            diagnosis = {
                "root_cause_category": "quota_exceeded",
                "explanation": "Daily AI request limit reached. Failure diagnostics are locked until tomorrow.",
                "suggested_action": "Keep practicing! You can still submit attempts, but AI diagnosis is currently disabled."
            }

    # Save failed attempt
    attempt = Attempt(
        problem_id=problem.id,
        verdict=req.verdict,
        root_cause_category=diagnosis["root_cause_category"],
        explanation_text=diagnosis["explanation"],
        time_taken_seconds=req.time_taken_seconds,
        time_spent_seconds=req.time_taken_seconds,
        hints_used=req.hints_used
    )
    db.add(attempt)
    db.commit()

    return SubmissionAnalyzeResponse(
        root_cause_category=diagnosis["root_cause_category"],
        explanation=diagnosis["explanation"],
        suggested_action=diagnosis["suggested_action"]
    )


@app.post("/submissions/success")
def record_success(problem_id: str, topic: str, time_taken_seconds: Optional[int] = None, db: Session = Depends(get_db)):
    """
    Direct endpoint to log a success event and update mastery.
    """
    problem = db.query(Problem).filter(Problem.id == problem_id).first()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found in database. Analyze first.")

    problem.is_solved = True
    problem.solved_live = True

    topics_to_update = [t.strip() for t in (topic or problem.topics or "Arrays & Hashing").split(",") if t.strip()]
    for t in topics_to_update:
        # Check badge test progress
        active_test = db.query(BadgeTest).filter(BadgeTest.status == "active").first()
        if active_test and active_test.topic == t:
            updated = False
            if active_test.problem1_id == problem.id and not active_test.problem1_solved:
                active_test.problem1_solved = True
                updated = True
            elif active_test.problem2_id == problem.id and not active_test.problem2_solved:
                active_test.problem2_solved = True
                updated = True

            if updated:
                if active_test.problem1_solved and active_test.problem2_solved:
                    active_test.status = "passed"
                    active_test.end_time = get_utc_now()
                    mastery = db.query(TopicMastery).filter(TopicMastery.topic == active_test.topic).first()
                    if mastery:
                        mastery.level = active_test.level
                    db.flush()

        update_mastery_on_submission(db, t, is_success=True, difficulty=problem.difficulty)

    attempt = Attempt(
        problem_id=problem.id,
        verdict="Accepted",
        root_cause_category="none",
        explanation_text="Submission succeeded!",
        time_taken_seconds=time_taken_seconds
    )
    db.add(attempt)
    update_spaced_repetition(db, problem.id)
    db.commit()
    return {"status": "success", "message": "Success logged and mastery updated."}


@app.get("/topics/mastery", response_model=List[TopicMasterySchema])
def get_mastery(db: Session = Depends(get_db)):
    """
    Returns the current mastery data for all topics.
    """
    masteries = db.query(TopicMastery).all()
    result = []
    for m in masteries:
        result.append(TopicMasterySchema(
            topic=m.topic,
            mastery_score=m.mastery_score,
            attempts_count=m.attempts_count,
            success_rate=m.success_rate,
            rating=m.rating,
            level=m.level,
            badge=m.badge,
            next_questions=[],
            last_attempted=m.last_attempted,
            next_due_date=m.next_due_date
        ))
    return result


@app.post("/badge-test/start", response_model=BadgeTestSchema)
def start_badge_test(req: BadgeTestStartRequest, db: Session = Depends(get_db)):
    # Check if there is already an active mock interview
    mock = db.query(MockInterviewSession).filter(MockInterviewSession.submitted_at.is_(None)).order_by(MockInterviewSession.id.desc()).first()
    if mock:
        elapsed = (get_utc_now() - mock.start_time).total_seconds()
        if elapsed > mock.time_limit_seconds:
            mock.submitted_at = get_utc_now()
            db.commit()
        else:
            raise HTTPException(status_code=400, detail="Cannot start a Badge Test while a Mock Interview is active.")

    # Check if there is already an active test
    active = db.query(BadgeTest).filter(BadgeTest.status == "active").first()
    if active:
        elapsed = (get_utc_now() - active.start_time).total_seconds()
        time_limit = getattr(active, 'time_limit_seconds', 5400) or 5400
        if elapsed > time_limit:
            active.status = "failed"
            db.commit()
        else:
            raise HTTPException(status_code=400, detail="A Badge Test is already active.")

    mastery = db.query(TopicMastery).filter(TopicMastery.topic == req.topic).first()
    if not mastery:
        mastery = TopicMastery(topic=req.topic, level=0, rating=1200.0)
        db.add(mastery)
        db.flush()

    target_level = mastery.level + 1
    if target_level > 5:
        raise HTTPException(status_code=400, detail="Maximum badge level (Diamond) already achieved.")

    # Select 2 non-premium problems for the test
    topic_clean = req.topic.replace("Arrays & Hashing", "Array").replace("Trees & BST", "Tree").replace("Graphs", "Graph")
    raw_problems = db.query(Problem).filter(
        Problem.topics.like(f"%{topic_clean}%"),
        Problem.is_premium == False
    ).all()
    if not raw_problems:
        raw_problems = db.query(Problem).filter(
            Problem.topics.like(f"%{req.topic}%"),
            Problem.is_premium == False
        ).all()

    # Filter out secondary conflicting tags (Trees, Graphs, BFS, DFS, DP, Trie, etc.) for pure topic tests
    problems = filter_problems_for_topic(raw_problems, req.topic)

    if target_level == 1:
        targets = ["Easy"]
    elif target_level in [2, 3]:
        targets = ["Medium"]
    elif target_level == 4:
        targets = ["Medium", "Hard"]
    else:
        targets = ["Hard"]

    candidates = [p for p in problems if p.difficulty in targets and not p.is_premium]
    if len(candidates) < 2:
        candidates = [p for p in problems if not p.is_premium]
    if len(candidates) < 2:
        candidates = filter_problems_for_topic(db.query(Problem).filter(Problem.is_premium == False).all(), req.topic)
        candidates = [p for p in candidates if not p.is_premium]

    import random
    selected = random.sample(candidates, 2) if len(candidates) >= 2 else candidates[:2]
    if len(selected) < 2:
        raise HTTPException(status_code=500, detail="Not enough problems in database to start test.")

    test = BadgeTest(
        topic=req.topic,
        level=target_level,
        problem1_id=selected[0].id,
        problem2_id=selected[1].id,
        problem1_solved=False,
        problem2_solved=False,
        time_limit_seconds=5400,
        start_time=get_utc_now()
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    now = get_utc_now()
    time_limit = getattr(test, 'time_limit_seconds', 5400) or 5400
    elapsed = int((now - test.start_time).total_seconds())

    return BadgeTestSchema(
        id=test.id,
        topic=test.topic,
        level=test.level,
        status=test.status,
        problem1=BadgeTestProblemSchema(id=selected[0].id, title=selected[0].title, url=selected[0].url, difficulty=selected[0].difficulty),
        problem2=BadgeTestProblemSchema(id=selected[1].id, title=selected[1].title, url=selected[1].url, difficulty=selected[1].difficulty),
        problem1_solved=test.problem1_solved,
        problem2_solved=test.problem2_solved,
        time_limit_seconds=time_limit,
        elapsed_seconds=elapsed,
        start_time=test.start_time,
        end_time=test.end_time
    )


@app.get("/badge-test/active", response_model=Optional[BadgeTestSchema])
def get_active_badge_test(db: Session = Depends(get_db)):
    test = db.query(BadgeTest).filter(BadgeTest.status == "active").first()
    if not test:
        return None

    now = get_utc_now()
    time_limit = getattr(test, 'time_limit_seconds', 5400) or 5400
    elapsed = int((now - test.start_time).total_seconds())

    if elapsed > time_limit:
        test.status = "expired"
        test.end_time = now
        db.commit()
        return None

    p1 = db.query(Problem).filter(Problem.id == test.problem1_id).first()
    p2 = db.query(Problem).filter(Problem.id == test.problem2_id).first()

    return BadgeTestSchema(
        id=test.id,
        topic=test.topic,
        level=test.level,
        status=test.status,
        problem1=BadgeTestProblemSchema(id=p1.id, title=p1.title, url=p1.url, difficulty=p1.difficulty),
        problem2=BadgeTestProblemSchema(id=p2.id, title=p2.title, url=p2.url, difficulty=p2.difficulty),
        problem1_solved=test.problem1_solved,
        problem2_solved=test.problem2_solved,
        time_limit_seconds=time_limit,
        elapsed_seconds=elapsed,
        start_time=test.start_time,
        end_time=test.end_time
    )


@app.post("/badge-test/abandon")
def abandon_badge_test(db: Session = Depends(get_db)):
    test = db.query(BadgeTest).filter(BadgeTest.status == "active").first()
    if not test:
        raise HTTPException(status_code=404, detail="No active Badge Test found.")
    test.status = "abandoned"
    test.end_time = get_utc_now()
    db.commit()
    return {"status": "success", "message": "Test abandoned."}


@app.get("/problems/next", response_model=ProblemRecommendResponse)
def get_recommendation(db: Session = Depends(get_db)):
    """
    Returns recommended problems (at least 3) and spaced repetition reviews.
    If a focus topic is saved in UserConfig, recommendations prioritize that topic.
    """
    cfg = db.query(UserConfig).filter(UserConfig.key == FOCUS_KEY).first()
    focus_topic = cfg.value if cfg else None
    result = get_next_problem(db, focus_topic=focus_topic)
    return ProblemRecommendResponse(
        recommendations=result["recommendations"],
        reviews=result["reviews"]
    )


@app.get("/health")
def health():
    """Lightweight liveness probe used by the extension footer."""
    return {"status": "ok"}


@app.post("/approach/check", response_model=CheckApproachResponse)
def check_approach(req: CheckApproachRequest, db: Session = Depends(get_db)):
    """Critiques the user's approach and suggests optimizations."""
    check_active_test_lock(db, is_contest=req.is_contest)
    check_and_increment_ai_quota(db)
    result = generate_approach_critique(
        problem_title=req.problem_title,
        code=req.code,
        language=req.language,
        constraints=req.constraints
    )
    return CheckApproachResponse(
        verdict=result.get("verdict", "Critique complete"),
        explanation=result.get("explanation") or result.get("feedback", ""),
        suggested_action=result.get("suggested_action") or result.get("alternative_approach", "")
    )


@app.post("/hints/get", response_model=GetHintResponse)
def get_hint(req: GetHintRequest, db: Session = Depends(get_db)):
    """Provides a progressive, conceptual hint without revealing the solution."""
    check_active_test_lock(db, is_contest=req.is_contest)
    check_and_increment_ai_quota(db)
    result = generate_hint(
        problem_title=req.problem_title,
        code=req.code,
        language=req.language,
        constraints=req.constraints
    )
    return GetHintResponse(hint=result.get("hint", ""), level=req.level or 1, has_next=(req.level or 1) < 3)


@app.post("/hints/reveal", response_model=HintRevealResponse)
def reveal_hint(req: HintRevealRequest, db: Session = Depends(get_db)):
    """Provides a progressive, conceptual hint at the requested level (1, 2, or 3)."""
    check_active_test_lock(db, is_contest=req.is_contest)
    check_and_increment_ai_quota(db)
    result = generate_levelled_hint(
        problem_title=req.problem_title,
        code=req.code,
        language=req.language,
        level=req.level,
        constraints=req.constraints
    )
    return HintRevealResponse(
        hint=result.get("hint", ""),
        level=result.get("level", req.level),
        has_next=result.get("has_next", req.level < 3)
    )


@app.post("/edge-cases/get", response_model=GetEdgeCasesResponse)
def get_edge_cases(req: GetEdgeCasesRequest, db: Session = Depends(get_db)):
    """Identifies potential edge cases and critiques the problem constraints."""
    check_active_test_lock(db, is_contest=req.is_contest)
    check_and_increment_ai_quota(db)
    result = analyze_edge_cases(
        problem_title=req.problem_title,
        code=req.code,
        language=req.language,
        constraints=req.constraints
    )
    return GetEdgeCasesResponse(
        edge_cases=result.get("edge_cases", []),
        constraints_critique=result.get("constraints_critique", "")
    )


@app.post("/help/ask", response_model=AskHelpResponse)
def ask_help(req: AskHelpRequest, db: Session = Depends(get_db)):
    """Answers a user's custom question about their code or the problem."""
    check_active_test_lock(db, is_contest=req.is_contest)
    check_and_increment_ai_quota(db)
    result = answer_custom_question(
        problem_title=req.problem_title,
        code=req.code,
        language=req.language,
        constraints=req.constraints,
        question=req.question
    )
    return AskHelpResponse(answer=result.get("answer", ""))


@app.post("/sync/solved")
def sync_solved(req: SyncSolvedRequest, db: Session = Depends(get_db)):
    """
    Imports already-solved LeetCode problems from the user's history.

    For each problem: upserts the Problem (marked is_solved=True) and tallies
    per-topic solved counts. For each topic touched, seeds TopicMastery:
    attempts_count = solved_count and mastery_score from the log formula — but
    ONLY when solved_count > existing attempts_count, so live tracking data is
    never overwritten. success_rate is left at 0 (we have no real attempts yet).
    """
    topics_seen = set()
    solved_per_topic = Counter()

    prob_ids = [p.problem_id for p in req.problems if p.problem_id]
    existing_problems = {
        p.id: p for p in db.query(Problem).filter(Problem.id.in_(prob_ids)).all()
    } if prob_ids else {}

    existing_srs = {
        sr.problem_id: sr for sr in db.query(SpacedRepetition).filter(SpacedRepetition.problem_id.in_(prob_ids)).all()
    } if prob_ids else {}

    now_utc = get_utc_now()
    due_utc = now_utc + timedelta(days=3)

    # 1. Upsert each problem (mark solved) and collect per-topic solved counts.
    for prob in req.problems:
        topics_csv = ", ".join(prob.topics) if prob.topics else "Arrays & Hashing"
        for t in [t.strip() for t in topics_csv.split(",") if t.strip()]:
            topics_seen.add(t)
            solved_per_topic[t] += 1

        url = f"https://leetcode.com/problems/{prob.problem_id}/"
        problem = existing_problems.get(prob.problem_id)
        if problem:
            # Refresh metadata for a previously seen problem
            problem.title = prob.title or problem.title
            problem.url = url
            problem.difficulty = prob.difficulty or problem.difficulty
            problem.topics = topics_csv
            problem.is_solved = True
        else:
            problem = Problem(
                id=prob.problem_id,
                title=prob.title or prob.problem_id,
                url=url,
                difficulty=prob.difficulty or "Medium",
                topics=topics_csv,
                is_solved=True
            )
            db.add(problem)

        # Seed initial spaced repetition schedule for solved problem (due in 3 days)
        if prob.problem_id not in existing_srs:
            sr = SpacedRepetition(
                problem_id=prob.problem_id,
                stage=1,
                last_solved=now_utc,
                next_due=due_utc
            )
            db.add(sr)

    # 2. Seed per-topic mastery from solved counts (never clobber live data).
    existing_masteries = {
        tm.topic: tm for tm in db.query(TopicMastery).filter(TopicMastery.topic.in_(list(topics_seen))).all()
    } if topics_seen else {}

    new_topics = 0
    seeded_topics = 0
    for topic in topics_seen:
        solved_count = solved_per_topic[topic]
        mastery = existing_masteries.get(topic)
        if not mastery:
            # Brand-new topic: seed with level 0 (Locked badge)
            mastery = TopicMastery(
                topic=topic,
                rating=800.0,
                attempts_count=solved_count,
                success_count=0,
                level=0
            )
            db.add(mastery)
            new_topics += 1
            seeded_topics += 1
        elif solved_count > mastery.attempts_count:
            mastery.attempts_count = solved_count
            seeded_topics += 1

    db.commit()
    synced = len(req.problems)
    return {
        "synced": synced,
        "topics": len(topics_seen),
        "new_topics": new_topics,
        "seeded_topics": seeded_topics,
        "message": f"Synced {synced} problem(s) across {len(topics_seen)} topic(s); seeded {seeded_topics} topic(s)."
    }


@app.get("/reviews/count")
def get_reviews_count(db: Session = Depends(get_db)):
    """Returns count of active spaced repetition reviews due today (Tier 1.2)."""
    now = get_utc_now()
    due_count = db.query(SpacedRepetition).filter(
        SpacedRepetition.next_due <= now,
        SpacedRepetition.stage < 5
    ).count()
    return {"due_count": due_count}


@app.post("/reviews/clear")
def clear_reviews(db: Session = Depends(get_db)):
    """Clears all spaced repetition review records from the database."""
    deleted = db.query(SpacedRepetition).delete()
    db.commit()
    return {"deleted": deleted, "message": f"Cleared {deleted} review records."}


@app.get("/topics/analysis", response_model=TopicAnalysisResponse)
def get_topic_analysis(db: Session = Depends(get_db)):
    """Full breakdown of solved problems: difficulty + per-topic counts + weakest topics."""
    solved_problems = db.query(Problem).filter(Problem.is_solved == True).all()  # noqa: E712

    # Difficulty breakdown
    difficulty_counts = {"Easy": 0, "Medium": 0, "Hard": 0}
    for p in solved_problems:
        diff = (p.difficulty or "").capitalize()
        if diff in difficulty_counts:
            difficulty_counts[diff] += 1

    # Per-topic solved counts
    topic_solved = Counter()
    for p in solved_problems:
        for t in [x.strip() for x in (p.topics or "").split(",") if x.strip()]:
            topic_solved[t] += 1

    # Join with mastery scores
    mastery_rows = {m.topic: m for m in db.query(TopicMastery).all()}
    items = []
    for topic, count in topic_solved.items():
        score = mastery_rows.get(topic).mastery_score if topic in mastery_rows else 0.0
        badge = mastery_rows.get(topic).badge if topic in mastery_rows else "None"
        items.append(TopicStatItem(topic=topic, solved_count=count, mastery_score=score or 0.0, badge=badge))

    top_topics = sorted(items, key=lambda x: x.solved_count, reverse=True)

    # Weakest topics: lowest mastery among all known topics, capped at 5
    all_items = []
    for topic, m in mastery_rows.items():
        all_items.append(TopicStatItem(
            topic=topic,
            solved_count=topic_solved.get(topic, 0),
            mastery_score=m.mastery_score or 0.0,
            badge=m.badge
        ))
    weak_topics = sorted(all_items, key=lambda x: x.mastery_score)[:5]

    return TopicAnalysisResponse(
        total_solved=len(solved_problems),
        difficulty_breakdown=difficulty_counts,
        top_topics=top_topics,
        weak_topics=weak_topics
    )


@app.get("/topics/focus", response_model=FocusResponse)
def get_focus(db: Session = Depends(get_db)):
    """Returns the saved focus topics (up to 3)."""
    cfg = db.query(UserConfig).filter(UserConfig.key == FOCUS_KEY).first()
    val = cfg.value if cfg else ""
    topics = [t.strip() for t in val.split(",") if t.strip()] if val else []
    return FocusResponse(focus_topic=val if val else None, focus_topics=topics)


@app.post("/topics/focus", response_model=FocusResponse)
def set_focus(req: Optional[SetFocusRequest] = None, topic: Optional[str] = None, db: Session = Depends(get_db)):
    """Saves (or clears) focus topics (up to 3)."""
    val_to_save = []
    if req and req.topics is not None:
        val_to_save = [t.strip() for t in req.topics if t and t.strip()][:3]
    elif req and req.topic is not None:
        val_to_save = [t.strip() for t in req.topic.split(",") if t and t.strip()][:3]
    elif topic is not None:
        val_to_save = [t.strip() for t in topic.split(",") if t and t.strip()][:3]

    cfg = db.query(UserConfig).filter(UserConfig.key == FOCUS_KEY).first()
    if not val_to_save:
        if cfg:
            db.delete(cfg)
        saved_str = None
        topics_out = []
    else:
        saved_str = ",".join(val_to_save)
        if cfg:
            cfg.value = saved_str
        else:
            cfg = UserConfig(key=FOCUS_KEY, value=saved_str)
            db.add(cfg)
        topics_out = val_to_save

    db.commit()
    return FocusResponse(focus_topic=saved_str, focus_topics=topics_out)


@app.get("/companies")
def get_companies(db: Session = Depends(get_db)):
    """Returns distinct list of company tags from all registered problems (Tier 1.1)."""
    problems = db.query(Problem).filter(Problem.companies.isnot(None)).all()
    companies = set()
    for p in problems:
        if p.companies:
            for c in [x.strip() for x in p.companies.split(",") if x.strip()]:
                companies.add(c)
    return sorted(list(companies))


@app.get("/companies/metadata")
def get_companies_metadata(db: Session = Depends(get_db)):
    """Returns a dictionary mapping company names to their focus notes."""
    meta = db.query(CompanyMetadata).all()
    return {m.name: m.focus_note for m in meta}


@app.get("/reviews/count")
def get_reviews_count(db: Session = Depends(get_db)):
    """Returns count of active spaced repetition reviews due today (Tier 1.2)."""
    now = get_utc_now()
    due_count = db.query(SpacedRepetition).filter(
        SpacedRepetition.next_due <= now,
        SpacedRepetition.stage < 5
    ).count()
    return {"due_count": due_count}


@app.get("/activity/streak", response_model=StreakResponse)
def get_streak(db: Session = Depends(get_db)):
    """Returns current streak days and today's activity counts (Tier 1.4)."""
    today_str = get_utc_now().strftime("%Y-%m-%d")
    today_act = db.query(DailyActivity).filter(DailyActivity.date == today_str).first()
    problems_today = today_act.problems_attempted if today_act else 0
    solved_today = today_act.problems_solved if today_act else 0

    # Calculate streak walking backwards
    streak = 0
    curr_date = get_utc_now().date()
    while True:
        d_str = curr_date.strftime("%Y-%m-%d")
        act = db.query(DailyActivity).filter(DailyActivity.date == d_str).first()
        if act and act.problems_solved > 0:
            streak += 1
            curr_date -= timedelta(days=1)
        elif d_str == today_str:
            # If today hasn't solved anything yet, check yesterday
            curr_date -= timedelta(days=1)
        else:
            break

    return StreakResponse(
        current_streak_days=streak,
        problems_today=problems_today,
        solved_today=solved_today
    )


@app.get("/topics/weak-pairs", response_model=List[WeakPairItem])
def get_weak_pairs(db: Session = Depends(get_db)):
    """Returns co-occurring weak topic pairs (Tier 2.1)."""
    return compute_weak_pairs(db)


@app.get("/topics/time-trend")
def get_time_trend(topic: str, db: Session = Depends(get_db)):
    """Returns recent time-spent attempts for a topic (Tier 1.3)."""
    return get_topic_time_trend(db, topic)


@app.post("/submissions/explain-back", response_model=ExplainBackResponse)
def explain_back(req: ExplainBackRequest, db: Session = Depends(get_db)):
    """Verifies user's self-explanation against their submitted code (Tier 3.2)."""
    check_active_test_lock(db, is_contest=req.is_contest)
    check_and_increment_ai_quota(db)
    res = generate_explain_back_check(
        code=req.code,
        language=req.language,
        user_explanation=req.user_explanation
    )
    return ExplainBackResponse(
        matches=bool(res.get("matches", True)),
        discrepancy_note=res.get("discrepancy_note")
    )


@app.post("/critique/estimate")
def store_complexity_estimate(req: ComplexityEstimateRequest, db: Session = Depends(get_db)):
    """Stores the user's complexity guess before revealing critique (Tier 3.3)."""
    check_active_test_lock(db, is_contest=req.is_contest)
    import json
    key = f"estimate_{req.problem_id}"
    value = json.dumps({"time_complexity": req.time_complexity, "space_complexity": req.space_complexity})
    cfg = db.query(UserConfig).filter(UserConfig.key == key).first()
    if cfg:
        cfg.value = value
    else:
        cfg = UserConfig(key=key, value=value)
        db.add(cfg)
    db.commit()
    return {"status": "stored"}


@app.post("/critique/reveal", response_model=ComplexityRevealResponse)
def reveal_complexity_critique(req: ComplexityRevealRequest, db: Session = Depends(get_db)):
    """Runs LLM approach critique and compares with stored self-estimate (Tier 3.3)."""
    check_active_test_lock(db, is_contest=req.is_contest)
    check_and_increment_ai_quota(db)
    import json
    key = f"estimate_{req.problem_id}"
    cfg = db.query(UserConfig).filter(UserConfig.key == key).first()
    estimate = json.loads(cfg.value) if cfg and cfg.value else None

    result = generate_approach_critique(
        problem_title=req.problem_title,
        code=req.code,
        language=req.language,
        constraints=req.constraints
    )

    return ComplexityRevealResponse(
        estimate=estimate,
        is_optimal=bool(result.get("is_optimal", False)),
        current_complexity=result.get("current_complexity", "Unknown"),
        optimal_complexity=result.get("optimal_complexity", "Unknown"),
        feedback=result.get("feedback", ""),
        alternative_approach=result.get("alternative_approach", "")
    )


class MockSwitchRequest(BaseModel):
    session_id: int
    target_index: int


@app.post("/mock-interview/start", response_model=MockStartResponse)
def start_mock_interview(req: MockStartRequest, db: Session = Depends(get_db)):
    """Starts a timed mock interview session with 3 randomized questions (Tier 4.1)."""
    import random

    active_test = db.query(BadgeTest).filter(BadgeTest.status == "active").first()
    if active_test:
        raise HTTPException(status_code=400, detail="Cannot start a Mock Interview while a Badge Test is active.")

    # 1. Fetch recently used problem IDs from past mock sessions to avoid repeats
    past_sessions = db.query(MockInterviewSession).order_by(MockInterviewSession.id.desc()).limit(15).all()
    recently_used_ids = set()
    for s in past_sessions:
        if s.problem_ids:
            for pid in s.problem_ids.split(","):
                if pid.strip():
                    recently_used_ids.add(pid.strip())

    # 2. Build candidate problem pool
    candidate_pool = []
    if req.company:
        company_probs = db.query(Problem).filter(
            Problem.companies.like(f"%{req.company}%"),
            Problem.is_premium == False
        ).all()
        if len(company_probs) >= 15:
            candidate_pool = company_probs
        else:
            # Combine specific company problems with general non-premium problem pool to ensure rich variety
            all_non_prem = db.query(Problem).filter(Problem.is_premium == False).all()
            # Order company_probs first, followed by general problems
            seen = set()
            for p in company_probs + all_non_prem:
                if p.id not in seen:
                    seen.add(p.id)
                    candidate_pool.append(p)
    else:
        candidate_pool = db.query(Problem).filter(Problem.is_premium == False).all()

    # 3. Filter out recently used problems if enough fresh problems exist
    fresh_pool = [p for p in candidate_pool if p.id not in recently_used_ids]
    if len(fresh_pool) < 3:
        fresh_pool = candidate_pool

    if not fresh_pool:
        raise HTTPException(status_code=404, detail="No suitable problems found for mock interview.")

    # 4. Partition by difficulty to select 1 Easy, 1 Medium, 1 Hard (or balanced mix)
    easy_pool = [p for p in fresh_pool if p.difficulty == "Easy"]
    medium_pool = [p for p in fresh_pool if p.difficulty == "Medium"]
    hard_pool = [p for p in fresh_pool if p.difficulty == "Hard"]

    selected_probs = []
    
    # Pick 1 Easy
    if easy_pool:
        p_easy = random.choice(easy_pool)
        selected_probs.append(p_easy)
        fresh_pool = [p for p in fresh_pool if p.id != p_easy.id]

    # Pick 1 Medium
    medium_pool = [p for p in fresh_pool if p.difficulty == "Medium"]
    if medium_pool:
        p_med = random.choice(medium_pool)
        selected_probs.append(p_med)
        fresh_pool = [p for p in fresh_pool if p.id != p_med.id]

    # Pick 1 Hard (or 2nd Medium / remaining)
    hard_or_med_pool = [p for p in fresh_pool if p.difficulty in ["Hard", "Medium"]]
    if not hard_or_med_pool:
        hard_or_med_pool = fresh_pool

    if hard_or_med_pool:
        p_third = random.choice(hard_or_med_pool)
        selected_probs.append(p_third)
        fresh_pool = [p for p in fresh_pool if p.id != p_third.id]

    # Fill up if less than 3
    while len(selected_probs) < 3 and fresh_pool:
        p_next = random.choice(fresh_pool)
        selected_probs.append(p_next)
        fresh_pool = [p for p in fresh_pool if p.id != p_next.id]

    # Backup fill from all candidate problems if still needed
    if len(selected_probs) < 3:
        remaining = [p for p in candidate_pool if p not in selected_probs]
        while len(selected_probs) < 3 and remaining:
            p_rem = random.choice(remaining)
            selected_probs.append(p_rem)
            remaining.remove(p_rem)

    # Final fallback if pool was tiny
    while len(selected_probs) < 3 and selected_probs:
        selected_probs.append(selected_probs[0])

    # Shuffle selected 3 problems
    random.shuffle(selected_probs)
    probs = selected_probs[:3]
    
    problem_ids_str = ",".join([p.id for p in probs])

    # 5. Create MockInterviewSession record
    import json
    session = MockInterviewSession(
        problem_id=probs[0].id,
        time_limit_seconds=req.time_limit_seconds,
        company=req.company,
        problem_ids=problem_ids_str,
        current_question_index=0,
        approaches_submitted="0,0,0",
        approaches_text=json.dumps(["", "", ""])
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # 6. Build list of metadata for 3 questions
    problem_titles = [p.title for p in probs]
    problem_urls = [p.url for p in probs]
    difficulties = [p.difficulty for p in probs]
    approaches_submitted_list = [False, False, False]

    return MockStartResponse(
        session_id=session.id,
        problem_id=probs[0].id,
        problem_title=probs[0].title,
        problem_url=probs[0].url,
        difficulty=probs[0].difficulty,
        topics=probs[0].topics or "",
        time_limit_seconds=session.time_limit_seconds,
        approach_submitted=False,
        current_question_index=0,
        problem_ids=[p.id for p in probs],
        problem_titles=problem_titles,
        problem_urls=problem_urls,
        difficulties=difficulties,
        approaches_submitted_list=approaches_submitted_list
    )


@app.get("/mock-interview/active")
def get_active_mock_interview(db: Session = Depends(get_db)):
    """Fetches the current active mock interview session if it hasn't been submitted yet."""
    session = db.query(MockInterviewSession).filter(MockInterviewSession.submitted_at.is_(None)).order_by(MockInterviewSession.id.desc()).first()
    if not session:
        return None
        
    # Check if time is exceeded
    elapsed = (get_utc_now() - session.start_time).total_seconds()
    if elapsed > session.time_limit_seconds:
        return None

    # Parse multi-problem lists
    problem_ids_str = session.problem_ids
    if not problem_ids_str:
        problem_ids_str = session.problem_id
        
    problem_ids = [pid.strip() for pid in problem_ids_str.split(",") if pid.strip()]
    probs = [db.query(Problem).filter(Problem.id == pid).first() for pid in problem_ids]
    probs = [p for p in probs if p is not None]
    
    if not probs:
        return None
        
    while len(probs) < 3:
        probs.append(probs[0])
        
    cur_idx = session.current_question_index
    if cur_idx >= len(probs):
        cur_idx = 0
        
    cur_prob = probs[cur_idx]
    
    # Parse approaches submitted status
    appr_sub = [False, False, False]
    if session.approaches_submitted:
        parts = session.approaches_submitted.split(",")
        for idx, val in enumerate(parts):
            if idx < len(appr_sub):
                appr_sub[idx] = (val.strip() == "1")
                
    import json
    appr_texts = ["", "", ""]
    if session.approaches_text:
        try:
            appr_texts = json.loads(session.approaches_text)
        except Exception:
            pass

    ai_feedbacks = ["", "", ""]
    if session.ai_feedback:
        try:
            ai_feedbacks = json.loads(session.ai_feedback)
        except Exception:
            pass

    scorecard_data = None
    if session.scorecard:
        try:
            scorecard_data = json.loads(session.scorecard)
        except Exception:
            pass

    return {
        "session_id": session.id,
        "problem_id": cur_prob.id,
        "problem_title": cur_prob.title,
        "problem_url": cur_prob.url,
        "difficulty": cur_prob.difficulty,
        "topics": cur_prob.topics or "",
        "time_limit_seconds": session.time_limit_seconds,
        "start_time": session.start_time,
        "elapsed_seconds": int(elapsed),
        "approach_submitted": appr_sub[cur_idx],
        "current_question_index": cur_idx,
        "problem_ids": [p.id for p in probs],
        "problem_titles": [p.title for p in probs],
        "problem_urls": [p.url for p in probs],
        "difficulties": [p.difficulty for p in probs],
        "approaches_submitted_list": appr_sub,
        "approaches_text_list": appr_texts,
        "ai_feedback_list": ai_feedbacks,
        "scorecard": scorecard_data
    }


@app.post("/mock-interview/approach")
def submit_mock_approach(req: MockApproachRequest, db: Session = Depends(get_db)):
    """Records the approach explanation before unlocking code editor and provides AI feedback."""
    session = db.query(MockInterviewSession).filter(MockInterviewSession.id == req.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Mock session not found.")

    cur_idx = session.current_question_index

    # Generate AI Interviewer Feedback on the strategy
    problem_ids = [pid.strip() for pid in (session.problem_ids or "").split(",") if pid.strip()]
    cur_prob_id = problem_ids[cur_idx] if cur_idx < len(problem_ids) else session.problem_id
    cur_prob = db.query(Problem).filter(Problem.id == cur_prob_id).first()
    prob_title = cur_prob.title if cur_prob else cur_prob_id

    from backend.agent import evaluate_mock_approach
    eval_res = evaluate_mock_approach(prob_title, req.approach_text)
    is_approved = eval_res.get("approved", False)

    appr_sub = ["0", "0", "0"]
    if session.approaches_submitted:
        parts = [p.strip() for p in session.approaches_submitted.split(",")]
        for idx, val in enumerate(parts):
            if idx < len(appr_sub):
                appr_sub[idx] = val

    if cur_idx < len(appr_sub):
        appr_sub[cur_idx] = "1" if is_approved else "0"

    session.approaches_submitted = ",".join(appr_sub)

    import json
    appr_texts = ["", "", ""]
    if session.approaches_text:
        try:
            appr_texts = json.loads(session.approaches_text)
        except Exception:
            pass

    while len(appr_texts) < 3:
        appr_texts.append("")

    if cur_idx < len(appr_texts):
        appr_texts[cur_idx] = req.approach_text

    session.approaches_text = json.dumps(appr_texts)
    session.approach_submitted_at = get_utc_now()

    ai_feedbacks = ["", "", ""]
    if session.ai_feedback:
        try:
            ai_feedbacks = json.loads(session.ai_feedback)
        except Exception:
            pass
    while len(ai_feedbacks) < 3:
        ai_feedbacks.append("")
    ai_feedbacks[cur_idx] = eval_res.get("feedback", "")
    session.ai_feedback = json.dumps(ai_feedbacks)

    db.commit()
    return {
        "status": "approach_accepted" if is_approved else "approach_rejected",
        "session_id": session.id,
        "feedback": eval_res.get("feedback", ""),
        "approved": is_approved
    }


class MockEvaluateRequest(BaseModel):
    session_id: int


@app.post("/mock-interview/evaluate")
def evaluate_mock_session(req: MockEvaluateRequest, db: Session = Depends(get_db)):
    """Generates an AI interviewer evaluation scorecard for the mock interview session."""
    session = db.query(MockInterviewSession).filter(MockInterviewSession.id == req.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Mock session not found.")
    
    import json
    from backend.agent import generate_mock_scorecard
    
    prob_ids = [p.strip() for p in (session.problem_ids or "").split(",") if p.strip()]
    appr_texts = json.loads(session.approaches_text) if session.approaches_text else ["", "", ""]
    
    session_start = session.start_time

    questions_data = []
    for idx, pid in enumerate(prob_ids):
        p = db.query(Problem).filter(Problem.id == pid).first()
        
        # Query ONLY attempts submitted DURING or AFTER this mock interview session start
        session_attempts = db.query(Attempt).filter(
            Attempt.problem_id == pid,
            Attempt.timestamp >= session_start
        ).order_by(Attempt.timestamp.asc()).all()

        attempts_count = len(session_attempts)
        is_solved = any(a.verdict == "Accepted" for a in session_attempts)
        latest_verdict = session_attempts[-1].verdict if session_attempts else "Not Submitted"

        questions_data.append({
            "title": p.title if p else pid,
            "difficulty": p.difficulty if p else "Medium",
            "approach": appr_texts[idx] if idx < len(appr_texts) else "",
            "attempts_in_session": attempts_count,
            "session_status": "Solved (Accepted)" if is_solved else (f"Attempted ({latest_verdict})" if attempts_count > 0 else "Not Submitted")
        })
        
    duration = session.time_taken_seconds or int((get_utc_now() - session.start_time).total_seconds())
    card = generate_mock_scorecard(session.company, duration, questions_data)
    session.scorecard = json.dumps(card)
    db.commit()
    return card


@app.post("/mock-interview/switch")
def switch_mock_question(req: MockSwitchRequest, db: Session = Depends(get_db)):
    """Switches the active question index in the mock session (Tier 4.1)."""
    session = db.query(MockInterviewSession).filter(MockInterviewSession.id == req.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Mock session not found.")
        
    if req.target_index < 0 or req.target_index >= 3:
        raise HTTPException(status_code=400, detail="Invalid target index. Must be between 0 and 2.")
        
    session.current_question_index = req.target_index
    
    problem_ids = [pid.strip() for pid in session.problem_ids.split(",") if pid.strip()]
    if req.target_index < len(problem_ids):
        session.problem_id = problem_ids[req.target_index]
        
    db.commit()
    return {"status": "question_switched", "session_id": session.id, "current_question_index": session.current_question_index}


@app.post("/mock-interview/submit")
def submit_mock_solution(req: MockSubmitRequest, db: Session = Depends(get_db)):
    """Submits final code for a mock interview session (Tier 4.1)."""
    session = db.query(MockInterviewSession).filter(MockInterviewSession.id == req.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Mock session not found.")

    now = get_utc_now()
    session.submitted_at = now
    elapsed = int((now - session.start_time).total_seconds())
    session.time_taken_seconds = elapsed
    db.commit()

    # Check if an attempt was already recorded during this session
    session_attempts = db.query(Attempt).filter(
        Attempt.problem_id == req.problem_id,
        Attempt.timestamp >= session.start_time
    ).all()

    if not session_attempts:
        sub_req = SubmissionAnalyzeRequest(
            problem_id=req.problem_id,
            problem_title=req.problem_title,
            code=req.code,
            language=req.language,
            verdict="Accepted",
            time_taken_seconds=elapsed,
            hints_used=0
        )
        return analyze_submission(sub_req, db)

    return SubmissionAnalyzeResponse(
        root_cause_category="none",
        explanation="Mock interview session completed!",
        suggested_action="View your mock interview performance report."
    )


@app.get("/mock-interview/report")
def get_mock_interview_report(db: Session = Depends(get_db)):
    """Generates a complete, highly detailed markdown report of all mock interview sessions."""
    sessions = db.query(MockInterviewSession).order_by(MockInterviewSession.id.desc()).all()
    
    if not sessions:
        return "# 📊 Mock Interview History & Performance Report\n\nNo mock interviews found. Start a mock interview to generate a report!"

    import json

    total_sessions = len(sessions)
    completed_sessions = sum(1 for s in sessions if s.submitted_at is not None)
    
    companies = set(s.company for s in sessions if s.company)
    companies_str = ", ".join(sorted(list(companies))) if companies else "General Tech"

    # Aggregates for report header
    verdict_counts = {"Strong Hire": 0, "Hire": 0, "Weak Lean": 0, "Needs Practice": 0}
    all_weak_areas = []
    all_strengths = []
    
    # Process scorecards for summary stats
    for s in sessions:
        card = None
        if s.scorecard:
            try:
                card = json.loads(s.scorecard)
            except Exception:
                card = None
        
        if card and isinstance(card, dict):
            v = card.get("verdict", "")
            if v in verdict_counts:
                verdict_counts[v] += 1
            if card.get("areas_for_improvement"):
                all_weak_areas.extend(card.get("areas_for_improvement"))
            if card.get("strengths"):
                all_strengths.extend(card.get("strengths"))

    verdict_str = ", ".join([f"{k}: {v}" for k, v in verdict_counts.items() if v > 0]) or "Pending Evaluation"

    # Deduplicate weak areas & strengths for header summary
    unique_weak_areas = list(dict.fromkeys(all_weak_areas))[:5]
    unique_strengths = list(dict.fromkeys(all_strengths))[:5]

    md = [
        "# 📊 Mock Interview Performance & Diagnostic Report",
        f"**Generated on**: `{get_utc_now().strftime('%Y-%m-%d %H:%M:%S')} UTC`",
        "",
        "## 📈 Executive Performance Summary",
        f"- **Total Mock Sessions**: {total_sessions}",
        f"- **Completed Sessions**: {completed_sessions} / {total_sessions}",
        f"- **Target Companies**: {companies_str}",
        f"- **Interviewer Verdict Breakdown**: {verdict_str}",
        ""
    ]

    if unique_weak_areas:
        md.append("### ⚠️ Key Weak Areas & Focus Topics Across Sessions")
        for area in unique_weak_areas:
            md.append(f"- 🔸 {area}")
        md.append("")

    if unique_strengths:
        md.append("### 🌟 Key Candidate Strengths")
        for st in unique_strengths:
            md.append(f"- 🔹 {st}")
        md.append("")

    md.append("---")
    md.append("")

    # Detailed session breakdown
    for s in sessions:
        company_tag = f" ({s.company})" if s.company else ""
        status = "Completed" if s.submitted_at else "Active / Incomplete"
        date_str = s.start_time.strftime('%Y-%m-%d %H:%M:%S')
        
        md.append(f"## 🏆 Session #{s.id}: Mock Interview{company_tag}")
        md.append(f"- **Start Time**: {date_str}")
        md.append(f"- **Status**: `{status}`")
        md.append(f"- **Time Limit**: {s.time_limit_seconds // 60} minutes")
        if s.submitted_at:
            time_taken = s.time_taken_seconds or 0
            md.append(f"- **Time Taken**: {time_taken // 60} min {time_taken % 60} sec")
        md.append("")
        
        # 1. AI Interviewer Scorecard Section
        card = None
        if s.scorecard:
            try:
                card = json.loads(s.scorecard)
            except Exception:
                card = None
                
        if not card:
            from backend.agent import generate_mock_scorecard
            prob_ids_raw = [p.strip() for p in (s.problem_ids or s.problem_id or "").split(",") if p.strip()]
            appr_texts_raw = []
            if s.approaches_text:
                try:
                    appr_texts_raw = json.loads(s.approaches_text)
                except Exception:
                    pass
            q_data = []
            session_start = s.start_time
            for idx, pid in enumerate(prob_ids_raw):
                p = db.query(Problem).filter(Problem.id == pid).first()
                s_attempts = db.query(Attempt).filter(
                    Attempt.problem_id == pid,
                    Attempt.timestamp >= session_start
                ).order_by(Attempt.timestamp.asc()).all()
                q_data.append({
                    "title": p.title if p else pid,
                    "difficulty": p.difficulty if p else "Medium",
                    "approach": appr_texts_raw[idx] if idx < len(appr_texts_raw) else "",
                    "attempts_in_session": len(s_attempts),
                    "session_status": "Solved (Accepted)" if any(a.verdict == "Accepted" for a in s_attempts) else ("Attempted" if s_attempts else "Not Submitted")
                })
            duration = s.time_taken_seconds or int((get_utc_now() - s.start_time).total_seconds())
            try:
                card = generate_mock_scorecard(s.company, duration, q_data)
                s.scorecard = json.dumps(card)
                db.commit()
            except Exception:
                card = {
                    "verdict": "Hire",
                    "strategy_score": 4,
                    "code_quality_score": 4,
                    "time_management_score": 4,
                    "overall_summary": "Session recorded with technical approaches provided.",
                    "strengths": ["Structured problem solving approach"],
                    "areas_for_improvement": ["Focus on edge case validation"]
                }

        verdict_badge = {
            "Strong Hire": "🟢 Strong Hire",
            "Hire": "🟢 Hire",
            "Weak Lean": "⚠️ Weak Lean",
            "Needs Practice": "🔴 Needs Practice"
        }.get(card.get("verdict"), card.get("verdict", "Evaluated"))

        md.append("### 📋 AI Interviewer Scorecard & Verdict")
        md.append(f"- **Final Verdict**: `{verdict_badge}`")
        md.append(f"- **Strategy & Communication Score**: `{card.get('strategy_score', 'N/A')}/5`")
        md.append(f"- **Code Quality & Correctness Score**: `{card.get('code_quality_score', 'N/A')}/5`")
        md.append(f"- **Time Management Score**: `{card.get('time_management_score', 'N/A')}/5`")
        md.append("")
        md.append(f"**Interviewer Summary**:")
        md.append(f"> {card.get('overall_summary', 'No summary available.')}")
        md.append("")

        if card.get("strengths"):
            md.append("**Strengths Identified**:")
            for item in card["strengths"]:
                md.append(f"  - ✅ {item}")
            md.append("")

        if card.get("areas_for_improvement"):
            md.append("**Weak Areas / Areas for Improvement**:")
            for item in card["areas_for_improvement"]:
                md.append(f"  - ⚠️ {item}")
            md.append("")

        # 2. Questions & Code Submissions Breakdown
        problem_ids_str = s.problem_ids or s.problem_id
        problem_ids = [pid.strip() for pid in problem_ids_str.split(",") if pid.strip()]
        
        appr_sub = [False] * len(problem_ids)
        if s.approaches_submitted:
            parts = [p.strip() for p in s.approaches_submitted.split(",")]
            for idx, val in enumerate(parts):
                if idx < len(appr_sub):
                    appr_sub[idx] = (val == "1")
                    
        appr_texts = [""] * len(problem_ids)
        if s.approaches_text:
            try:
                appr_texts = json.loads(s.approaches_text)
            except Exception:
                pass
                
        ai_feedback_list = [""] * len(problem_ids)
        if s.ai_feedback:
            try:
                ai_feedback_list = json.loads(s.ai_feedback)
            except Exception:
                pass

        md.append("### 🧩 Questions, Strategy & Execution Details")
        session_start = s.start_time

        for idx, pid in enumerate(problem_ids):
            prob = db.query(Problem).filter(Problem.id == pid).first()
            title = prob.title if prob else pid
            diff = prob.difficulty if prob else "Unknown"
            url = prob.url if prob else f"https://leetcode.com/problems/{pid}/"
            
            md.append(f"#### Q{idx + 1}: {title} (`{diff}`)")
            md.append(f"- **LeetCode URL**: [{title}]({url})")
            
            sub_status = "🔓 Approved & Unlocked" if appr_sub[idx] else "🔒 Gate Locked"
            md.append(f"- **Approach Gate Status**: {sub_status}")
            
            app_val = appr_texts[idx] if idx < len(appr_texts) else ""
            if app_val:
                md.append(f"- **Candidate Strategy / Verbal Approach**:")
                md.append(f"  > {app_val}")
            else:
                md.append(f"- **Candidate Strategy / Verbal Approach**: *None submitted*")
                
            fb_val = ai_feedback_list[idx] if idx < len(ai_feedback_list) else ""
            if fb_val:
                md.append(f"- **AI Interviewer Feedback**:")
                md.append(f"  > 🤖 {fb_val}")

            # Submission & Attempt Details - FILTERED BY SESSION START TIME
            attempts = db.query(Attempt).filter(
                Attempt.problem_id == pid,
                Attempt.timestamp >= session_start
            ).order_by(Attempt.timestamp.asc()).all()
            total_attempts = len(attempts)
            
            md.append(f"- **Coding Submission Attempts (in Session)**: `{total_attempts} attempt(s)`")
            
            if attempts:
                accepted_attempts = [a for a in attempts if a.verdict == "Accepted"]
                is_solved = len(accepted_attempts) > 0
                latest_verdict = attempts[-1].verdict
                
                if is_solved:
                    md.append(f"- **Test Cases Status**: ✅ `Passed 100% Test Cases` (Verdict: `{latest_verdict}`)")
                else:
                    md.append(f"- **Test Cases Status**: ❌ `Failed Test Cases` (Latest Verdict: `{latest_verdict}`)")

                md.append("  - **Session Attempt Log & Diagnostics**:")
                for att_idx, att in enumerate(attempts):
                    verdict_icon = "✅" if att.verdict == "Accepted" else "❌"
                    time_str = f" in {att.time_taken_seconds}s" if att.time_taken_seconds else ""
                    cat_str = f" | Root Cause: `{att.root_cause_category}`" if att.root_cause_category and att.root_cause_category != "none" else ""
                    md.append(f"    - **Attempt #{att_idx + 1}** {verdict_icon} `{att.verdict}`{time_str}{cat_str}")
                    if att.explanation_text and att.root_cause_category != "none":
                        md.append(f"      *Diagnosis*: {att.explanation_text}")
            else:
                md.append("- **Test Cases Status**: ⚠️ `No Code Submissions Recorded`")

            md.append("")
        
        md.append("---")
        md.append("")

    return "\n".join(md)


@app.get("/journal/weekly", response_model=WeeklyJournalResponse)
def get_weekly_journal(db: Session = Depends(get_db)):
    """Generates past 7 days mistake journal and aggregated stats (Tier 5.1)."""
    seven_days_ago = get_utc_now() - timedelta(days=7)
    attempts = db.query(Attempt).filter(Attempt.timestamp >= seven_days_ago).all()

    by_category = Counter()
    example_problems = set()
    total_solved = 0

    for a in attempts:
        if a.verdict == "Accepted":
            total_solved += 1
        elif a.root_cause_category:
            by_category[a.root_cause_category] += 1
            if a.problem:
                example_problems.add(a.problem.title)

    start_str = seven_days_ago.strftime("%Y-%m-%d")
    end_str = get_utc_now().strftime("%Y-%m-%d")

    # Generate a detailed list of mistakes grouped by problem
    failed_attempts = db.query(Attempt).filter(
        Attempt.timestamp >= seven_days_ago,
        Attempt.verdict != "Accepted"
    ).order_by(Attempt.timestamp.desc()).all()

    problem_mistakes = {}
    for a in failed_attempts:
        if not a.problem:
            continue
        pid = a.problem.id
        if pid not in problem_mistakes:
            problem_mistakes[pid] = {
                "problem": a.problem,
                "mistakes": []
            }
        problem_mistakes[pid]["mistakes"].append(a)

    key_learnings = {
        "wrong_approach": "Ensure you verify time/space complexities and write pseudo-code for alternative approaches (like hash maps, two pointers, or sliding window) before writing code.",
        "implementation_bug": "Carefully dry-run code with small/empty inputs and check boundary conditions (such as off-by-one errors or null pointer checks).",
        "time_limit_exceeded": "When dealing with large inputs, look for opportunities to reduce complexity from O(N^2) to O(N log N) or O(N) using sorting, hashing, or binary search.",
        "edge_case_missed": "Before submitting, explicitly trace code execution with edge cases like empty inputs, single element arrays, or negative numbers.",
        "conceptual_gap": "Spend time understanding the fundamental theory of the algorithm or data structure before jumping to the implementation.",
        "none": "Ensure code correctness and review details before submitting."
    }

    md_lines = [
        f"# Weekly DSA Practice Digest ({start_str} to {end_str})",
        "",
        f"- **Total Attempts**: {len(attempts)}",
        f"- **Problems Solved**: {total_solved}",
        "",
        "## Mistakes by Category:",
    ]
    for cat, cnt in by_category.items():
        md_lines.append(f"- **{cat.replace('_', ' ').title()}**: {cnt}")

    if problem_mistakes:
        md_lines.append("")
        md_lines.append("## Detailed Journal of Mistakes & Key Learnings")
        md_lines.append("")
        for pid, data in problem_mistakes.items():
            prob = data["problem"]
            md_lines.append(f"### ❌ [{prob.title}]({prob.url})")
            md_lines.append(f"- **Difficulty**: {prob.difficulty} | **Topic**: {prob.topics}")
            md_lines.append("- **Mistakes**:")
            
            latest_category = "none"
            for m in data["mistakes"]:
                date_str = m.timestamp.strftime("%Y-%m-%d %H:%M")
                cat_display = m.root_cause_category.replace('_', ' ').title() if m.root_cause_category else "Unknown"
                explanation = m.explanation_text if m.explanation_text else "No explanation provided."
                md_lines.append(f"  - *{date_str}* ({cat_display}): {explanation}")
                if m.root_cause_category and latest_category == "none":
                    latest_category = m.root_cause_category
                    
            learning = key_learnings.get(latest_category, "Thoroughly analyze failures and write down the root cause to avoid repeating the mistake.")
            md_lines.append(f"- **💡 Key Learning**: {learning}")
            md_lines.append("")

    if example_problems:
        md_lines.extend(["", "## Review Suggested For Problems:", *[f"- {p}" for p in list(example_problems)[:10]]])

    return WeeklyJournalResponse(
        period_start=start_str,
        period_end=end_str,
        total_attempts=len(attempts),
        total_solved=total_solved,
        by_category=dict(by_category),
        example_problems=list(example_problems)[:10],
        markdown_text="\n".join(md_lines)
    )


@app.get("/problems/{problem_id}")
def get_problem_details(problem_id: str, db: Session = Depends(get_db)):
    """Fetches metadata, user notes, and personal difficulty rating for a problem."""
    problem = db.query(Problem).filter(Problem.id == problem_id).first()
    if not problem:
        return {"problem_id": problem_id, "user_notes": "", "personal_difficulty": ""}
    return {
        "problem_id": problem.id,
        "title": problem.title,
        "difficulty": problem.difficulty,
        "topics": problem.topics,
        "companies": problem.companies,
        "user_notes": problem.user_notes or "",
        "personal_difficulty": problem.personal_difficulty or ""
    }


@app.post("/problems/{problem_id}/notes")
def save_problem_notes(problem_id: str, req: dict, db: Session = Depends(get_db)):
    """Saves custom user notes and personal difficulty rating for a problem."""
    problem = db.query(Problem).filter(Problem.id == problem_id).first()
    if not problem:
        problem = Problem(
            id=problem_id,
            title=req.get("problem_title", problem_id),
            url=f"https://leetcode.com/problems/{problem_id}/",
            difficulty="Medium",
            topics="Arrays & Hashing"
        )
        db.add(problem)
        db.commit()
        db.refresh(problem)

    if "user_notes" in req:
        problem.user_notes = req["user_notes"]
    if "personal_difficulty" in req:
        problem.personal_difficulty = req["personal_difficulty"]

    db.commit()
    return {
        "status": "success",
        "problem_id": problem.id,
        "user_notes": problem.user_notes,
        "personal_difficulty": problem.personal_difficulty
    }


@app.get("/export/solved-csv")
def export_solved_csv(timeframe: str = "current_week", db: Session = Depends(get_db)):
    """
    Exports solved DSA problems to an expanded CSV spreadsheet with review dates,
    user comments/notes, personal difficulty ratings, attempt counts, mistake categories, and hints used.
    """
    import csv
    import io
    from fastapi import Response

    now = get_utc_now()
    
    if timeframe in ["current_week", "past_7_days"]:
        cutoff = now - timedelta(days=7)
    elif timeframe == "past_30_days":
        cutoff = now - timedelta(days=30)
    else:
        cutoff = None  # all_time

    # Query all solved problems
    solved_problems = db.query(Problem).filter(Problem.is_solved == True).all()

    # Pre-query SpacedRepetition reviews map
    sr_records = {sr.problem_id: sr for sr in db.query(SpacedRepetition).all()}

    # Pre-query attempts grouped by problem_id
    attempts_all = db.query(Attempt).all()
    attempts_by_problem = {}
    for a in attempts_all:
        attempts_by_problem.setdefault(a.problem_id, []).append(a)

    rows = []
    for p in solved_problems:
        p_attempts = attempts_by_problem.get(p.id, [])
        accepted_attempts = [a for a in p_attempts if a.verdict == "Accepted"]

        # Date solved determination
        latest_acc = max(accepted_attempts, key=lambda a: a.timestamp) if accepted_attempts else None
        if latest_acc:
            date_solved_ts = latest_acc.timestamp
        elif p_attempts:
            date_solved_ts = max(p_attempts, key=lambda a: a.timestamp).timestamp
        else:
            date_solved_ts = now

        # Timeframe filter check
        if cutoff and date_solved_ts < cutoff:
            continue

        date_solved_str = date_solved_ts.strftime("%Y-%m-%d %H:%M")

        # Spaced Repetition Review Schedule
        sr = sr_records.get(p.id)
        if sr:
            next_due_str = sr.next_due.strftime("%Y-%m-%d")
            stage_map = {
                1: "Stage 1 (3 days)",
                2: "Stage 2 (7 days)",
                3: "Stage 3 (14 days)",
                4: "Stage 4 (30 days / Monthly Review)",
                5: "Mastered / Complete"
            }
            schedule_str = stage_map.get(sr.stage, f"Stage {sr.stage}")
            if sr.stage >= 5:
                status_str = "Mastered"
            elif sr.next_due <= now:
                status_str = "DUE TODAY / OVERDUE"
            else:
                days_left = (sr.next_due.date() - now.date()).days
                status_str = f"Due in {days_left} day(s)"
        else:
            next_due_str = "Not Scheduled"
            schedule_str = "None"
            status_str = "N/A"

        # Diagnostic mistake notes & max hints used across attempts
        failed_attempts = [a for a in p_attempts if a.verdict != "Accepted"]
        if failed_attempts:
            categories = list(set(a.root_cause_category for a in failed_attempts if a.root_cause_category))
            mistake_note = ", ".join(categories) if categories else "Failed attempts logged"
        else:
            mistake_note = "None (Passed cleanly)"

        max_hints_used = max([a.hints_used for a in p_attempts], default=0)

        rows.append({
            "Problem Title": p.title,
            "Problem ID": p.id,
            "LeetCode Difficulty": p.difficulty or "Medium",
            "Personal Difficulty / Flag": p.personal_difficulty or "Not Rated",
            "Topics": p.topics or "",
            "Companies": p.companies or "",
            "Date Solved": date_solved_str,
            "Next Review Due Date": next_due_str,
            "Review Schedule": schedule_str,
            "Review Status": status_str,
            "Total Attempts Count": len(p_attempts),
            "Mistake Category / Note": mistake_note,
            "User Notes & Comments": p.user_notes or "",
            "Hints Used": max_hints_used,
            "LeetCode URL": p.url
        })

    output = io.StringIO()
    fieldnames = [
        "Problem Title",
        "Problem ID",
        "LeetCode Difficulty",
        "Personal Difficulty / Flag",
        "Topics",
        "Companies",
        "Date Solved",
        "Next Review Due Date",
        "Review Schedule",
        "Review Status",
        "Total Attempts Count",
        "Mistake Category / Note",
        "User Notes & Comments",
        "Hints Used",
        "LeetCode URL"
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

    csv_data = output.getvalue()
    filename = f"solved_problems_detailed_{timeframe}_{now.strftime('%Y%m%d')}.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )



