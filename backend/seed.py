from backend.database import SessionLocal, engine, Base
from backend.models import Problem, TopicMastery

# Predefined standard LeetCode problems with topic + company tags
SEED_PROBLEMS = [
    # Arrays & Hashing
    {
        "id": "two-sum",
        "title": "Two Sum",
        "url": "https://leetcode.com/problems/two-sum/",
        "difficulty": "Easy",
        "topics": "Arrays & Hashing",
        "companies": "Google,Amazon,Facebook,Apple,Microsoft"
    },
    {
        "id": "contains-duplicate",
        "title": "Contains Duplicate",
        "url": "https://leetcode.com/problems/contains-duplicate/",
        "difficulty": "Easy",
        "topics": "Arrays & Hashing",
        "companies": "Amazon,Apple"
    },
    {
        "id": "valid-anagram",
        "title": "Valid Anagram",
        "url": "https://leetcode.com/problems/valid-anagram/",
        "difficulty": "Easy",
        "topics": "Arrays & Hashing",
        "companies": "Amazon,Google,Microsoft"
    },
    {
        "id": "group-anagrams",
        "title": "Group Anagrams",
        "url": "https://leetcode.com/problems/group-anagrams/",
        "difficulty": "Medium",
        "topics": "Arrays & Hashing",
        "companies": "Amazon,Google,Facebook,Uber"
    },
    {
        "id": "top-k-frequent-elements",
        "title": "Top K Frequent Elements",
        "url": "https://leetcode.com/problems/top-k-frequent-elements/",
        "difficulty": "Medium",
        "topics": "Arrays & Hashing",
        "companies": "Amazon,Google,Facebook,Uber"
    },
    {
        "id": "product-of-array-except-self",
        "title": "Product of Array Except Self",
        "url": "https://leetcode.com/problems/product-of-array-except-self/",
        "difficulty": "Medium",
        "topics": "Arrays & Hashing",
        "companies": "Amazon,Google,Facebook,Microsoft"
    },
    # Two Pointers
    {
        "id": "valid-palindrome",
        "title": "Valid Palindrome",
        "url": "https://leetcode.com/problems/valid-palindrome/",
        "difficulty": "Easy",
        "topics": "Two Pointers",
        "companies": "Facebook,Amazon,Microsoft"
    },
    {
        "id": "two-sum-ii-input-array-is-sorted",
        "title": "Two Sum II - Input Array Is Sorted",
        "url": "https://leetcode.com/problems/two-sum-ii-input-array-is-sorted/",
        "difficulty": "Medium",
        "topics": "Two Pointers",
        "companies": "Amazon,Google"
    },
    {
        "id": "3sum",
        "title": "3Sum",
        "url": "https://leetcode.com/problems/3sum/",
        "difficulty": "Medium",
        "topics": "Two Pointers",
        "companies": "Amazon,Google,Facebook,Microsoft,Adobe"
    },
    {
        "id": "container-with-most-water",
        "title": "Container With Most Water",
        "url": "https://leetcode.com/problems/container-with-most-water/",
        "difficulty": "Medium",
        "topics": "Two Pointers",
        "companies": "Google,Amazon,Facebook,Bloomberg"
    },
    # Sliding Window
    {
        "id": "best-time-to-buy-and-sell-stock",
        "title": "Best Time to Buy and Sell Stock",
        "url": "https://leetcode.com/problems/best-time-to-buy-and-sell-stock/",
        "difficulty": "Easy",
        "topics": "Sliding Window",
        "companies": "Amazon,Google,Facebook,Goldman Sachs"
    },
    {
        "id": "longest-substring-without-repeating-characters",
        "title": "Longest Substring Without Repeating Characters",
        "url": "https://leetcode.com/problems/longest-substring-without-repeating-characters/",
        "difficulty": "Medium",
        "topics": "Sliding Window",
        "companies": "Amazon,Google,Facebook,Microsoft,Bloomberg"
    },
    {
        "id": "longest-repeating-character-replacement",
        "title": "Longest Repeating Character Replacement",
        "url": "https://leetcode.com/problems/longest-repeating-character-replacement/",
        "difficulty": "Medium",
        "topics": "Sliding Window",
        "companies": "Google,Amazon"
    },
    {
        "id": "minimum-window-substring",
        "title": "Minimum Window Substring",
        "url": "https://leetcode.com/problems/minimum-window-substring/",
        "difficulty": "Hard",
        "topics": "Sliding Window",
        "companies": "Google,Facebook,Amazon,LinkedIn"
    },
    # Stack
    {
        "id": "valid-parentheses",
        "title": "Valid Parentheses",
        "url": "https://leetcode.com/problems/valid-parentheses/",
        "difficulty": "Easy",
        "topics": "Stack",
        "companies": "Google,Amazon,Facebook,Microsoft,Bloomberg"
    },
    {
        "id": "min-stack",
        "title": "Min Stack",
        "url": "https://leetcode.com/problems/min-stack/",
        "difficulty": "Medium",
        "topics": "Stack",
        "companies": "Amazon,Google,Microsoft"
    },
    {
        "id": "evaluate-reverse-polish-notation",
        "title": "Evaluate Reverse Polish Notation",
        "url": "https://leetcode.com/problems/evaluate-reverse-polish-notation/",
        "difficulty": "Medium",
        "topics": "Stack",
        "companies": "Amazon,LinkedIn"
    },
    {
        "id": "daily-temperatures",
        "title": "Daily Temperatures",
        "url": "https://leetcode.com/problems/daily-temperatures/",
        "difficulty": "Medium",
        "topics": "Stack",
        "companies": "Google,Amazon"
    },
    # Binary Search
    {
        "id": "binary-search",
        "title": "Binary Search",
        "url": "https://leetcode.com/problems/binary-search/",
        "difficulty": "Easy",
        "topics": "Binary Search",
        "companies": "Google,Amazon,Facebook"
    },
    {
        "id": "search-a-2d-matrix",
        "title": "Search a 2D Matrix",
        "url": "https://leetcode.com/problems/search-a-2d-matrix/",
        "difficulty": "Medium",
        "topics": "Binary Search",
        "companies": "Google,Amazon,Microsoft"
    },
    {
        "id": "find-minimum-in-rotated-sorted-array",
        "title": "Find Minimum in Rotated Sorted Array",
        "url": "https://leetcode.com/problems/find-minimum-in-rotated-sorted-array/",
        "difficulty": "Medium",
        "topics": "Binary Search",
        "companies": "Google,Amazon,Facebook,Microsoft"
    },
    {
        "id": "search-in-rotated-sorted-array",
        "title": "Search in Rotated Sorted Array",
        "url": "https://leetcode.com/problems/search-in-rotated-sorted-array/",
        "difficulty": "Medium",
        "topics": "Binary Search",
        "companies": "Google,Facebook,Amazon,Microsoft,Bloomberg"
    },
    {
        "id": "median-of-two-sorted-arrays",
        "title": "Median of Two Sorted Arrays",
        "url": "https://leetcode.com/problems/median-of-two-sorted-arrays/",
        "difficulty": "Hard",
        "topics": "Binary Search",
        "companies": "Google,Amazon,Adobe"
    },
    # Linked List
    {
        "id": "reverse-linked-list",
        "title": "Reverse Linked List",
        "url": "https://leetcode.com/problems/reverse-linked-list/",
        "difficulty": "Easy",
        "topics": "Linked List",
        "companies": "Amazon,Google,Facebook,Microsoft"
    },
    {
        "id": "merge-two-sorted-lists",
        "title": "Merge Two Sorted Lists",
        "url": "https://leetcode.com/problems/merge-two-sorted-lists/",
        "difficulty": "Easy",
        "topics": "Linked List",
        "companies": "Amazon,Google,Microsoft,Bloomberg"
    },
    {
        "id": "linked-list-cycle",
        "title": "Linked List Cycle",
        "url": "https://leetcode.com/problems/linked-list-cycle/",
        "difficulty": "Easy",
        "topics": "Linked List",
        "companies": "Amazon,Google,Microsoft"
    },
    {
        "id": "remove-nth-node-from-end-of-list",
        "title": "Remove Nth Node From End of List",
        "url": "https://leetcode.com/problems/remove-nth-node-from-end-of-list/",
        "difficulty": "Medium",
        "topics": "Linked List",
        "companies": "Amazon,Google,Facebook"
    },
    {
        "id": "lru-cache",
        "title": "LRU Cache",
        "url": "https://leetcode.com/problems/lru-cache/",
        "difficulty": "Medium",
        "topics": "Linked List",
        "companies": "Amazon,Google,Facebook,Microsoft,Bloomberg"
    },
    {
        "id": "merge-k-sorted-lists",
        "title": "Merge K Sorted Lists",
        "url": "https://leetcode.com/problems/merge-k-sorted-lists/",
        "difficulty": "Hard",
        "topics": "Linked List",
        "companies": "Amazon,Google,Facebook,LinkedIn"
    },
    # Trees
    {
        "id": "invert-binary-tree",
        "title": "Invert Binary Tree",
        "url": "https://leetcode.com/problems/invert-binary-tree/",
        "difficulty": "Easy",
        "topics": "Trees",
        "companies": "Google,Amazon,Facebook"
    },
    {
        "id": "maximum-depth-of-binary-tree",
        "title": "Maximum Depth of Binary Tree",
        "url": "https://leetcode.com/problems/maximum-depth-of-binary-tree/",
        "difficulty": "Easy",
        "topics": "Trees",
        "companies": "Amazon,LinkedIn"
    },
    {
        "id": "same-tree",
        "title": "Same Tree",
        "url": "https://leetcode.com/problems/same-tree/",
        "difficulty": "Easy",
        "topics": "Trees",
        "companies": "Bloomberg,Amazon"
    },
    {
        "id": "binary-tree-level-order-traversal",
        "title": "Binary Tree Level Order Traversal",
        "url": "https://leetcode.com/problems/binary-tree-level-order-traversal/",
        "difficulty": "Medium",
        "topics": "Trees",
        "companies": "Amazon,Google,Facebook,Microsoft"
    },
    {
        "id": "validate-binary-search-tree",
        "title": "Validate Binary Search Tree",
        "url": "https://leetcode.com/problems/validate-binary-search-tree/",
        "difficulty": "Medium",
        "topics": "Trees",
        "companies": "Amazon,Google,Facebook,Bloomberg"
    },
    {
        "id": "lowest-common-ancestor-of-a-binary-search-tree",
        "title": "Lowest Common Ancestor of a BST",
        "url": "https://leetcode.com/problems/lowest-common-ancestor-of-a-binary-search-tree/",
        "difficulty": "Medium",
        "topics": "Trees",
        "companies": "Amazon,Google,Facebook,Microsoft"
    },
    {
        "id": "serialize-and-deserialize-binary-tree",
        "title": "Serialize and Deserialize Binary Tree",
        "url": "https://leetcode.com/problems/serialize-and-deserialize-binary-tree/",
        "difficulty": "Hard",
        "topics": "Trees",
        "companies": "Google,Amazon,Facebook,Microsoft"
    },
    # Backtracking
    {
        "id": "subsets",
        "title": "Subsets",
        "url": "https://leetcode.com/problems/subsets/",
        "difficulty": "Medium",
        "topics": "Backtracking",
        "companies": "Facebook,Amazon,Google"
    },
    {
        "id": "combination-sum",
        "title": "Combination Sum",
        "url": "https://leetcode.com/problems/combination-sum/",
        "difficulty": "Medium",
        "topics": "Backtracking",
        "companies": "Amazon,Google,Airbnb"
    },
    {
        "id": "permutations",
        "title": "Permutations",
        "url": "https://leetcode.com/problems/permutations/",
        "difficulty": "Medium",
        "topics": "Backtracking",
        "companies": "Microsoft,LinkedIn,Adobe"
    },
    {
        "id": "word-search",
        "title": "Word Search",
        "url": "https://leetcode.com/problems/word-search/",
        "difficulty": "Medium",
        "topics": "Backtracking",
        "companies": "Amazon,Facebook,Bloomberg,Microsoft"
    },
    # Dynamic Programming
    {
        "id": "climbing-stairs",
        "title": "Climbing Stairs",
        "url": "https://leetcode.com/problems/climbing-stairs/",
        "difficulty": "Easy",
        "topics": "Dynamic Programming",
        "companies": "Amazon,Google,Apple"
    },
    {
        "id": "coin-change",
        "title": "Coin Change",
        "url": "https://leetcode.com/problems/coin-change/",
        "difficulty": "Medium",
        "topics": "Dynamic Programming",
        "companies": "Amazon,Google,Microsoft"
    },
    {
        "id": "longest-increasing-subsequence",
        "title": "Longest Increasing Subsequence",
        "url": "https://leetcode.com/problems/longest-increasing-subsequence/",
        "difficulty": "Medium",
        "topics": "Dynamic Programming",
        "companies": "Amazon,Google,Microsoft"
    },
    {
        "id": "house-robber",
        "title": "House Robber",
        "url": "https://leetcode.com/problems/house-robber/",
        "difficulty": "Medium",
        "topics": "Dynamic Programming",
        "companies": "Amazon,Google,LinkedIn"
    },
    {
        "id": "longest-common-subsequence",
        "title": "Longest Common Subsequence",
        "url": "https://leetcode.com/problems/longest-common-subsequence/",
        "difficulty": "Medium",
        "topics": "Dynamic Programming",
        "companies": "Google,Amazon,Microsoft"
    },
    {
        "id": "word-break",
        "title": "Word Break",
        "url": "https://leetcode.com/problems/word-break/",
        "difficulty": "Medium",
        "topics": "Dynamic Programming",
        "companies": "Google,Amazon,Facebook,Bloomberg"
    },
    # Graphs
    {
        "id": "number-of-islands",
        "title": "Number of Islands",
        "url": "https://leetcode.com/problems/number-of-islands/",
        "difficulty": "Medium",
        "topics": "Graphs",
        "companies": "Amazon,Google,Facebook,Microsoft"
    },
    {
        "id": "clone-graph",
        "title": "Clone Graph",
        "url": "https://leetcode.com/problems/clone-graph/",
        "difficulty": "Medium",
        "topics": "Graphs",
        "companies": "Google,Facebook,Amazon"
    },
    {
        "id": "course-schedule",
        "title": "Course Schedule",
        "url": "https://leetcode.com/problems/course-schedule/",
        "difficulty": "Medium",
        "topics": "Graphs",
        "companies": "Google,Amazon,Facebook,Airbnb"
    },
    {
        "id": "pacific-atlantic-water-flow",
        "title": "Pacific Atlantic Water Flow",
        "url": "https://leetcode.com/problems/pacific-atlantic-water-flow/",
        "difficulty": "Medium",
        "topics": "Graphs",
        "companies": "Google,Amazon"
    },
    # Heap / Priority Queue
    {
        "id": "kth-largest-element-in-an-array",
        "title": "Kth Largest Element in an Array",
        "url": "https://leetcode.com/problems/kth-largest-element-in-an-array/",
        "difficulty": "Medium",
        "topics": "Heap / Priority Queue",
        "companies": "Amazon,Google,Facebook,Microsoft"
    },
    {
        "id": "find-median-from-data-stream",
        "title": "Find Median from Data Stream",
        "url": "https://leetcode.com/problems/find-median-from-data-stream/",
        "difficulty": "Hard",
        "topics": "Heap / Priority Queue",
        "companies": "Google,Amazon,Uber"
    },
]


def seed_db():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Seed Problems
        print("Seeding problems...")
        for prob_data in SEED_PROBLEMS:
            existing = db.query(Problem).filter(Problem.id == prob_data["id"]).first()
            if not existing:
                prob = Problem(
                    id=prob_data["id"],
                    title=prob_data["title"],
                    url=prob_data["url"],
                    difficulty=prob_data["difficulty"],
                    topics=prob_data["topics"],
                    companies=prob_data.get("companies"),
                )
                db.add(prob)
            else:
                # Patch companies onto existing rows that predate this field
                if existing.companies is None and prob_data.get("companies"):
                    existing.companies = prob_data["companies"]

        # Extract unique topics
        unique_topics = set(p["topics"] for p in SEED_PROBLEMS)

        # Seed TopicMastery
        print("Seeding topic mastery records...")
        for topic_name in unique_topics:
            exists = db.query(TopicMastery).filter(TopicMastery.topic == topic_name).first()
            if not exists:
                mastery = TopicMastery(
                    topic=topic_name,
                    rating=1200.0,
                    attempts_count=0,
                    success_count=0,
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
