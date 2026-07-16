from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from backend.database import get_db, engine, Base
from backend.models import (
    Problem, Attempt, TopicMastery,
    SubmissionAnalyzeRequest, SubmissionAnalyzeResponse,
    ProblemRecommendResponse, TopicMasterySchema,
    CheckApproachRequest, CheckApproachResponse,
    GetHintRequest, GetHintResponse,
    GetEdgeCasesRequest, GetEdgeCasesResponse,
    AskHelpRequest, AskHelpResponse,
    SyncSolvedRequest, SolvedProblemSyncSchema
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
    Returns the next recommended problem.
    """
    rec = get_next_problem(db)
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

    Registers each problem (upsert) and ensures a baseline TopicMastery row
    exists per topic without inflating scores or logging synthetic attempts.
    """
    synced = 0
    topics_seen = set()

    for prob in req.problems:
        topics_csv = ", ".join(prob.topics) if prob.topics else "Arrays & Hashing"
        for t in [t.strip() for t in topics_csv.split(",") if t.strip()]:
            topics_seen.add(t)

        url = f"https://leetcode.com/problems/{prob.problem_id}/"
        problem = db.query(Problem).filter(Problem.id == prob.problem_id).first()
        if problem:
            # Refresh metadata for a previously seen problem
            problem.title = prob.title or problem.title
            problem.url = url
            problem.difficulty = prob.difficulty or problem.difficulty
            problem.topics = topics_csv
        else:
            problem = Problem(
                id=prob.problem_id,
                title=prob.title or prob.problem_id,
                url=url,
                difficulty=prob.difficulty or "Medium",
                topics=topics_csv
            )
            db.add(problem)
        synced += 1

    # Ensure a baseline TopicMastery row exists (score 0, no attempts) for each topic
    new_topics = 0
    for topic in topics_seen:
        if not db.query(TopicMastery).filter(TopicMastery.topic == topic).first():
            db.add(TopicMastery(
                topic=topic,
                mastery_score=0.0,
                attempts_count=0,
                success_rate=0.0
            ))
            new_topics += 1

    db.commit()
    return {
        "synced": synced,
        "topics": len(topics_seen),
        "new_topics": new_topics,
        "message": f"Synced {synced} problem(s) across {len(topics_seen)} topic(s)."
    }
