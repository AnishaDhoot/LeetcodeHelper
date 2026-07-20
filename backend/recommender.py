"""
recommender.py — Elo-based topic mastery scoring & next-problem selection.

Elo update rule
---------------
  expected  = 1 / (1 + 10 ** ((opponent_rating - player_rating) / 400))
  new_rating = player_rating + K * (actual - expected)

Where:
  • player_rating   = TopicMastery.rating  (starts at 1200)
  • opponent_rating = difficulty-based problem rating
      Easy   → 800
      Medium → 1200
      Hard   → 1600
  • actual  = 1.0 (Accepted) | 0.0 (failure)
  • K       = dynamic: 32 for first 10 attempts, 24 for 11-30, 16 thereafter

mastery_score (0-1) is derived from rating by the model property:
    max(0, min(1, (rating - 800) / 1200))
so rating 800 → 0.0, 1600 → ~0.67, 2000 → 1.0.
"""

import random
import time
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc
from backend.models import Problem, Attempt, TopicMastery, SpacedRepetition

# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------
_DIFFICULTY_RATING = {
    "Easy": 800,
    "Medium": 1200,
    "Hard": 1600,
}
_DEFAULT_PROBLEM_RATING = 1200  # fallback for unknown difficulties

# Tier 2.3 — force Easy problems until a topic has this many attempts
RAMP_THRESHOLD = 3

# Tier 2.2 — exploration probability (epsilon-greedy)
EPSILON = 0.15

# Tier 2.1 — weak-pair detection: min co-occurrence count and max rating for "weak"
WEAK_PAIR_MIN_COOCCUR = 2
WEAK_PAIR_MAX_RATING = 1100.0  # mastery_score ≈ 25%

# Module-level cache for weak pairs {result: list, computed_at: float}
_weak_pair_cache: dict = {"result": [], "computed_at": 0.0}
_WEAK_PAIR_TTL = 3600  # seconds


# ---------------------------------------------------------------------------
# Elo helpers
# ---------------------------------------------------------------------------

def _problem_rating(difficulty: str) -> int:
    """Return the implied Elo rating for a given problem difficulty."""
    return _DIFFICULTY_RATING.get(difficulty or "", _DEFAULT_PROBLEM_RATING)


def _k_factor(attempts: int) -> float:
    """Dynamic K-factor: large early on (fast learning), stable later."""
    if attempts <= 10:
        return 32.0
    elif attempts <= 30:
        return 24.0
    return 16.0


def _elo_update(player_rating: float, opponent_rating: int, actual: float, k: float) -> float:
    """Return the new Elo rating after one match."""
    expected = 1.0 / (1.0 + 10.0 ** ((opponent_rating - player_rating) / 400.0))
    return player_rating + k * (actual - expected)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def update_mastery_on_submission(
    db: Session,
    topic_name: str,
    is_success: bool,
    difficulty: str = "Medium",
) -> TopicMastery:
    """
    Updates TopicMastery via Elo rating math and reschedules spaced-repetition
    review date based on the resulting mastery_score.

    Parameters
    ----------
    db          : active SQLAlchemy session
    topic_name  : topic string (e.g. "Arrays & Hashing")
    is_success  : True → Accepted, False → any failure
    difficulty  : problem difficulty used to set the opponent Elo rating
    """
    mastery = db.query(TopicMastery).filter(TopicMastery.topic == topic_name).first()
    if not mastery:
        mastery = TopicMastery(
            topic=topic_name,
            rating=1200.0,
            attempts_count=0,
            success_count=0,
        )
        db.add(mastery)
        db.flush()  # assign PK before we modify it

    now = datetime.utcnow()

    # --- Elo calculation ---
    k = _k_factor(mastery.attempts_count)
    opponent = _problem_rating(difficulty)
    actual = 1.0 if is_success else 0.0

    new_rating = _elo_update(mastery.rating, opponent, actual, k)
    # Clamp to a sane range so ratings stay interpretable
    mastery.rating = max(400.0, min(3000.0, new_rating))

    # --- Bookkeeping ---
    mastery.attempts_count += 1
    if is_success:
        mastery.success_count += 1
    mastery.last_updated = now

    # --- Spaced-repetition scheduling ---
    score = mastery.mastery_score  # derived 0-1 from model property
    if is_success:
        if score < 0.3:
            interval_days = 1
        elif score < 0.5:
            interval_days = 3
        elif score < 0.7:
            interval_days = 7
        else:
            interval_days = 14
        mastery.next_review_date = now + timedelta(days=interval_days)
    else:
        # Failed: needs immediate review
        mastery.next_review_date = now

    db.commit()
    db.refresh(mastery)
    return mastery


def update_spaced_repetition(db: Session, problem_id: str) -> SpacedRepetition:
    """
    Saves or advances the spaced-repetition schedule for a solved problem.

    Stages
    ------
    1 → review in  3 days (Short term)
    2 → review in  7 days (1 week)
    3 → review in 14 days (2 weeks)
    4 → review in 30 days (1 month review)
    5 → completed / mastered, far-future date
    """
    now = datetime.utcnow()
    sr = db.query(SpacedRepetition).filter(SpacedRepetition.problem_id == problem_id).first()

    if not sr:
        sr = SpacedRepetition(
            problem_id=problem_id,
            stage=1,
            last_solved=now,
            next_due=now + timedelta(days=3),
        )
        db.add(sr)
    else:
        if sr.stage == 1:
            sr.stage = 2
            sr.next_due = now + timedelta(days=7)
        elif sr.stage == 2:
            sr.stage = 3
            sr.next_due = now + timedelta(days=14)
        elif sr.stage == 3:
            sr.stage = 4
            sr.next_due = now + timedelta(days=30)  # Monthly review!
        elif sr.stage >= 4:
            sr.stage = 5
            sr.next_due = now + timedelta(days=3650)  # effectively "done / mastered"
        sr.last_solved = now

    db.commit()
    db.refresh(sr)
    return sr


# ---------------------------------------------------------------------------
# Tier 2.1 — Weak-pair detection
# ---------------------------------------------------------------------------

def compute_weak_pairs(db: Session) -> list:
    """
    Finds pairs of topics that are both weak (rating < WEAK_PAIR_MAX_RATING)
    and frequently co-occur in the same problem.

    Returns a list of dicts: [{topic_a, topic_b, co_occurrence}]
    Sorted by co_occurrence descending.  Results are cached for TTL seconds.
    """
    global _weak_pair_cache
    now_ts = time.time()
    if now_ts - _weak_pair_cache["computed_at"] < _WEAK_PAIR_TTL:
        return _weak_pair_cache["result"]

    weak_masteries = (
        db.query(TopicMastery)
        .filter(TopicMastery.rating < WEAK_PAIR_MAX_RATING)
        .all()
    )
    weak_topics = [m.topic for m in weak_masteries]

    if len(weak_topics) < 2:
        _weak_pair_cache = {"result": [], "computed_at": now_ts}
        return []

    # Count co-occurrences in the Problem table
    all_problems = db.query(Problem).all()
    pair_counts: dict = {}

    for i in range(len(weak_topics)):
        for j in range(i + 1, len(weak_topics)):
            ta, tb = weak_topics[i], weak_topics[j]
            count = sum(
                1 for p in all_problems
                if ta in (p.topics or "") and tb in (p.topics or "")
            )
            if count >= WEAK_PAIR_MIN_COOCCUR:
                pair_counts[(ta, tb)] = count

    result = [
        {"topic_a": a, "topic_b": b, "co_occurrence": c}
        for (a, b), c in sorted(pair_counts.items(), key=lambda x: -x[1])
    ]

    _weak_pair_cache = {"result": result, "computed_at": now_ts}
    return result


def get_topic_time_trend(db: Session, topic_name: str) -> list:
    """
    Returns recent attempts for problems tagged with topic_name containing
    timestamp and time_spent_seconds (Tier 1.3).
    """
    problems = db.query(Problem).filter(Problem.topics.like(f"%{topic_name}%")).all()
    if not problems:
        return []
    prob_ids = [p.id for p in problems]
    attempts = (
        db.query(Attempt)
        .filter(Attempt.problem_id.in_(prob_ids), Attempt.time_spent_seconds.isnot(None))
        .order_by(desc(Attempt.timestamp))
        .limit(10)
        .all()
    )
    return [
        {
            "timestamp": a.timestamp.isoformat() if a.timestamp else None,
            "time_spent_seconds": a.time_spent_seconds,
            "verdict": a.verdict,
            "problem_id": a.problem_id
        }
        for a in reversed(attempts)
    ]


# ---------------------------------------------------------------------------
# Tier 2.2 + 2.3 — Main recommender
# ---------------------------------------------------------------------------

def get_next_problem(db: Session, focus_topic: str = None, company: str = None) -> dict:
    """
    Determines recommended problems and spaced-repetition review items.

    Returns at least 3 unique problem recommendations plus all active reviews
    that are currently due.

    Tier 2.3: For topics with attempts_count < RAMP_THRESHOLD, candidates are
    restricted to Easy difficulty regardless of mastery score.

    Tier 2.2: With probability EPSILON, the top pick is swapped for a random
    problem outside the "productive struggle" mastery band (0.40–0.65), giving
    the user occasional exposure to topics outside their current weak zone.

    Parameters
    ----------
    focus_topic : prioritise this topic when non-None
    company     : filter problem pool to those with this company tag (1.1)
    """
    now = datetime.utcnow()

    # 1. Gather active spaced-repetition reviews that are due
    reviews_due = db.query(SpacedRepetition).filter(
        SpacedRepetition.next_due <= now,
        SpacedRepetition.stage < 5,
    ).all()

    reviews = []
    due_problem_ids = set()
    for r in reviews_due:
        prob = db.query(Problem).filter(Problem.id == r.problem_id).first()
        if prob:
            reviews.append({
                "problem_id": prob.id,
                "title": prob.title,
                "url": prob.url,
                "difficulty": prob.difficulty,
                "due_date": r.next_due,
                "stage": r.stage,
            })
            due_problem_ids.add(prob.id)

    # 2. Build base problem pool (optionally filtered by company — Tier 1.1)
    def _pool_query():
        q = db.query(Problem)
        if company:
            q = q.filter(Problem.companies.like(f"%{company}%"))
        return q.all()

    base_pool = _pool_query()
    base_pool_ids = {p.id for p in base_pool}

    # 3. Build a prioritized list of topics
    masteries = db.query(TopicMastery).all()

    prioritized_topics = []

    if focus_topic:
        focus_record = next((m for m in masteries if m.topic == focus_topic), None)
        if focus_record:
            prioritized_topics.append(focus_record)

    overdue_topics = []
    other_topics = []

    for m in masteries:
        if focus_topic and m.topic == focus_topic:
            continue  # already added above

        has_problems = any(
            m.topic in (p.topics or "") for p in base_pool
        )
        if not has_problems:
            continue

        if m.next_review_date and m.next_review_date <= now:
            overdue_topics.append(m)
        else:
            other_topics.append(m)

    # Sort by mastery_score ascending so weakest topics come first
    overdue_topics.sort(key=lambda x: x.mastery_score)
    other_topics.sort(key=lambda x: x.mastery_score)

    prioritized_topics.extend(overdue_topics)
    prioritized_topics.extend(other_topics)

    recommendations = []
    recommended_ids = set()

    def add_recommendation(p, reason):
        if p.id not in recommended_ids and p.id not in due_problem_ids and p.id in base_pool_ids:
            recommendations.append({
                "problem_id": p.id,
                "title": p.title,
                "url": p.url,
                "difficulty": p.difficulty,
                "reason": reason,
            })
            recommended_ids.add(p.id)
            return True
        return False

    # 4. Iterate topics collecting at least 3 unique recommendations
    for topic_record in prioritized_topics:
        if len(recommendations) >= 3:
            break

        topic = topic_record.topic
        mastery_score = topic_record.mastery_score
        rating = topic_record.rating

        # --- Tier 2.3: difficulty ramp for new topics ---
        if topic_record.attempts_count < RAMP_THRESHOLD:
            target_difficulty = "Easy"
            difficulty_reason = (
                f"Starting your {topic} journey with Easy problems to build a foundation."
            )
        elif mastery_score < 0.40:
            target_difficulty = "Easy"
            difficulty_reason = (
                f"Your Elo rating for {topic} is {rating:.0f} (mastery {mastery_score:.0%})."
            )
        elif mastery_score < 0.65:
            target_difficulty = "Medium"
            difficulty_reason = (
                f"Your Elo rating for {topic} is {rating:.0f} (mastery {mastery_score:.0%})."
            )
        else:
            target_difficulty = "Hard"
            difficulty_reason = (
                f"Your Elo rating for {topic} is {rating:.0f} (mastery {mastery_score:.0%})."
            )

        # Adjust for recent streaks
        topic_problems = [p for p in base_pool if topic in (p.topics or "")]
        topic_prob_ids = [p.id for p in topic_problems]
        recent_attempts = (
            db.query(Attempt)
            .filter(Attempt.problem_id.in_(topic_prob_ids))
            .order_by(desc(Attempt.timestamp))
            .limit(3)
            .all()
        )

        if len(recent_attempts) >= 2:
            last_verdicts = [a.verdict for a in recent_attempts[:2]]
            if all(v == "Accepted" for v in last_verdicts):
                if target_difficulty == "Easy":
                    target_difficulty = "Medium"
                    difficulty_reason = f"You solved the last 2 {topic} problems! Upgrading to Medium."
                elif target_difficulty == "Medium":
                    target_difficulty = "Hard"
                    difficulty_reason = f"You solved the last 2 {topic} problems! Upgrading to Hard."
            elif all(v != "Accepted" for v in last_verdicts):
                if target_difficulty == "Hard":
                    target_difficulty = "Medium"
                    difficulty_reason = f"Let's try Medium difficulty in {topic} to rebuild confidence."
                elif target_difficulty == "Medium":
                    target_difficulty = "Easy"
                    difficulty_reason = f"Let's build core concepts in {topic} with an Easy problem."

        # Build reason string
        if focus_topic and topic == focus_topic:
            reason_prefix = "Focus topic suggestion."
        elif topic_record in overdue_topics:
            reason_prefix = f"Review due for {topic}."
        else:
            reason_prefix = f"Lowest mastery focus: {topic}."

        full_reason = f"{reason_prefix} {difficulty_reason}"

        # Prioritise retrying the last failed problem
        if recent_attempts and recent_attempts[0].verdict != "Accepted":
            failed_prob = db.query(Problem).filter(
                Problem.id == recent_attempts[0].problem_id
            ).first()
            if failed_prob and failed_prob.id in base_pool_ids:
                add_recommendation(
                    failed_prob,
                    f"Retry {failed_prob.title} to resolve your last failure: "
                    f"{recent_attempts[0].root_cause_category or 'implementation bug'}.",
                )

        # Primary: problems matching topic & target difficulty (not solved recently)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        problems = [
            p for p in topic_problems if p.difficulty == target_difficulty
        ]

        for p in problems:
            if len(recommendations) >= 3:
                break
            recent_success = db.query(Attempt).filter(
                Attempt.problem_id == p.id,
                Attempt.verdict == "Accepted",
                Attempt.timestamp >= seven_days_ago,
            ).first()
            if not recent_success:
                add_recommendation(p, full_reason)

        # Fallback: any difficulty in topic
        if len(recommendations) < 3:
            for p in topic_problems:
                if len(recommendations) >= 3:
                    break
                add_recommendation(p, f"{reason_prefix} Practicing topic: {topic}.")

    # 5. Global fallback
    if len(recommendations) < 3:
        for p in base_pool:
            if len(recommendations) >= 3:
                break
            add_recommendation(p, "General practice recommendation.")

    # --- Tier 2.2: epsilon-greedy exploration ---
    if recommendations and random.random() < EPSILON:
        # Pick a random problem outside the productive-struggle band (mastery 0.40–0.65)
        # i.e. topics that are either very easy (mastery > 0.65) or untouched (< 0.40 and new)
        exploration_topics = [
            m for m in masteries
            if not (0.40 <= m.mastery_score <= 0.65)
            and m.topic != focus_topic
        ]
        if exploration_topics:
            exp_topic = random.choice(exploration_topics)
            exp_probs = [
                p for p in base_pool
                if exp_topic.topic in (p.topics or "")
                and p.id not in recommended_ids
                and p.id not in due_problem_ids
            ]
            if exp_probs:
                ep = random.choice(exp_probs)
                # Replace the last recommendation with the exploration pick
                recommendations[-1] = {
                    "problem_id": ep.id,
                    "title": ep.title,
                    "url": ep.url,
                    "difficulty": ep.difficulty,
                    "reason": f"Exploration: trying {exp_topic.topic} to broaden your skills.",
                }

    return {"recommendations": recommendations, "reviews": reviews}
