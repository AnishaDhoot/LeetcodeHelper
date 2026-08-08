from fastapi.testclient import TestClient
from backend.main import app, AI_DAILY_QUOTA_LIMIT, get_utc_now, check_and_increment_ai_quota
from backend.database import SessionLocal, get_db
from backend.models import Problem, Attempt, TopicMastery, BadgeTest, UserConfig, MockInterviewSession
from unittest.mock import patch
import datetime

client = TestClient(app)

def test_db_setup():
    db = SessionLocal()
    try:
        # Clean up any leftover badge tests from previous runs to prevent 403 locks
        db.query(BadgeTest).delete()
        # Clean up leftover mock sessions
        db.query(MockInterviewSession).delete()
        # Clean up any AI quota keys to prevent test quota failures
        db.query(UserConfig).filter(UserConfig.key.like("ai_limit_%")).delete()
        db.commit()

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
    assert "mastery_score" in data[0]  # derived property, always present
    assert "rating" in data[0]         # Elo rating column
    assert "level" in data[0]
    assert "badge" in data[0]
    assert "next_questions" in data[0]

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
        "time_taken_seconds": 120,
        "hints_used": 1
    }
    db = SessionLocal()
    prob = db.query(Problem).filter(Problem.id == "two-sum").first()
    target_topic = [t.strip() for t in prob.topics.split(",") if t.strip()][0] if prob and prob.topics else "Arrays & Hashing"
    mastery_before = db.query(TopicMastery).filter(TopicMastery.topic == target_topic).first()
    initial_attempts = mastery_before.attempts_count if mastery_before else 0
    initial_successes = mastery_before.success_count if mastery_before else 0
    initial_level = mastery_before.level if mastery_before else 0
    db.close()

    response = client.post("/submissions/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    print(f"POST /submissions/analyze (Accepted) returns: {data}")
    assert data["root_cause_category"] == "none"

    # Verify that the topic's attempt and success count increased
    db = SessionLocal()
    try:
        mastery = db.query(TopicMastery).filter(TopicMastery.topic == target_topic).first()
        print(f"{target_topic} level after success: {mastery.level} (was {initial_level})")
        assert mastery.attempts_count == initial_attempts + 1
        assert mastery.success_count == initial_successes + 1
        
        # Verify attempt was recorded with hints
        latest_attempt = db.query(Attempt).filter(Attempt.problem_id == "two-sum").order_by(Attempt.id.desc()).first()
        assert latest_attempt is not None
        assert latest_attempt.hints_used == 1
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
        "test_cases": [{"input": "[1, 2, 3]", "expected": "false", "actual": "true"}],
        "hints_used": 3
    }

    db = SessionLocal()
    prob = db.query(Problem).filter(Problem.id == "contains-duplicate").first()
    target_topic = [t.strip() for t in prob.topics.split(",") if t.strip()][0] if prob and prob.topics else "Arrays & Hashing"
    mastery_before = db.query(TopicMastery).filter(TopicMastery.topic == target_topic).first()
    initial_attempts = mastery_before.attempts_count if mastery_before else 0
    initial_rating = mastery_before.rating if mastery_before else 800.0
    db.close()

    response = client.post("/submissions/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    print(f"POST /submissions/analyze (Failure) returns: {data}")
    assert data["root_cause_category"] == "implementation_bug"
    assert "Off-by-one" in data["explanation"]

    # Verify attempt count tracked and rating unchanged
    db = SessionLocal()
    try:
        mastery = db.query(TopicMastery).filter(TopicMastery.topic == target_topic).first()
        print(f"{target_topic} rating after failure: {mastery.rating:.1f} (was {initial_rating:.1f})")
        assert mastery.attempts_count == initial_attempts + 1
        assert mastery.rating == initial_rating, "Rating must not change on a failed submission outside a test"

        latest_attempt = db.query(Attempt).filter(Attempt.problem_id == "contains-duplicate").order_by(Attempt.id.desc()).first()
        assert latest_attempt is not None
        assert latest_attempt.hints_used == 3
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

        # New topic gets a seeded TopicMastery row with Elo rating above 1200
        # (log-scaled: 2 solves => ~800 + 1200*log(3)/log(51) ≈ 1160 ... actually
        # for 2 problems across 2 probs the seed is for count=2)
        m = db.query(TopicMastery).filter(TopicMastery.topic == sentinel_topic).first()
        assert m is not None
        assert m.rating == 800.0
        assert m.attempts_count == 2
        assert m.success_count == 0  # synced solves do not count towards badges

        # Existing "Arrays & Hashing" mastery must be unchanged by the sync
        existing = db.query(TopicMastery).filter(TopicMastery.topic == "Arrays & Hashing").first()
        print(f"Arrays & Hashing after sync: rating={existing.rating:.1f}, attempts={existing.attempts_count}")
    finally:
        # Clean up sentinel artifacts so the test is repeatable.
        db.query(TopicMastery).filter(TopicMastery.topic == sentinel_topic).delete()
        db.query(Problem).filter(Problem.id.in_(["sync-test-problem", "another-sync-problem"])).delete()
        db.commit()
        db.close()


@patch("backend.main.generate_levelled_hint")
def test_reveal_hint(mock_levelled_hint):
    mock_levelled_hint.return_value = {
        "hint": "Think about storing index in a hash map.",
        "level": 2,
        "has_next": True
    }
    payload = {
        "problem_id": "two-sum",
        "problem_title": "Two Sum",
        "code": "class Solution { }",
        "language": "java",
        "level": 2
    }
    response = client.post("/hints/reveal", json=payload)
    assert response.status_code == 200
    data = response.json()
    print(f"POST /hints/reveal returns: {data}")
    assert data["level"] == 2
    assert "hash map" in data["hint"]
    assert data["has_next"] is True


def test_get_companies():
    response = client.get("/companies")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_reviews_count():
    response = client.get("/reviews/count")
    assert response.status_code == 200
    data = response.json()
    assert "due_count" in data


def test_streak():
    response = client.get("/activity/streak")
    assert response.status_code == 200
    data = response.json()
    assert "current_streak_days" in data
    assert "problems_today" in data


def test_weak_pairs():
    response = client.get("/topics/weak-pairs")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@patch("backend.main.generate_explain_back_check")
def test_explain_back(mock_check):
    mock_check.return_value = {"matches": True, "discrepancy_note": None}
    payload = {
        "problem_id": "two-sum",
        "code": "class Solution { }",
        "language": "java",
        "user_explanation": "I used a hash map to look up complements in O(N) time."
    }
    response = client.post("/submissions/explain-back", json=payload)
    assert response.status_code == 200
    assert response.json()["matches"] is True


def test_mock_interview():
    # Verify initially no active mock session
    active_before = client.get("/mock-interview/active")
    assert active_before.status_code == 200
    assert active_before.json() is None

    # Start mock interview
    start_res = client.post("/mock-interview/start", json={"time_limit_seconds": 2700})
    assert start_res.status_code == 200
    session = start_res.json()
    assert "session_id" in session

    # Verify active mock session returns details
    active_after = client.get("/mock-interview/active")
    assert active_after.status_code == 200
    active_data = active_after.json()
    assert active_data is not None
    assert active_data["session_id"] == session["session_id"]
    assert active_data["approach_submitted"] is False

    # Submit approach explanation
    app_res = client.post("/mock-interview/approach", json={"session_id": session["session_id"], "approach_text": "Use two pointers"})
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "approach_accepted"

    # Verify approach_submitted updates to True
    active_submitted = client.get("/mock-interview/active")
    assert active_submitted.status_code == 200
    assert active_submitted.json()["approach_submitted"] is True

    # Test AI quota endpoint
    quota_res = client.get("/ai/quota")
    assert quota_res.status_code == 200
    quota_data = quota_res.json()
    assert "used" in quota_data
    assert quota_data["limit"] == AI_DAILY_QUOTA_LIMIT


def test_weekly_journal():
    response = client.get("/journal/weekly")
    assert response.status_code == 200
    data = response.json()
    assert "markdown_text" in data
    assert "total_attempts" in data


def test_badge_test_flow():
    # Clean up Arrays & Hashing topic level and any active badge test
    db = SessionLocal()
    try:
        db.query(BadgeTest).filter(BadgeTest.topic == "Arrays & Hashing").delete()
        mastery = db.query(TopicMastery).filter(TopicMastery.topic == "Arrays & Hashing").first()
        if mastery:
            mastery.level = 0
            mastery.rating = 800.0
        db.commit()
    finally:
        db.close()

    # Start badge test
    start_res = client.post("/badge-test/start", json={"topic": "Arrays & Hashing"})
    assert start_res.status_code == 200
    test_data = start_res.json()
    assert test_data["status"] == "active"
    assert test_data["level"] == 1
    p1 = test_data["problem1"]["id"]
    p2 = test_data["problem2"]["id"]

    # Verify hints are blocked during test
    hint_payload = {
        "problem_id": p1,
        "problem_title": test_data["problem1"]["title"],
        "code": "class Solution { }",
        "language": "java"
    }
    hint_res = client.post("/hints/get", json=hint_payload)
    assert hint_res.status_code == 403
    assert "locked" in hint_res.json()["detail"].lower()

    # Solve first problem
    solve_payload1 = {
        "problem_id": p1,
        "problem_title": test_data["problem1"]["title"],
        "code": "class Solution { }",
        "language": "java",
        "verdict": "Accepted",
        "time_taken_seconds": 120,
        "hints_used": 0
    }
    sol1_res = client.post("/submissions/analyze", json=solve_payload1)
    assert sol1_res.status_code == 200

    # Solve second problem
    solve_payload2 = {
        "problem_id": p2,
        "problem_title": test_data["problem2"]["title"],
        "code": "class Solution { }",
        "language": "java",
        "verdict": "Accepted",
        "time_taken_seconds": 120,
        "hints_used": 0
    }
    sol2_res = client.post("/submissions/analyze", json=solve_payload2)
    assert sol2_res.status_code == 200

    # Verify badge level increased and rating is updated
    db = SessionLocal()
    try:
        mastery = db.query(TopicMastery).filter(TopicMastery.topic == "Arrays & Hashing").first()
        assert mastery.level == 1
        assert mastery.badge == "Bronze"
        assert mastery.rating == 1040.0
    finally:
        db.close()

    # Verify active test returns None (since it passed and is no longer active)
    active_res = client.get("/badge-test/active")
    assert active_res.status_code == 200
    assert active_res.json() is None


@patch("backend.main.check_and_increment_ai_quota")
def test_analyze_submission_quota_exceeded(mock_quota_check):
    from fastapi import HTTPException
    mock_quota_check.side_effect = HTTPException(status_code=429, detail="Daily AI request limit reached.")

    payload = {
        "problem_id": "contains-duplicate",
        "problem_title": "Contains Duplicate",
        "code": "some faulty code",
        "language": "java",
        "verdict": "Wrong Answer",
        "error_details": "Failed testcase [1, 2, 3]",
        "test_cases": [{"input": "[1, 2, 3]", "expected": "false", "actual": "true"}],
        "hints_used": 0
    }

    response = client.post("/submissions/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["root_cause_category"] == "quota_exceeded"
    assert "limit reached" in data["explanation"].lower()


def test_quota_concurrency_at_boundary():
    from concurrent.futures import ThreadPoolExecutor
    from fastapi import HTTPException
    
    db = SessionLocal()
    today_str = get_utc_now().strftime("%Y-%m-%d")
    key = f"ai_limit_{today_str}"
    db.query(UserConfig).filter(UserConfig.key == key).delete()
    
    starting_used = AI_DAILY_QUOTA_LIMIT - 1
    config_row = UserConfig(key=key, value=str(starting_used))
    db.add(config_row)
    db.commit()
    db.close()
    
    results = []
    
    def run_increment():
        thread_db = SessionLocal()
        try:
            check_and_increment_ai_quota(thread_db)
            results.append("success")
        except HTTPException as e:
            if e.status_code == 429:
                results.append("quota_exceeded")
            else:
                results.append(f"error_{e.status_code}")
        except Exception as e:
            results.append(f"exception_{str(e)}")
        finally:
            thread_db.close()
            
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(run_increment) for _ in range(10)]
        for f in futures:
            f.result()
            
    successes = [r for r in results if r == "success"]
    exceeded = [r for r in results if r == "quota_exceeded"]
    
    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}. Results: {results}"
    assert len(exceeded) == 9, f"Expected 9 quota exclusions, got {len(exceeded)}. Results: {results}"
    
    db = SessionLocal()
    final_row = db.query(UserConfig).filter(UserConfig.key == key).first()
    assert int(final_row.value) == AI_DAILY_QUOTA_LIMIT
    db.close()


if __name__ == "__main__":
    print("Starting backend tests...")
    test_db_setup()
    test_get_mastery()
    test_get_recommendation()
    test_analyze_submission_success()
    test_analyze_submission_failure()
    test_badge_test_flow()
    test_health()
    test_check_approach()
    test_get_hint()
    test_reveal_hint()
    test_get_edge_cases()
    test_ask_help()
    test_sync_solved()
    test_get_companies()
    test_reviews_count()
    test_streak()
    test_weak_pairs()
    test_explain_back()
    test_mock_interview()
    test_weekly_journal()
    test_analyze_submission_quota_exceeded()
    test_quota_concurrency_at_boundary()
    print("All backend tests passed successfully!")

