from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import math
from collections import Counter

from backend.database import get_db, engine, Base
from backend.models import (
    Problem, Attempt, TopicMastery, UserConfig,
    SubmissionAnalyzeRequest, SubmissionAnalyzeResponse,
    ProblemRecommendResponse, TopicMasterySchema,
    CheckApproachRequest, CheckApproachResponse,
    GetHintRequest, GetHintResponse,
    GetEdgeCasesRequest, GetEdgeCasesResponse,
    AskHelpRequest, AskHelpResponse,
    SyncSolvedRequest, SolvedProblemSyncSchema,
    TopicAnalysisResponse, TopicStatItem, FocusResponse
)
from backend.agent import (
    generate_diagnosis,
    generate_approach_critique,
    generate_hint,
    analyze_edge_cases,
    answer_custom_question
)
from backend.recommender import update_mastery_on_submission, get_next_problem

# Ensure tables are created (just in case)
Base.metadata.create_all(bind=engine)


# --- Lightweight in-place schema migration ---------------------------------
# Older databases won't have the `is_solved` column on `problems`. Add it if
# missing so existing installs keep working without a full re-seed.
def _ensure_is_solved_column():
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    cols = [c["name"] for c in insp.get_columns("problems")] if "problems" in insp.get_table_names() else []
    if "is_solved" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE problems ADD COLUMN is_solved BOOLEAN DEFAULT 0 NOT NULL"))


_ensure_is_solved_column()


# Focus-topic key used inside the UserConfig key/value store.
FOCUS_KEY = "focus_topic"


def _seed_mastery_score(solved_count: int) -> float:
    """Log-scaled mastery seed so synced history yields meaningful scores.

    mastery_score = min(1.0, log(solved + 1) / log(51))
      1  -> ~0%, 5 -> ~28%, 10 -> ~43%, 25 -> ~63%, 50 -> ~100%
    """
    if solved_count <= 0:
        return 0.0
    return min(1.0, math.log(solved_count + 1) / math.log(51))

app = FastAPI(title="Autonomous DSA Tutor Agent Backend")

# Enable CORS for the Chrome Extension and LeetCode page requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In development, we can allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

    # 2. Update topic mastery
    update_mastery_on_submission(db, problem.topics, is_success=is_success)

    # 3. Handle success vs failure
    if is_success:
        # Save success attempt
        attempt = Attempt(
            problem_id=problem.id,
            verdict=req.verdict,
            root_cause_category="none",
            explanation_text="Submission succeeded! No diagnosis required.",
            time_taken_seconds=req.time_taken_seconds
        )
        db.add(attempt)
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
        time_taken_seconds=req.time_taken_seconds
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
        
    update_mastery_on_submission(db, problem.topics, is_success=True)
    
    attempt = Attempt(
        problem_id=problem.id,
        verdict="Accepted",
        root_cause_category="none",
        explanation_text="Submission succeeded!",
        time_taken_seconds=time_taken_seconds
    )
    db.add(attempt)
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
    Returns the next recommended problem. If a focus topic is saved in
    UserConfig, recommendations prioritize that topic.
    """
    cfg = db.query(UserConfig).filter(UserConfig.key == FOCUS_KEY).first()
    focus_topic = cfg.value if cfg else None
    rec = get_next_problem(db, focus_topic=focus_topic)
    return ProblemRecommendResponse(
        problem_id=rec["problem_id"],
        title=rec["title"],
        url=rec["url"],
        difficulty=rec["difficulty"],
        reason=rec["reason"]
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
            # Brand-new topic: seed from the sync.
            mastery = TopicMastery(
                topic=topic,
                mastery_score=_seed_mastery_score(solved_count),
                attempts_count=solved_count,
                success_rate=0.0
            )
            db.add(mastery)
            new_topics += 1
            seeded_topics += 1
        elif solved_count > mastery.attempts_count:
            # Existing topic whose live attempts are below the sync count: bring
            # the seed up, but never lower it (live progress wins on the way down).
            mastery.attempts_count = solved_count
            seeded_score = _seed_mastery_score(solved_count)
            mastery.mastery_score = max(mastery.mastery_score, seeded_score)
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
