from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc
from backend.models import Problem, Attempt, TopicMastery, SpacedRepetition

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


def update_spaced_repetition(db: Session, problem_id: str):
    """
    Saves or advances the spaced repetition schedule for a solved problem.
    Stages:
      Stage 1: solved initially, review due in 3 days.
      Stage 2: solved second time, review due in 7 days.
      Stage 3: solved third time, review due in 14 days.
      Stage 4: completed, scheduled far in the future.
    """
    now = datetime.utcnow()
    sr = db.query(SpacedRepetition).filter(SpacedRepetition.problem_id == problem_id).first()
    
    if not sr:
        # First solve: review in 3 days
        sr = SpacedRepetition(
            problem_id=problem_id,
            stage=1,
            last_solved=now,
            next_due=now + timedelta(days=3)
        )
        db.add(sr)
    else:
        # Solve exists: advance stage
        if sr.stage == 1:
            sr.stage = 2
            sr.next_due = now + timedelta(days=7)
        elif sr.stage == 2:
            sr.stage = 3
            sr.next_due = now + timedelta(days=14)
        elif sr.stage >= 3:
            sr.stage = 4
            sr.next_due = now + timedelta(days=3650) # Far future
            
        sr.last_solved = now

    db.commit()
    db.refresh(sr)
    return sr


def get_next_problem(db: Session, focus_topic: str = None) -> dict:
    """
    Determines recommended problems and spaced repetition review items.
    Returns at least 3 unique problem recommendations and a list of active reviews due.
    """
    now = datetime.utcnow()

    # 1. Gather all active reviews due (spaced repetition next_due <= now)
    reviews_due = db.query(SpacedRepetition).filter(
        SpacedRepetition.next_due <= now,
        SpacedRepetition.stage < 4
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
                "stage": r.stage
            })
            due_problem_ids.add(prob.id)

    # 2. Determine topics to pull recommendations from
    masteries = db.query(TopicMastery).all()
    
    # Prioritize topics
    prioritized_topics = []
    if focus_topic:
        focus_record = next((m for m in masteries if m.topic == focus_topic), None)
        if focus_record:
            prioritized_topics.append(focus_record)
            
    # Add overdue and other topics (excluding focus_topic if already added)
    overdue_topics = []
    other_topics = []
    for m in masteries:
        if focus_topic and m.topic == focus_topic:
            continue
            
        # Check if topic has problems
        has_problems = db.query(Problem).filter(Problem.topics.like(f"%{m.topic}%")).first() is not None
        if not has_problems:
            continue

        if m.next_due_date and m.next_due_date <= now:
            overdue_topics.append(m)
        else:
            other_topics.append(m)

    overdue_topics.sort(key=lambda x: x.mastery_score)
    other_topics.sort(key=lambda x: x.mastery_score)
    
    prioritized_topics.extend(overdue_topics)
    prioritized_topics.extend(other_topics)

    recommendations = []
    recommended_ids = set()

    # Helper function to add a problem to recommendations
    def add_recommendation(p: Problem, reason: str):
        if p.id not in recommended_ids and p.id not in due_problem_ids:
            recommendations.append({
                "problem_id": p.id,
                "title": p.title,
                "url": p.url,
                "difficulty": p.difficulty,
                "reason": reason
            })
            recommended_ids.add(p.id)
            return True
        return False

    # 3. Iterate through topics to collect at least 3 unique recommendations
    for topic_record in prioritized_topics:
        if len(recommendations) >= 3:
            break
            
        topic = topic_record.topic
        mastery_score = topic_record.mastery_score

        # Determine target difficulty based on mastery & recent attempts
        topic_problems = db.query(Problem).filter(Problem.topics.like(f"%{topic}%")).all()
        topic_prob_ids = [p.id for p in topic_problems]
        
        recent_attempts = db.query(Attempt).filter(
            Attempt.problem_id.in_(topic_prob_ids)
        ).order_by(desc(Attempt.timestamp)).limit(3).all()

        if mastery_score < 0.4:
            target_difficulty = "Easy"
        elif mastery_score < 0.75:
            target_difficulty = "Medium"
        else:
            target_difficulty = "Hard"

        difficulty_reason = f"Your mastery score for {topic} is {mastery_score:.1%}."

        if len(recent_attempts) >= 2:
            last_verdicts = [a.verdict for a in recent_attempts[:2]]
            if all(v == "Accepted" for v in last_verdicts):
                if target_difficulty == "Easy":
                    target_difficulty = "Medium"
                    difficulty_reason = f"You solved the last 2 problems in {topic}! Upgrading you to Medium."
                elif target_difficulty == "Medium":
                    target_difficulty = "Hard"
                    difficulty_reason = f"You solved the last 2 problems in {topic}! Upgrading you to Hard."
            elif all(v != "Accepted" for v in last_verdicts):
                if target_difficulty == "Hard":
                    target_difficulty = "Medium"
                    difficulty_reason = f"Let's try Medium difficulty in {topic} to rebuild confidence."
                elif target_difficulty == "Medium":
                    target_difficulty = "Easy"
                    difficulty_reason = f"Let's build core concepts in {topic} with an Easy problem."

        reason_prefix = ""
        if focus_topic and topic == focus_topic:
            reason_prefix = f"🎯 Focus topic suggestion."
        elif topic_record in overdue_topics:
            reason_prefix = f"⌛ Review due for {topic}."
        else:
            reason_prefix = f"💡 Lowest mastery focus: {topic}."

        full_reason = f"{reason_prefix} {difficulty_reason}"

        # If the last attempt failed, prioritize recommending retrying it
        if recent_attempts and recent_attempts[0].verdict != "Accepted":
            failed_prob = db.query(Problem).filter(Problem.id == recent_attempts[0].problem_id).first()
            if failed_prob:
                add_recommendation(
                    failed_prob, 
                    f"Retry {failed_prob.title} to resolve your last failure: {recent_attempts[0].root_cause_category or 'implementation bug'}."
                )

        # Retrieve matching problems (topic & difficulty)
        problems = db.query(Problem).filter(
            Problem.topics.like(f"%{topic}%"),
            Problem.difficulty == target_difficulty
        ).all()

        # Filter out completed recently (e.g. in last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        for p in problems:
            if len(recommendations) >= 3:
                break
            recent_success = db.query(Attempt).filter(
                Attempt.problem_id == p.id,
                Attempt.verdict == "Accepted",
                Attempt.timestamp >= seven_days_ago
            ).first()
            if not recent_success:
                add_recommendation(p, full_reason)

        # Fallback 1: Allow any difficulty in topic
        if len(recommendations) < 3:
            all_topic_problems = db.query(Problem).filter(Problem.topics.like(f"%{topic}%")).all()
            for p in all_topic_problems:
                if len(recommendations) >= 3:
                    break
                add_recommendation(p, f"{reason_prefix} Practicing topic: {topic}.")

    # 4. Global Fallbacks if we still have fewer than 3 recommendations
    if len(recommendations) < 3:
        all_problems = db.query(Problem).all()
        for p in all_problems:
            if len(recommendations) >= 3:
                break
            add_recommendation(p, "General practice recommendation.")

    return {
        "recommendations": recommendations,
        "reviews": reviews
    }
