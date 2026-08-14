"""
recommender.py — Test-driven topic mastery scoring & next-problem selection.
Badges and topic mastery levels (0-5) are unlocked strictly via Badge Tests.
"""

import random
import time
from datetime import datetime, timedelta, timezone

def get_utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
from sqlalchemy.orm import Session
from sqlalchemy import desc
from backend.models import Problem, Attempt, TopicMastery, SpacedRepetition

# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------
RAMP_THRESHOLD = 3
EPSILON = 0.15

# Weak-pair detection: min co-occurrence count and max badge level for "weak"
WEAK_PAIR_MIN_COOCCUR = 2
WEAK_PAIR_MAX_LEVEL = 2  # Level 0 or 1 (< 40% mastery)

# Module-level cache for weak pairs {result: list, computed_at: float}
_weak_pair_cache: dict = {"result": [], "computed_at": 0.0}
_WEAK_PAIR_TTL = 3600  # seconds


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
    Updates TopicMastery attempt/success metrics and reschedules spaced-repetition
    review dates. Badge levels advance exclusively via Badge Tests.
    """
    mastery = db.query(TopicMastery).filter(TopicMastery.topic == topic_name).first()
    if not mastery:
        mastery = TopicMastery(
            topic=topic_name,
            rating=1200.0,
            attempts_count=0,
            success_count=0,
            level=0
        )
        db.add(mastery)
        db.flush()

    now = get_utc_now()

    # --- Bookkeeping ---
    mastery.attempts_count += 1
    if is_success:
        mastery.success_count += 1
    mastery.last_updated = get_utc_now()

    # Keep rating column synchronized with level (800 + level * 240)
    mastery.rating = 800.0 + (mastery.level or 0) * 240.0

    # --- Spaced-repetition scheduling ---
    score = mastery.mastery_score  # derived 0-1 from level property
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
    now = get_utc_now()
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
        .filter(TopicMastery.level < WEAK_PAIR_MAX_LEVEL)
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

def get_next_problem(db: Session, focus_topic=None, company: str = None) -> dict:
    """
    Determines recommended problems and spaced-repetition review items.

    Returns at least 3 unique problem recommendations plus all active reviews
    that are currently due.

    Supports up to 3 focus topics (focus_topic can be a list or comma-separated string).
    """
    now = get_utc_now()

    # Normalize focus_topics list (up to 3)
    focus_list = []
    if isinstance(focus_topic, str) and focus_topic.strip():
        focus_list = [t.strip() for t in focus_topic.split(',') if t.strip()]
    elif isinstance(focus_topic, (list, tuple)):
        focus_list = [str(t).strip() for t in focus_topic if str(t).strip()]
    focus_list = focus_list[:3]

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
                "topics": prob.topics,
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

    for f_topic in focus_list:
        focus_record = next((m for m in masteries if m.topic == f_topic), None)
        if focus_record and focus_record not in prioritized_topics:
            prioritized_topics.append(focus_record)

    overdue_topics = []
    other_topics = []

    for m in masteries:
        if m.topic in focus_list:
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
                "topics": p.topics,
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
        level = topic_record.level or 0
        badge = topic_record.badge

        if level == 0:
            target_difficulty = "Easy"
            difficulty_reason = (
                f"Locked badge for {topic}. Try Easy questions to build foundation and start a test!"
            )
        elif level == 1:
            target_difficulty = "Easy"
            difficulty_reason = (
                f"You have the Bronze badge for {topic}. Try Easy questions to practice!"
            )
        elif level in [2, 3]:
            target_difficulty = "Medium"
            difficulty_reason = (
                f"You have the {badge} badge for {topic}. Recommending Medium difficulty."
            )
        else:
            target_difficulty = "Hard"
            difficulty_reason = (
                f"You have the {badge} badge for {topic}. Challenging you with Hard questions!"
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
        seven_days_ago = get_utc_now() - timedelta(days=7)
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
