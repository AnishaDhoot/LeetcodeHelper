import sqlite3
from pathlib import Path

db_path = Path(__file__).resolve().parent / "dsa_tutor.db"
print(f"Connecting to database at: {db_path}\n")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all table names
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [row[0] for row in cursor.fetchall()]

print("=== DATABASE TABLES ===")
for t in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {t};")
    count = cursor.fetchone()[0]
    print(f" • {t}: {count} row(s)")

print("\n=== TOPIC MASTERY (ELO RATINGS) ===")
cursor.execute("SELECT topic, rating, attempts_count, success_count FROM topic_mastery ORDER BY rating DESC LIMIT 10;")
rows = cursor.fetchall()
if rows:
    print(f"{'Topic':<30} | {'Elo Rating':<10} | {'Attempts':<8} | {'Successes':<8}")
    print("-" * 65)
    for r in rows:
        print(f"{r[0]:<30} | {r[1]:<10.1f} | {r[2]:<8} | {r[3]:<8}")
else:
    print("No topic mastery records found yet.")

print("\n=== RECENT SUBMISSION ATTEMPTS ===")
cursor.execute("SELECT problem_id, verdict, root_cause_category, timestamp FROM attempts ORDER BY timestamp DESC LIMIT 5;")
attempts = cursor.fetchall()
if attempts:
    print(f"{'Problem ID':<25} | {'Verdict':<15} | {'Category':<18} | {'Timestamp'}")
    print("-" * 75)
    for a in attempts:
        print(f"{a[0]:<25} | {a[1]:<15} | {str(a[2]):<18} | {a[3]}")
else:
    print("No attempts recorded yet.")

print("\n=== ACTIVE SPACED REPETITION REVIEWS ===")
cursor.execute("SELECT problem_id, stage, next_due FROM spaced_repetition LIMIT 5;")
reviews = cursor.fetchall()
if reviews:
    print(f"{'Problem ID':<25} | {'Stage':<6} | {'Next Due'}")
    print("-" * 55)
    for r in reviews:
        print(f"{r[0]:<25} | Stage {r[1]:<2} | {r[2]}")
else:
    print("No active spaced repetition schedules found.")

conn.close()
