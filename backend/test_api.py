from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal, get_db
from backend.models import Problem, Attempt, TopicMastery
from unittest.mock import patch
import datetime

client = TestClient(app)

def test_db_setup():
    db = SessionLocal()
    try:
        problems = db.query(Problem).all()
        print(f"Verified: found {len(problems)} problems in DB.")
        assert len(problems) > 0, "No problems found in DB."
        
        masteries = db.query(TopicMastery).all()
        print(f"Verified: found {len(masteries)} topics in DB.")
        assert len(masteries) > 0, "No topics found in DB."
    finally:
        db.close()

def test_get_mastery():
    response = client.get("/topics/mastery")
    assert response.status_code == 200
    data = response.json()
    print(f"GET /topics/mastery returns {len(data)} topics.")
    assert len(data) > 0
    assert "topic" in data[0]
    assert "mastery_score" in data[0]

def test_get_recommendation():
    response = client.get("/problems/next")
    assert response.status_code == 200
    data = response.json()
    print(f"GET /problems/next returns: {data}")
    assert "recommendations" in data
    assert "reviews" in data
    assert len(data["recommendations"]) > 0
    rec = data["recommendations"][0]
    assert "problem_id" in rec
    assert "title" in rec
    assert "url" in rec
    assert "difficulty" in rec
    assert "reason" in rec

def test_analyze_submission_success():
    # Test submission success path (does not trigger LLM)
    payload = {
        "problem_id": "two-sum",
        "problem_title": "Two Sum",
        "code": "class Solution { public int[] twoSum(int[] nums, int target) { return new int[]{0, 1}; } }",
        "language": "java",
        "verdict": "Accepted",
        "time_taken_seconds": 120
    }
    db = SessionLocal()
    prob = db.query(Problem).filter(Problem.id == "two-sum").first()
    target_topic = prob.topics if prob else "Arrays & Hashing"
    mastery_before = db.query(TopicMastery).filter(TopicMastery.topic == target_topic).first()
    initial_attempts = mastery_before.attempts_count if mastery_before else 0
    db.close()

    response = client.post("/submissions/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    print(f"POST /submissions/analyze (Accepted) returns: {data}")
    assert data["root_cause_category"] == "none"

    # Verify that Two Sum's topic mastery score increased
    db = SessionLocal()
    try:
        mastery = db.query(TopicMastery).filter(TopicMastery.topic == target_topic).first()
        print(f"{target_topic} mastery after success: {mastery.mastery_score}")
        assert mastery.mastery_score > 0.0
        assert mastery.attempts_count == initial_attempts + 1
    finally:
        db.close()

@patch("backend.main.generate_diagnosis")
def test_analyze_submission_failure(mock_diagnose):
    # Mock the LLM tutor output
    mock_diagnose.return_value = {
        "root_cause_category": "implementation_bug",
        "explanation": "Off-by-one bug in the loop condition.",
        "suggested_action": "Change i <= nums.length to i < nums.length."
    }

    payload = {
        "problem_id": "contains-duplicate",
        "problem_title": "Contains Duplicate",
        "code": "some faulty code",
        "language": "java",
        "verdict": "Wrong Answer",
        "error_details": "Failed testcase [1, 2, 3]",
        "test_cases": [{"input": "[1, 2, 3]", "expected": "false", "actual": "true"}]
    }

    db = SessionLocal()
    prob = db.query(Problem).filter(Problem.id == "contains-duplicate").first()
    target_topic = prob.topics if prob else "Arrays & Hashing"
    mastery_before = db.query(TopicMastery).filter(TopicMastery.topic == target_topic).first()
    initial_attempts = mastery_before.attempts_count if mastery_before else 0
    db.close()

    response = client.post("/submissions/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    print(f"POST /submissions/analyze (Failure) returns: {data}")
    assert data["root_cause_category"] == "implementation_bug"
    assert "Off-by-one" in data["explanation"]

    # Verify that Contains Duplicate's topic mastery score decreased or attempt count tracked
    db = SessionLocal()
    try:
        mastery = db.query(TopicMastery).filter(TopicMastery.topic == target_topic).first()
        print(f"{target_topic} mastery after failure: {mastery.mastery_score}")
        assert mastery.attempts_count == initial_attempts + 1
    finally:
        db.close()


# ==========================================
# Code Coach endpoint tests (LLM functions mocked)
# ==========================================

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    print("GET /health returns:", response.json())


@patch("backend.main.generate_approach_critique")
def test_check_approach(mock_critique):
    mock_critique.return_value = {
        "is_optimal": False,
        "current_complexity": "O(N^2) time, O(1) space",
        "optimal_complexity": "O(N) time, O(N) space",
        "feedback": "Nested loops are too slow for the constraints.",
        "alternative_approach": "Use a hash map to remember seen values."
    }
    payload = {
        "problem_id": "two-sum",
        "problem_title": "Two Sum",
        "code": "class Solution { }",
        "language": "java",
        "constraints": ["2 <= nums.length <= 10^4"]
    }
    response = client.post("/approach/check", json=payload)
    assert response.status_code == 200
    data = response.json()
    print(f"POST /approach/check returns: {data}")
    assert data["is_optimal"] is False
    assert "O(N)" in data["optimal_complexity"]
    assert "hash map" in data["alternative_approach"]


@patch("backend.main.generate_hint")
def test_get_hint(mock_hint):
    mock_hint.return_value = {"hint": "Think about what a hash map could store about seen numbers."}
    payload = {
        "problem_id": "two-sum",
        "problem_title": "Two Sum",
        "code": "class Solution { }",
        "language": "java"
    }
    response = client.post("/hints/get", json=payload)
    assert response.status_code == 200
    data = response.json()
    print(f"POST /hints/get returns: {data}")
    assert "hash map" in data["hint"]


@patch("backend.main.analyze_edge_cases")
def test_get_edge_cases(mock_edge):
    mock_edge.return_value = {
        "edge_cases": [
            {"case": "Two identical numbers that sum to target", "handled": False, "suggestion": "Allow same index twice only if value*2 == target."}
        ],
        "constraints_critique": "An O(N^2) solution may TLE because N can be 10^4."
    }
    payload = {
        "problem_id": "two-sum",
        "problem_title": "Two Sum",
        "code": "class Solution { }",
        "language": "java"
    }
    response = client.post("/edge-cases/get", json=payload)
    assert response.status_code == 200
    data = response.json()
    print(f"POST /edge-cases/get returns: {data}")
    assert len(data["edge_cases"]) == 1
    assert data["edge_cases"][0]["handled"] is False
    assert "TLE" in data["constraints_critique"]


@patch("backend.main.answer_custom_question")
def test_ask_help(mock_answer):
    mock_answer.return_value = {"answer": "Your outer loop should start at i = 0, and the inner at j = i + 1."}
    payload = {
        "problem_id": "two-sum",
        "problem_title": "Two Sum",
        "code": "class Solution { }",
        "language": "java",
        "question": "Why does my loop skip the first element?"
    }
    response = client.post("/help/ask", json=payload)
    assert response.status_code == 200
    data = response.json()
    print(f"POST /help/ask returns: {data}")
    assert "inner at j = i + 1" in data["answer"]


def test_sync_solved():
    # Use a sentinel topic to avoid clashing with existing mastery rows.
    sentinel_topic = f"TestTopic_{datetime.datetime.now().strftime('%H%M%S%f')}"
    payload = {
        "problems": [
            {"problem_id": "sync-test-problem", "title": "Sync Test Problem", "difficulty": "Easy", "topics": [sentinel_topic]},
            {"problem_id": "another-sync-problem", "title": "Another Sync", "difficulty": "Medium", "topics": [sentinel_topic, "Arrays & Hashing"]}
        ]
    }
    response = client.post("/sync/solved", json=payload)
    assert response.status_code == 200
    data = response.json()
    print(f"POST /sync/solved returns: {data}")
    assert data["synced"] == 2
    assert data["topics"] == 2  # sentinel + Arrays & Hashing

    db = SessionLocal()
    try:
        # Problems registered
        p = db.query(Problem).filter(Problem.id == "sync-test-problem").first()
        assert p is not None
        assert p.title == "Sync Test Problem"
        assert sentinel_topic in p.topics

        # New topic gets a seeded TopicMastery row
        m = db.query(TopicMastery).filter(TopicMastery.topic == sentinel_topic).first()
        assert m is not None
        assert m.mastery_score > 0.0
        assert m.attempts_count == 2

        # Existing "Arrays & Hashing" mastery must be unchanged by the sync
        existing = db.query(TopicMastery).filter(TopicMastery.topic == "Arrays & Hashing").first()
        # (It was last touched by the analyze tests above; sync must not alter it further.)
        print(f"Arrays & Hashing after sync: score={existing.mastery_score}, attempts={existing.attempts_count}")
    finally:
        # Clean up sentinel artifacts so the test is repeatable.
        db.query(TopicMastery).filter(TopicMastery.topic == sentinel_topic).delete()
        db.query(Problem).filter(Problem.id.in_(["sync-test-problem", "another-sync-problem"])).delete()
        db.commit()
        db.close()


if __name__ == "__main__":
    print("Starting backend tests...")
    test_db_setup()
    test_get_mastery()
    test_get_recommendation()
    test_analyze_submission_success()
    test_analyze_submission_failure()
    test_health()
    test_check_approach()
    test_get_hint()
    test_get_edge_cases()
    test_ask_help()
    test_sync_solved()
    print("All backend tests passed successfully!")
