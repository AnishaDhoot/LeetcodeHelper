from backend.database import SessionLocal, engine, Base
from backend.models import Problem, TopicMastery

# Predefined standard LeetCode problems for DSA prep
SEED_PROBLEMS = [
    # Arrays & Hashing
    {
        "id": "two-sum",
        "title": "Two Sum",
        "url": "https://leetcode.com/problems/two-sum/",
        "difficulty": "Easy",
        "topics": "Arrays & Hashing"
    },
    {
        "id": "contains-duplicate",
        "title": "Contains Duplicate",
        "url": "https://leetcode.com/problems/contains-duplicate/",
        "difficulty": "Easy",
        "topics": "Arrays & Hashing"
    },
    {
        "id": "valid-anagram",
        "title": "Valid Anagram",
        "url": "https://leetcode.com/problems/valid-anagram/",
        "difficulty": "Easy",
        "topics": "Arrays & Hashing"
    },
    {
        "id": "group-anagrams",
        "title": "Group Anagrams",
        "url": "https://leetcode.com/problems/group-anagrams/",
        "difficulty": "Medium",
        "topics": "Arrays & Hashing"
    },
    # Two Pointers
    {
        "id": "valid-palindrome",
        "title": "Valid Palindrome",
        "url": "https://leetcode.com/problems/valid-palindrome/",
        "difficulty": "Easy",
        "topics": "Two Pointers"
    },
    {
        "id": "two-sum-ii-input-array-is-sorted",
        "title": "Two Sum II - Input Array Is Sorted",
        "url": "https://leetcode.com/problems/two-sum-ii-input-array-is-sorted/",
        "difficulty": "Medium",
        "topics": "Two Pointers"
    },
    {
        "id": "3sum",
        "title": "3Sum",
        "url": "https://leetcode.com/problems/3sum/",
        "difficulty": "Medium",
        "topics": "Two Pointers"
    },
    {
        "id": "container-with-most-water",
        "title": "Container With Most Water",
        "url": "https://leetcode.com/problems/container-with-most-water/",
        "difficulty": "Medium",
        "topics": "Two Pointers"
    },
    # Sliding Window
    {
        "id": "best-time-to-buy-and-sell-stock",
        "title": "Best Time to Buy and Sell Stock",
        "url": "https://leetcode.com/problems/best-time-to-buy-and-sell-stock/",
        "difficulty": "Easy",
        "topics": "Sliding Window"
    },
    {
        "id": "longest-substring-without-repeating-characters",
        "title": "Longest Substring Without Repeating Characters",
        "url": "https://leetcode.com/problems/longest-substring-without-repeating-characters/",
        "difficulty": "Medium",
        "topics": "Sliding Window"
    },
    {
        "id": "longest-repeating-character-replacement",
        "title": "Longest Repeating Character Replacement",
        "url": "https://leetcode.com/problems/longest-repeating-character-replacement/",
        "difficulty": "Medium",
        "topics": "Sliding Window"
    },
    # Stack
    {
        "id": "valid-parentheses",
        "title": "Valid Parentheses",
        "url": "https://leetcode.com/problems/valid-parentheses/",
        "difficulty": "Easy",
        "topics": "Stack"
    },
    {
        "id": "min-stack",
        "title": "Min Stack",
        "url": "https://leetcode.com/problems/min-stack/",
        "difficulty": "Medium",
        "topics": "Stack"
    },
    {
        "id": "evaluate-reverse-polish-notation",
        "title": "Evaluate Reverse Polish Notation",
        "url": "https://leetcode.com/problems/evaluate-reverse-polish-notation/",
        "difficulty": "Medium",
        "topics": "Stack"
    },
    # Binary Search
    {
        "id": "binary-search",
        "title": "Binary Search",
        "url": "https://leetcode.com/problems/binary-search/",
        "difficulty": "Easy",
        "topics": "Binary Search"
    },
    {
        "id": "search-a-2d-matrix",
        "title": "Search a 2D Matrix",
        "url": "https://leetcode.com/problems/search-a-2d-matrix/",
        "difficulty": "Medium",
        "topics": "Binary Search"
    },
    {
        "id": "find-minimum-in-rotated-sorted-array",
        "title": "Find Minimum in Rotated Sorted Array",
        "url": "https://leetcode.com/problems/find-minimum-in-rotated-sorted-array/",
        "difficulty": "Medium",
        "topics": "Binary Search"
    },
    # Linked List
    {
        "id": "reverse-linked-list",
        "title": "Reverse Linked List",
        "url": "https://leetcode.com/problems/reverse-linked-list/",
        "difficulty": "Easy",
        "topics": "Linked List"
    },
    {
        "id": "merge-two-sorted-lists",
        "title": "Merge Two Sorted Lists",
        "url": "https://leetcode.com/problems/merge-two-sorted-lists/",
        "difficulty": "Easy",
        "topics": "Linked List"
    },
    {
        "id": "linked-list-cycle",
        "title": "Linked List Cycle",
        "url": "https://leetcode.com/problems/linked-list-cycle/",
        "difficulty": "Easy",
        "topics": "Linked List"
    },
    {
        "id": "remove-nth-node-from-end-of-list",
        "title": "Remove Nth Node From End of List",
        "url": "https://leetcode.com/problems/remove-nth-node-from-end-of-list/",
        "difficulty": "Medium",
        "topics": "Linked List"
    },
    # Trees
    {
        "id": "invert-binary-tree",
        "title": "Invert Binary Tree",
        "url": "https://leetcode.com/problems/invert-binary-tree/",
        "difficulty": "Easy",
        "topics": "Trees"
    },
    {
        "id": "maximum-depth-of-binary-tree",
        "title": "Maximum Depth of Binary Tree",
        "url": "https://leetcode.com/problems/maximum-depth-of-binary-tree/",
        "difficulty": "Easy",
        "topics": "Trees"
    },
    {
        "id": "same-tree",
        "title": "Same Tree",
        "url": "https://leetcode.com/problems/same-tree/",
        "difficulty": "Easy",
        "topics": "Trees"
    },
    {
        "id": "binary-tree-level-order-traversal",
        "title": "Binary Tree Level Order Traversal",
        "url": "https://leetcode.com/problems/binary-tree-level-order-traversal/",
        "difficulty": "Medium",
        "topics": "Trees"
    },
    # Backtracking
    {
        "id": "subsets",
        "title": "Subsets",
        "url": "https://leetcode.com/problems/subsets/",
        "difficulty": "Medium",
        "topics": "Backtracking"
    },
    {
        "id": "combination-sum",
        "title": "Combination Sum",
        "url": "https://leetcode.com/problems/combination-sum/",
        "difficulty": "Medium",
        "topics": "Backtracking"
    },
    # Dynamic Programming
    {
        "id": "climbing-stairs",
        "title": "Climbing Stairs",
        "url": "https://leetcode.com/problems/climbing-stairs/",
        "difficulty": "Easy",
        "topics": "Dynamic Programming"
    },
    {
        "id": "coin-change",
        "title": "Coin Change",
        "url": "https://leetcode.com/problems/coin-change/",
        "difficulty": "Medium",
        "topics": "Dynamic Programming"
    },
    {
        "id": "longest-increasing-subsequence",
        "title": "Longest Increasing Subsequence",
        "url": "https://leetcode.com/problems/longest-increasing-subsequence/",
        "difficulty": "Medium",
        "topics": "Dynamic Programming"
    }
]

def seed_db():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Seed Problems
        print("Seeding problems...")
        for prob_data in SEED_PROBLEMS:
            # Check if exists
            exists = db.query(Problem).filter(Problem.id == prob_data["id"]).first()
            if not exists:
                prob = Problem(
                    id=prob_data["id"],
                    title=prob_data["title"],
                    url=prob_data["url"],
                    difficulty=prob_data["difficulty"],
                    topics=prob_data["topics"]
                )
                db.add(prob)
        
        # Extract unique topics
        unique_topics = set(p["topics"] for p in SEED_PROBLEMS)
        
        # Seed TopicMastery
        print("Seeding topic mastery records...")
        for topic_name in unique_topics:
            exists = db.query(TopicMastery).filter(TopicMastery.topic == topic_name).first()
            if not exists:
                mastery = TopicMastery(
                    topic=topic_name,
                    mastery_score=0.0,
                    attempts_count=0,
                    success_rate=0.0
                )
                db.add(mastery)
                
        db.commit()
        print("Database seeding completed successfully!")
    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_db()
