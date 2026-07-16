from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc
from backend.models import Problem, Attempt, TopicMastery

def update_mastery_on_submission(db: Session, topic_name: str, is_success: bool):
    """
    Updates TopicMastery score, success rates, and spaced-repetition schedules.
    """
    mastery = db.query(TopicMastery).filter(TopicMastery.topic == topic_name).first()
    if not mastery:
        # Create mastery record if it doesn't exist
        mastery = TopicMastery(
            topic=topic_name,
            mastery_score=0.0,
            attempts_count=0,
            success_rate=0.0
        )
        db.add(mastery)
        db.flush()

    now = datetime.utcnow()
    mastery.attempts_count += 1
    mastery.last_attempted = now

    # Update success rate
    success_val = 1.0 if is_success else 0.0
    mastery.success_rate = ((mastery.success_rate * (mastery.attempts_count - 1)) + success_val) / mastery.attempts_count

    # Update mastery score and spaced repetition interval
    if is_success:
        # Increase mastery
        mastery.mastery_score = min(1.0, mastery.mastery_score + 0.15)
        
        # Spaced repetition schedule based on mastery score
        if mastery.mastery_score < 0.3:
            interval_days = 1
        elif mastery.mastery_score < 0.6:
            interval_days = 3
        elif mastery.mastery_score < 0.8:
            interval_days = 7
        else:
            interval_days = 14
        mastery.next_due_date = now + timedelta(days=interval_days)
    else:
        # Decrease mastery
        mastery.mastery_score = max(0.0, mastery.mastery_score - 0.08)
        # Needs review immediately
        mastery.next_due_date = now

    db.commit()
    db.refresh(mastery)
    return mastery

def get_next_problem(db: Session, focus_topic: str = None) -> dict:
    """
    Determines the next problem to recommend based on:
    1. Overdue spaced-repetition topics
    2. Lowest mastery score topics
    3. Performance history (success/failure streaks adjusting difficulty)

    If `focus_topic` is provided, recommendations are restricted to that topic
    (with graceful fallback to the normal logic if it has no available problems).
    """
    now = datetime.utcnow()

    # 1. Fetch all topic masteries
    masteries = db.query(TopicMastery).all()
    if not masteries:
        return {
            "problem_id": "two-sum",
            "title": "Two Sum",
            "url": "https://leetcode.com/problems/two-sum/",
            "difficulty": "Easy",
            "reason": "Database is unseeded. Start with the classic Two Sum!"
        }

    # Separate into overdue and standard topics
    overdue_topics = []
    other_topics = []

    for m in masteries:
        # Check if topic has any problems associated with it
        has_problems = db.query(Problem).filter(Problem.topics == m.topic).first() is not None
        if not has_problems:
            continue

        if m.next_due_date and m.next_due_date <= now:
            overdue_topics.append(m)
        else:
            other_topics.append(m)

    # Pick the target topic
    # Overdue topics sorted by lowest mastery first, then other topics sorted by lowest mastery
    overdue_topics.sort(key=lambda x: x.mastery_score)
    other_topics.sort(key=lambda x: x.mastery_score)

    selected_topic_record = None
    reason_prefix = ""

    # If a focus topic is set, try to honor it directly.
    if focus_topic:
        focus_record = next((m for m in masteries if m.topic == focus_topic), None)
        if focus_record:
            selected_topic_record = focus_record
            reason_prefix = f"Targeting your focus topic: {focus_topic}."

    if not selected_topic_record:
        if overdue_topics:
            selected_topic_record = overdue_topics[0]
            reason_prefix = f"Review session is overdue for {selected_topic_record.topic}."
        elif other_topics:
            selected_topic_record = other_topics[0]
            reason_prefix = f"Focusing on your lowest mastery topic: {selected_topic_record.topic}."
        else:
            # Fallback to any topic
            selected_topic_record = masteries[0]
            reason_prefix = f"Targeting topic: {selected_topic_record.topic}."

    topic = selected_topic_record.topic
    mastery_score = selected_topic_record.mastery_score

    # 2. Determine target difficulty
    # Analyze recent attempts in this topic to adjust difficulty tier
    # Get all problem IDs in this topic
    topic_problems = db.query(Problem).filter(Problem.topics == topic).all()
    topic_prob_ids = [p.id for p in topic_problems]
    
    recent_attempts = db.query(Attempt).filter(
        Attempt.problem_id.in_(topic_prob_ids)
    ).order_by(desc(Attempt.timestamp)).limit(3).all()

    # Default difficulty based on current mastery score
    if mastery_score < 0.4:
        target_difficulty = "Easy"
    elif mastery_score < 0.75:
        target_difficulty = "Medium"
    else:
        target_difficulty = "Hard"

    difficulty_reason = f"Your mastery is {mastery_score:.1%}."

    if len(recent_attempts) >= 2:
        # Check for success or failure streak
        last_verdicts = [a.verdict for a in recent_attempts[:2]]
        if all(v == "Accepted" for v in last_verdicts):
            # Success streak - upgrade difficulty if possible
            if target_difficulty == "Easy":
                target_difficulty = "Medium"
                difficulty_reason = "You got the last 2 problems correct! Upgrading you to Medium."
            elif target_difficulty == "Medium":
                target_difficulty = "Hard"
                difficulty_reason = "You got the last 2 problems correct! Upgrading you to Hard."
            else:
                difficulty_reason = "You are on a streak! Keep crushing Hard problems."
        elif all(v != "Accepted" for v in last_verdicts):
            # Failure streak - downgrade difficulty if possible
            if target_difficulty == "Hard":
                target_difficulty = "Medium"
                difficulty_reason = "Let's step down to Medium to build confidence after recent failures."
            elif target_difficulty == "Medium":
                target_difficulty = "Easy"
                difficulty_reason = "Let's step down to Easy to solidify concepts after recent failures."
            else:
                difficulty_reason = "Don't worry, let's try another Easy problem together."

    # If the absolute last attempt on this topic failed, suggest a retry of that exact problem!
    if recent_attempts and recent_attempts[0].verdict != "Accepted":
        failed_prob_id = recent_attempts[0].problem_id
        failed_prob = db.query(Problem).filter(Problem.id == failed_prob_id).first()
        if failed_prob:
            return {
                "problem_id": failed_prob.id,
                "title": failed_prob.title,
                "url": failed_prob.url,
                "difficulty": failed_prob.difficulty,
                "reason": f"Retrying {failed_prob.title} to resolve your last failure: {recent_attempts[0].root_cause_category or 'bug'}."
            }

    # 3. Find problems matching target topic & target difficulty
    problems = db.query(Problem).filter(
        Problem.topics == topic,
        Problem.difficulty == target_difficulty
    ).all()

    # Filter out problems successfully completed recently (e.g. in last 7 days)
    # to avoid repeating successful problems too quickly.
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    valid_problems = []
    
    for p in problems:
        recent_success = db.query(Attempt).filter(
            Attempt.problem_id == p.id,
            Attempt.verdict == "Accepted",
            Attempt.timestamp >= seven_days_ago
        ).first()
        if not recent_success:
            valid_problems.append(p)

    # Fallback cascade if no problems match difficulty + recent constraints:
    if not valid_problems:
        # Fallback 1: Allow recently completed problems of same difficulty
        valid_problems = problems

    if not valid_problems:
        # Fallback 2: Any problem in the topic (regardless of difficulty)
        valid_problems = db.query(Problem).filter(Problem.topics == topic).all()

    if not valid_problems:
        # Fallback 3: Absolutely any problem in the DB
        valid_problems = db.query(Problem).all()

    # Pick the first matching problem
    selected_problem = valid_problems[0]
    
    return {
        "problem_id": selected_problem.id,
        "title": selected_problem.title,
        "url": selected_problem.url,
        "difficulty": selected_problem.difficulty,
        "reason": f"{reason_prefix} {difficulty_reason}"
    }
