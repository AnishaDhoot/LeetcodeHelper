from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import math
from collections import Counter

from backend.database import get_db, engine, Base
from backend.models import (
    Problem, Attempt, TopicMastery, UserConfig, SpacedRepetition, DailyActivity, MockInterviewSession,
    SubmissionAnalyzeRequest, SubmissionAnalyzeResponse,
    ProblemRecommendResponse, TopicMasterySchema,
    CheckApproachRequest, CheckApproachResponse,
    GetHintRequest, GetHintResponse,
    HintRevealRequest, HintRevealResponse,
    GetEdgeCasesRequest, GetEdgeCasesResponse,
    AskHelpRequest, AskHelpResponse,
    SyncSolvedRequest, SolvedProblemSyncSchema,
    TopicAnalysisResponse, TopicStatItem, FocusResponse,
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
    get_topic_time_trend
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

    # -- attempts columns --
    if "attempts" in table_names:
        att_cols = [c["name"] for c in insp.get_columns("attempts")]
        if "time_spent_seconds" not in att_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE attempts ADD COLUMN time_spent_seconds INTEGER"))

    # -- topic_mastery Elo migration --
    if "topic_mastery" in table_names:
        tm_cols = {c["name"] for c in insp.get_columns("topic_mastery")}

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
                        last_updated     DATETIME,
                        next_review_date DATETIME
                    )
                """))
                conn.execute(text("""
                    INSERT INTO topic_mastery
                        (topic, rating, attempts_count, success_count,
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
                ("last_updated",     "ALTER TABLE topic_mastery ADD COLUMN last_updated DATETIME"),
                ("next_review_date", "ALTER TABLE topic_mastery ADD COLUMN next_review_date DATETIME"),
            ]
            for col_name, ddl in elo_additions:
                if col_name not in tm_cols:
                    with engine.begin() as conn:
                        conn.execute(text(ddl))

    # Auto-seed standard problem set and company tags if missing
    try:
        seed_db()
    except Exception as e:
        print(f"Auto-seeding warning: {e}")


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

# Enable CORS for the Chrome Extension and LeetCode page requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In development, we can allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _record_daily_activity(db: Session, is_success: bool):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    act = db.query(DailyActivity).filter(DailyActivity.date == today).first()
    if not act:
        act = DailyActivity(date=today, problems_attempted=1, problems_solved=1 if is_success else 0)
        db.add(act)
    else:
        act.problems_attempted += 1
        if is_success:
            act.problems_solved += 1


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
        # Default topic to Arrays & Hashing as a fallback
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

    # 2. Update topic mastery & daily streak activity
    update_mastery_on_submission(db, problem.topics, is_success=is_success, difficulty=problem.difficulty)
    _record_daily_activity(db, is_success=is_success)

    # 3. Handle success vs failure
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

    # For failures, run the LLM diagnosis
    diagnosis = generate_diagnosis(
        problem_title=problem.title,
        code=req.code,
        language=req.language,
        verdict=req.verdict,
        error_details=req.error_details,
        test_cases=req.test_cases
    )

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
        
    update_mastery_on_submission(db, problem.topics, is_success=True, difficulty=problem.difficulty)
    
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
    return masteries


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
def check_approach(req: CheckApproachRequest):
    """Critiques the user's approach and suggests optimizations."""
    result = generate_approach_critique(
        problem_title=req.problem_title,
        code=req.code,
        language=req.language,
        constraints=req.constraints
    )
    return CheckApproachResponse(
        is_optimal=bool(result.get("is_optimal", False)),
        current_complexity=result.get("current_complexity", "Unknown"),
        optimal_complexity=result.get("optimal_complexity", "Unknown"),
        feedback=result.get("feedback", ""),
        alternative_approach=result.get("alternative_approach", "")
    )


@app.post("/hints/get", response_model=GetHintResponse)
def get_hint(req: GetHintRequest):
    """Provides a progressive, conceptual hint without revealing the solution."""
    result = generate_hint(
        problem_title=req.problem_title,
        code=req.code,
        language=req.language,
        constraints=req.constraints
    )
    return GetHintResponse(hint=result.get("hint", ""))


@app.post("/hints/reveal", response_model=HintRevealResponse)
def reveal_hint(req: HintRevealRequest):
    """Provides a progressive, conceptual hint at the requested level (1, 2, or 3)."""
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
def get_edge_cases(req: GetEdgeCasesRequest):
    """Identifies potential edge cases and critiques the problem constraints."""
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
def ask_help(req: AskHelpRequest):
    """Answers a user's custom question about their code or the problem."""
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

    # 1. Upsert each problem (mark solved) and collect per-topic solved counts.
    solved_per_topic = Counter()
    for prob in req.problems:
        topics_csv = ", ".join(prob.topics) if prob.topics else "Arrays & Hashing"
        for t in [t.strip() for t in topics_csv.split(",") if t.strip()]:
            topics_seen.add(t)
            solved_per_topic[t] += 1

        url = f"https://leetcode.com/problems/{prob.problem_id}/"
        problem = db.query(Problem).filter(Problem.id == prob.problem_id).first()
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

    # 2. Seed per-topic mastery from solved counts (never clobber live data).
    new_topics = 0
    seeded_topics = 0
    for topic in topics_seen:
        solved_count = solved_per_topic[topic]
        mastery = db.query(TopicMastery).filter(TopicMastery.topic == topic).first()
        if not mastery:
            # Brand-new topic: seed from the sync using Elo rating.
            mastery = TopicMastery(
                topic=topic,
                rating=_seed_elo_rating(solved_count),
                attempts_count=solved_count,
                success_count=solved_count,  # treat all synced solves as successes
            )
            db.add(mastery)
            new_topics += 1
            seeded_topics += 1
        elif solved_count > mastery.attempts_count:
            # Existing topic whose live attempts are below the sync count: bring
            # the seed up, but never lower it (live progress wins on the way down).
            mastery.attempts_count = solved_count
            mastery.success_count = max(mastery.success_count, solved_count)
            seeded_rating = _seed_elo_rating(solved_count)
            mastery.rating = max(mastery.rating, seeded_rating)
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
        items.append(TopicStatItem(topic=topic, solved_count=count, mastery_score=score or 0.0))

    top_topics = sorted(items, key=lambda x: x.solved_count, reverse=True)

    # Weakest topics: lowest mastery among all known topics, capped at 5
    all_items = []
    for topic, m in mastery_rows.items():
        all_items.append(TopicStatItem(
            topic=topic,
            solved_count=topic_solved.get(topic, 0),
            mastery_score=m.mastery_score or 0.0
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
    """Returns the saved focus topic (or None)."""
    cfg = db.query(UserConfig).filter(UserConfig.key == FOCUS_KEY).first()
    return FocusResponse(focus_topic=cfg.value if cfg else None)


@app.post("/topics/focus", response_model=FocusResponse)
def set_focus(topic: Optional[str] = None, db: Session = Depends(get_db)):
    """Saves (or clears, when topic is empty/None) the focus topic."""
    value = topic.strip() if topic and topic.strip() else None
    cfg = db.query(UserConfig).filter(UserConfig.key == FOCUS_KEY).first()
    if value is None:
        # Clear focus
        if cfg:
            db.delete(cfg)
        result = None
    else:
        if cfg:
            cfg.value = value
        else:
            cfg = UserConfig(key=FOCUS_KEY, value=value)
            db.add(cfg)
        result = value
    db.commit()
    return FocusResponse(focus_topic=result)


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


@app.get("/reviews/count")
def get_reviews_count(db: Session = Depends(get_db)):
    """Returns count of active spaced repetition reviews due today (Tier 1.2)."""
    now = datetime.utcnow()
    due_count = db.query(SpacedRepetition).filter(
        SpacedRepetition.next_due <= now,
        SpacedRepetition.stage < 4
    ).count()
    return {"due_count": due_count}


@app.get("/activity/streak", response_model=StreakResponse)
def get_streak(db: Session = Depends(get_db)):
    """Returns current streak days and today's activity counts (Tier 1.4)."""
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    today_act = db.query(DailyActivity).filter(DailyActivity.date == today_str).first()
    problems_today = today_act.problems_attempted if today_act else 0
    solved_today = today_act.problems_solved if today_act else 0

    # Calculate streak walking backwards
    streak = 0
    curr_date = datetime.utcnow().date()
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
def explain_back(req: ExplainBackRequest):
    """Verifies user's self-explanation against their submitted code (Tier 3.2)."""
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


@app.post("/mock-interview/start", response_model=MockStartResponse)
def start_mock_interview(req: MockStartRequest, db: Session = Depends(get_db)):
    """Starts a timed mock interview session (Tier 4.1)."""
    rec_res = get_next_problem(db, company=req.company)
    recs = rec_res.get("recommendations", [])
    if not recs:
        # Fallback to any problem
        prob = db.query(Problem).first()
    else:
        prob_id = recs[0]["problem_id"]
        prob = db.query(Problem).filter(Problem.id == prob_id).first()

    if not prob:
        raise HTTPException(status_code=404, detail="No suitable problem found for mock interview.")

    session = MockInterviewSession(
        problem_id=prob.id,
        time_limit_seconds=req.time_limit_seconds,
        company=req.company
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return MockStartResponse(
        session_id=session.id,
        problem_id=prob.id,
        problem_title=prob.title,
        problem_url=prob.url,
        difficulty=prob.difficulty,
        topics=prob.topics,
        time_limit_seconds=session.time_limit_seconds
    )


@app.post("/mock-interview/approach")
def submit_mock_approach(req: MockApproachRequest, db: Session = Depends(get_db)):
    """Records the approach explanation before unlocking code editor (Tier 4.1)."""
    session = db.query(MockInterviewSession).filter(MockInterviewSession.id == req.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Mock session not found.")

    session.approach_submitted_at = datetime.utcnow()
    db.commit()
    return {"status": "approach_accepted", "session_id": session.id}


@app.post("/mock-interview/submit")
def submit_mock_solution(req: MockSubmitRequest, db: Session = Depends(get_db)):
    """Submits final code for a mock interview session (Tier 4.1)."""
    session = db.query(MockInterviewSession).filter(MockInterviewSession.id == req.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Mock session not found.")

    now = datetime.utcnow()
    session.submitted_at = now
    elapsed = int((now - session.start_time).total_seconds())
    session.time_taken_seconds = elapsed
    db.commit()

    # Perform analysis
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


@app.get("/journal/weekly", response_model=WeeklyJournalResponse)
def get_weekly_journal(db: Session = Depends(get_db)):
    """Generates past 7 days mistake journal and aggregated stats (Tier 5.1)."""
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
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
    end_str = datetime.utcnow().strftime("%Y-%m-%d")

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

    now = datetime.utcnow()
    
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
            stage_map = {1: "Stage 1 (3 days)", 2: "Stage 2 (7 days)", 3: "Stage 3 (14 days)", 4: "Mastered / Complete"}
            schedule_str = stage_map.get(sr.stage, f"Stage {sr.stage}")
            if sr.stage >= 4:
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



