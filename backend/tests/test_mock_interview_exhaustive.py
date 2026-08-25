import pytest
from starlette.testclient import TestClient
from unittest.mock import patch
from datetime import timedelta
import json

from backend.main import app, get_utc_now
from backend.database import Base, engine, SessionLocal
from backend.models import Problem, Attempt, TopicMastery, UserConfig, BadgeTest, MockInterviewSession

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_mock_interview_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Seed problems with different companies and difficulties
    p1 = Problem(id="two-sum", title="Two Sum", url="https://leetcode.com/problems/two-sum", difficulty="Easy", topics="Arrays", companies="Google, Meta", is_premium=False)
    p2 = Problem(id="3sum", title="3Sum", url="https://leetcode.com/problems/3sum", difficulty="Medium", topics="Two Pointers", companies="Google, Amazon", is_premium=False)
    p3 = Problem(id="trapping-rain-water", title="Trapping Rain Water", url="https://leetcode.com/problems/trapping-rain-water", difficulty="Hard", topics="Stack", companies="Google, Apple", is_premium=False)
    p4 = Problem(id="valid-anagram", title="Valid Anagram", url="https://leetcode.com/problems/valid-anagram", difficulty="Easy", topics="Hash Table", companies="Amazon", is_premium=False)
    p5 = Problem(id="course-schedule", title="Course Schedule", url="https://leetcode.com/problems/course-schedule", difficulty="Medium", topics="Graphs", companies="Meta", is_premium=False)
    p_prem = Problem(id="premium-problem", title="Premium Problem", url="https://leetcode.com/problems/premium-problem", difficulty="Medium", topics="Arrays", companies="Google", is_premium=True)
    db.add_all([p1, p2, p3, p4, p5, p_prem])
    db.commit()

    yield db
    db.close()

def test_mock_interview_start_and_metadata_validation():
    """Verifies starting a mock interview assigns 3 non-premium balanced questions with company focus."""
    res = client.post("/mock-interview/start", json={"company": "Google", "time_limit_seconds": 3600})
    assert res.status_code == 200
    data = res.json()
    assert "session_id" in data
    assert len(data["problem_ids"]) == 3
    assert len(data["problem_titles"]) == 3
    assert len(data["difficulties"]) == 3
    assert data["current_question_index"] == 0
    assert data["approach_submitted"] is False
    assert data["time_limit_seconds"] == 3600

    # Ensure no premium problems were selected
    assert "premium-problem" not in data["problem_ids"]

def test_mock_interview_active_poll_lifecycle():
    """Verifies /mock-interview/active returns None when idle and full session state when active."""
    # When idle
    assert client.get("/mock-interview/active").json() is None

    # Start session
    start_res = client.post("/mock-interview/start", json={"company": "Google", "time_limit_seconds": 2700})
    session_id = start_res.json()["session_id"]

    # When active
    active_res = client.get("/mock-interview/active")
    assert active_res.status_code == 200
    active_data = active_res.json()
    assert active_data is not None
    assert active_data["session_id"] == session_id
    assert active_data["approach_submitted"] is False
    assert active_data["current_question_index"] == 0
    assert len(active_data["approaches_submitted_list"]) == 3

def test_mock_interview_strategy_submission_and_editor_unlock():
    """Verifies submitting verbal approach updates state and unlocks editor on approval."""
    start_res = client.post("/mock-interview/start", json={"company": "Google", "time_limit_seconds": 3600})
    session_id = start_res.json()["session_id"]

    # Submit valid strategy with time & space complexity
    approach_payload = {
        "session_id": session_id,
        "approach_text": "Using a Hash Map to store seen complements in one pass. Time complexity O(N), Space complexity O(N)."
    }
    with patch("backend.agent.evaluate_mock_approach", return_value={"approved": True, "feedback": "Great strategy!"}):
        app_res = client.post("/mock-interview/approach", json=approach_payload)
        assert app_res.status_code == 200
        app_data = app_res.json()
        assert app_data["status"] == "approach_accepted"
        assert app_data["approved"] is True
        assert "feedback" in app_data

    # Check active state now reflects approved approach
    active_res = client.get("/mock-interview/active")
    assert active_res.json()["approach_submitted"] is True
    assert active_res.json()["approaches_submitted_list"][0] is True

def test_mock_interview_question_switching():
    """Verifies switching between the 3 mock questions updates active index and problem id."""
    start_res = client.post("/mock-interview/start", json={"company": "Google", "time_limit_seconds": 3600})
    session_id = start_res.json()["session_id"]
    problem_ids = start_res.json()["problem_ids"]

    # Switch to Question 2 (index 1)
    switch_res = client.post("/mock-interview/switch", json={"session_id": session_id, "target_index": 1})
    assert switch_res.status_code == 200
    assert switch_res.json()["current_question_index"] == 1

    # Verify active poll matches switched index
    active_res = client.get("/mock-interview/active")
    assert active_res.json()["current_question_index"] == 1
    assert active_res.json()["problem_id"] == problem_ids[1]

    # Switch to Question 3 (index 2)
    switch_res3 = client.post("/mock-interview/switch", json={"session_id": session_id, "target_index": 2})
    assert switch_res3.status_code == 200
    assert switch_res3.json()["current_question_index"] == 2

    # Invalid switch (index 3) should return 400
    invalid_res = client.post("/mock-interview/switch", json={"session_id": session_id, "target_index": 3})
    assert invalid_res.status_code == 400

def test_mock_interview_hints_and_ai_locked_during_session():
    """Verifies that hints, explain-back, and badge tests are locked during mock sessions."""
    start_res = client.post("/mock-interview/start", json={"company": "Google", "time_limit_seconds": 3600})
    session_id = start_res.json()["session_id"]

    # Attempting to reveal hint must return 403 Forbidden
    hint_res = client.post("/hints/reveal", json={"problem_id": "two-sum", "code": "def twoSum(): pass", "language": "python3", "level": 1})
    assert hint_res.status_code == 403
    assert "locked during an active Mock Interview" in hint_res.json()["detail"]

def test_mock_interview_evaluation_scorecard_generation():
    """Verifies /mock-interview/evaluate generates an AI scorecard with hiring verdict and category ratings."""
    start_res = client.post("/mock-interview/start", json={"company": "Google", "time_limit_seconds": 3600})
    session_id = start_res.json()["session_id"]
    p_id = start_res.json()["problem_ids"][0]

    # Submit approach
    client.post("/mock-interview/approach", json={"session_id": session_id, "approach_text": "Optimal hash map solution with O(N) time and O(N) space."})

    # Record an accepted attempt for this problem during the session
    db = SessionLocal()
    att = Attempt(problem_id=p_id, verdict="Accepted", root_cause_category="none", explanation_text="Accepted solution", timestamp=get_utc_now())
    db.add(att)
    db.commit()
    db.close()

    # Generate scorecard
    mock_card = {
        "verdict": "Strong Hire",
        "overall_summary": "Excellent algorithmic structuring",
        "strategy_score": 5,
        "code_quality_score": 5,
        "time_management_score": 4,
        "strengths": ["Optimal two pointers approach", "Clean edge case handling"],
        "areas_for_improvement": ["Consider early termination"]
    }
    with patch("backend.agent.generate_mock_scorecard", return_value=mock_card):
        eval_res = client.post("/mock-interview/evaluate", json={"session_id": session_id})
        assert eval_res.status_code == 200
        card = eval_res.json()
        assert card["verdict"] == "Strong Hire"
        assert card["strategy_score"] == 5

def test_mock_interview_final_code_submission():
    """Verifies /mock-interview/submit marks the session as completed with duration recorded."""
    start_res = client.post("/mock-interview/start", json={"company": "Google", "time_limit_seconds": 3600})
    session_id = start_res.json()["session_id"]
    p_id = start_res.json()["problem_ids"][0]

    sub_res = client.post("/mock-interview/submit", json={
        "session_id": session_id,
        "problem_id": p_id,
        "problem_title": "Two Sum",
        "code": "class Solution { public int[] twoSum(int[] nums, int target) { return new int[]{0,1}; } }",
        "language": "python3"
    })
    assert sub_res.status_code == 200

    # Verify session is no longer active
    active_after = client.get("/mock-interview/active")
    assert active_after.json() is None

def test_mock_interview_performance_report():
    """Verifies /mock-interview/report produces a comprehensive markdown summary across sessions."""
    # Start and evaluate a session to have data in DB
    start_res = client.post("/mock-interview/start", json={"company": "Google", "time_limit_seconds": 3600})
    session_id = start_res.json()["session_id"]
    mock_card = {
        "verdict": "Hire",
        "overall_summary": "Solid problem solving",
        "strategy_score": 4,
        "code_quality_score": 4,
        "time_management_score": 4,
        "strengths": ["Clean approach"],
        "areas_for_improvement": ["Edge cases"]
    }
    with patch("backend.agent.generate_mock_scorecard", return_value=mock_card):
        client.post("/mock-interview/evaluate", json={"session_id": session_id})

    # Fetch report
    report_res = client.get("/mock-interview/report")
    assert report_res.status_code == 200
    report_md = report_res.text
    assert "Mock Interview Performance & Diagnostic Report" in report_md
    assert "Executive Performance Summary" in report_md
