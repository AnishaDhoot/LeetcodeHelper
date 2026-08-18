import csv
import io
import urllib.request
from backend.database import SessionLocal, engine, Base
from backend.models import Problem, TopicMastery, Attempt, SpacedRepetition, DailyActivity, MockInterviewSession, BadgeTest, CompanyMetadata

SEED_DATA = {
  "topics": [
    {
      "name": "Arrays",
      "badges": [
        {
          "level": 1,
          "badge": "Bronze",
          "difficulty": "Easy",
          "questions": [
            { "title": "Two Sum", "slug": "two-sum" },
            { "title": "Best Time to Buy and Sell Stock", "slug": "best-time-to-buy-and-sell-stock" }
          ]
        },
        {
          "level": 2,
          "badge": "Silver",
          "difficulty": "Medium",
          "questions": [
            { "title": "Product of Array Except Self", "slug": "product-of-array-except-self" },
            { "title": "3Sum", "slug": "3sum" }
          ]
        },
        {
          "level": 3,
          "badge": "Gold",
          "difficulty": "Medium",
          "questions": [
            { "title": "Subarray Sum Equals K", "slug": "subarray-sum-equals-k" },
            { "title": "Next Permutation", "slug": "next-permutation" }
          ]
        },
        {
          "level": 4,
          "badge": "Platinum",
          "difficulty": "Medium/Hard",
          "questions": [
            { "title": "Merge Intervals", "slug": "merge-intervals" },
            { "title": "Trapping Rain Water", "slug": "trapping-rain-water" }
          ]
        },
        {
          "level": 5,
          "badge": "Diamond",
          "difficulty": "Hard",
          "questions": [
            { "title": "First Missing Positive", "slug": "first-missing-positive" },
            { "title": "Median of Two Sorted Arrays", "slug": "median-of-two-sorted-arrays" }
          ]
        }
      ]
    },
    {
      "name": "Strings",
      "badges": [
        {
          "level": 1,
          "badge": "Bronze",
          "difficulty": "Easy",
          "questions": [
            { "title": "Valid Anagram", "slug": "valid-anagram" },
            { "title": "Reverse String", "slug": "reverse-string" }
          ]
        },
        {
          "level": 2,
          "badge": "Silver",
          "difficulty": "Medium",
          "questions": [
            { "title": "Longest Substring Without Repeating Characters", "slug": "longest-substring-without-repeating-characters" },
            { "title": "Group Anagrams", "slug": "group-anagrams" }
          ]
        },
        {
          "level": 3,
          "badge": "Gold",
          "difficulty": "Medium",
          "questions": [
            { "title": "Longest Palindromic Substring", "slug": "longest-palindromic-substring" },
            { "title": "String to Integer (atoi)", "slug": "string-to-integer-atoi" }
          ]
        },
        {
          "level": 4,
          "badge": "Platinum",
          "difficulty": "Medium/Hard",
          "questions": [
            { "title": "Decode Ways", "slug": "decode-ways" },
            { "title": "Minimum Window Substring", "slug": "minimum-window-substring" }
          ]
        },
        {
          "level": 5,
          "badge": "Diamond",
          "difficulty": "Hard",
          "questions": [
            { "title": "Regular Expression Matching", "slug": "regular-expression-matching" },
            { "title": "Wildcard Matching", "slug": "wildcard-matching" }
          ]
        }
      ]
    },
    {
      "name": "Sliding Window & Two Pointers",
      "badges": [
        {
          "level": 1,
          "badge": "Bronze",
          "difficulty": "Easy",
          "questions": [
            { "title": "Valid Palindrome", "slug": "valid-palindrome" },
            { "title": "Contains Duplicate II", "slug": "contains-duplicate-ii" }
          ]
        },
        {
          "level": 2,
          "badge": "Silver",
          "difficulty": "Medium",
          "questions": [
            { "title": "Container With Most Water", "slug": "container-with-most-water" },
            { "title": "Longest Repeating Character Replacement", "slug": "longest-repeating-character-replacement" }
          ]
        },
        {
          "level": 3,
          "badge": "Gold",
          "difficulty": "Medium",
          "questions": [
            { "title": "Permutation in String", "slug": "permutation-in-string" },
            { "title": "Find All Anagrams in a String", "slug": "find-all-anagrams-in-a-string" }
          ]
        },
        {
          "level": 4,
          "badge": "Platinum",
          "difficulty": "Medium/Hard",
          "questions": [
            { "title": "Fruit Into Baskets", "slug": "fruit-into-baskets" },
            { "title": "Sliding Window Maximum", "slug": "sliding-window-maximum" }
          ]
        },
        {
          "level": 5,
          "badge": "Diamond",
          "difficulty": "Hard",
          "questions": [
            { "title": "Substring with Concatenation of All Words", "slug": "substring-with-concatenation-of-all-words" },
            { "title": "Smallest Range Covering Elements from K Lists", "slug": "smallest-range-covering-elements-from-k-lists" }
          ]
        }
      ]
    },
    {
      "name": "Binary Search",
      "badges": [
        {
          "level": 1,
          "badge": "Bronze",
          "difficulty": "Easy",
          "questions": [
            { "title": "Binary Search", "slug": "binary-search" },
            { "title": "Search Insert Position", "slug": "search-insert-position" }
          ]
        },
        {
          "level": 2,
          "badge": "Silver",
          "difficulty": "Medium",
          "questions": [
            { "title": "Search in Rotated Sorted Array", "slug": "search-in-rotated-sorted-array" },
            { "title": "Find First and Last Position of Element in Sorted Array", "slug": "find-first-and-last-position-of-element-in-sorted-array" }
          ]
        },
        {
          "level": 3,
          "badge": "Gold",
          "difficulty": "Medium",
          "questions": [
            { "title": "Find Minimum in Rotated Sorted Array", "slug": "find-minimum-in-rotated-sorted-array" },
            { "title": "Search a 2D Matrix", "slug": "search-a-2d-matrix" }
          ]
        },
        {
          "level": 4,
          "badge": "Platinum",
          "difficulty": "Medium/Hard",
          "questions": [
            { "title": "Koko Eating Bananas", "slug": "koko-eating-bananas" },
            { "title": "Median of Two Sorted Arrays", "slug": "median-of-two-sorted-arrays" }
          ]
        },
        {
          "level": 5,
          "badge": "Diamond",
          "difficulty": "Hard",
          "questions": [
            { "title": "Split Array Largest Sum", "slug": "split-array-largest-sum" },
            { "title": "Find K-th Smallest Pair Distance", "slug": "find-k-th-smallest-pair-distance" }
          ]
        }
      ]
    },
    {
      "name": "Linked List",
      "badges": [
        {
          "level": 1,
          "badge": "Bronze",
          "difficulty": "Easy",
          "questions": [
            { "title": "Reverse Linked List", "slug": "reverse-linked-list" },
            { "title": "Merge Two Sorted Lists", "slug": "merge-two-sorted-lists" }
          ]
        },
        {
          "level": 2,
          "badge": "Silver",
          "difficulty": "Medium",
          "questions": [
            { "title": "Add Two Numbers", "slug": "add-two-numbers" },
            { "title": "Remove Nth Node From End of List", "slug": "remove-nth-node-from-end-of-list" }
          ]
        },
        {
          "level": 3,
          "badge": "Gold",
          "difficulty": "Medium",
          "questions": [
            { "title": "Reorder List", "slug": "reorder-list" },
            { "title": "Linked List Cycle II", "slug": "linked-list-cycle-ii" }
          ]
        },
        {
          "level": 4,
          "badge": "Platinum",
          "difficulty": "Medium/Hard",
          "questions": [
            { "title": "Copy List with Random Pointer", "slug": "copy-list-with-random-pointer" },
            { "title": "Merge k Sorted Lists", "slug": "merge-k-sorted-lists" }
          ]
        },
        {
          "level": 5,
          "badge": "Diamond",
          "difficulty": "Hard",
          "questions": [
            { "title": "Reverse Nodes in k-Group", "slug": "reverse-nodes-in-k-group" },
            { "title": "LFU Cache", "slug": "lfu-cache" }
          ]
        }
      ]
    },
    {
      "name": "Stack & Queue",
      "badges": [
        {
          "level": 1,
          "badge": "Bronze",
          "difficulty": "Easy",
          "questions": [
            { "title": "Valid Parentheses", "slug": "valid-parentheses" },
            { "title": "Implement Queue using Stacks", "slug": "implement-queue-using-stacks" }
          ]
        },
        {
          "level": 2,
          "badge": "Silver",
          "difficulty": "Medium",
          "questions": [
            { "title": "Min Stack", "slug": "min-stack" },
            { "title": "Daily Temperatures", "slug": "daily-temperatures" }
          ]
        },
        {
          "level": 3,
          "badge": "Gold",
          "difficulty": "Medium",
          "questions": [
            { "title": "Evaluate Reverse Polish Notation", "slug": "evaluate-reverse-polish-notation" },
            { "title": "Next Greater Element II", "slug": "next-greater-element-ii" }
          ]
        },
        {
          "level": 4,
          "badge": "Platinum",
          "difficulty": "Medium/Hard",
          "questions": [
            { "title": "Asteroid Collision", "slug": "asteroid-collision" },
            { "title": "Largest Rectangle in Histogram", "slug": "largest-rectangle-in-histogram" }
          ]
        },
        {
          "level": 5,
          "badge": "Diamond",
          "difficulty": "Hard",
          "questions": [
            { "title": "Basic Calculator", "slug": "basic-calculator" },
            { "title": "Maximal Rectangle", "slug": "maximal-rectangle" }
          ]
        }
      ]
    },
    {
      "name": "Hashing",
      "badges": [
        {
          "level": 1,
          "badge": "Bronze",
          "difficulty": "Easy",
          "questions": [
            { "title": "Two Sum", "slug": "two-sum" },
            { "title": "Contains Duplicate", "slug": "contains-duplicate" }
          ]
        },
        {
          "level": 2,
          "badge": "Silver",
          "difficulty": "Medium",
          "questions": [
            { "title": "Top K Frequent Elements", "slug": "top-k-frequent-elements" },
            { "title": "4Sum", "slug": "4sum" }
          ]
        },
        {
          "level": 3,
          "badge": "Gold",
          "difficulty": "Medium",
          "questions": [
            { "title": "Longest Consecutive Sequence", "slug": "longest-consecutive-sequence" },
            { "title": "Insert Delete GetRandom O(1)", "slug": "insert-delete-getrandom-o1" }
          ]
        },
        {
          "level": 4,
          "badge": "Platinum",
          "difficulty": "Medium/Hard",
          "questions": [
            { "title": "LRU Cache", "slug": "lru-cache" },
            { "title": "Max Points on a Line", "slug": "max-points-on-a-line" }
          ]
        },
        {
          "level": 5,
          "badge": "Diamond",
          "difficulty": "Hard",
          "questions": [
            { "title": "Alien Dictionary", "slug": "alien-dictionary" },
            { "title": "Text Justification", "slug": "text-justification" }
          ]
        }
      ]
    },
    {
      "name": "Recursion & Backtracking",
      "badges": [
        {
          "level": 1,
          "badge": "Bronze",
          "difficulty": "Easy",
          "questions": [
            { "title": "Climbing Stairs", "slug": "climbing-stairs" },
            { "title": "Fibonacci Number", "slug": "fibonacci-number" }
          ]
        },
        {
          "level": 2,
          "badge": "Silver",
          "difficulty": "Medium",
          "questions": [
            { "title": "Subsets", "slug": "subsets" },
            { "title": "Permutations", "slug": "permutations" }
          ]
        },
        {
          "level": 3,
          "badge": "Gold",
          "difficulty": "Medium",
          "questions": [
            { "title": "Combination Sum", "slug": "combination-sum" },
            { "title": "Generate Parentheses", "slug": "generate-parentheses" }
          ]
        },
        {
          "level": 4,
          "badge": "Platinum",
          "difficulty": "Medium/Hard",
          "questions": [
            { "title": "Word Search", "slug": "word-search" },
            { "title": "N-Queens", "slug": "n-queens" }
          ]
        },
        {
          "level": 5,
          "badge": "Diamond",
          "difficulty": "Hard",
          "questions": [
            { "title": "Sudoku Solver", "slug": "sudoku-solver" },
            { "title": "Word Break II", "slug": "word-break-ii" }
          ]
        }
      ]
    },
    {
      "name": "Trees & BST",
      "badges": [
        {
          "level": 1,
          "badge": "Bronze",
          "difficulty": "Easy",
          "questions": [
            { "title": "Maximum Depth of Binary Tree", "slug": "maximum-depth-of-binary-tree" },
            { "title": "Same Tree", "slug": "same-tree" }
          ]
        },
        {
          "level": 2,
          "badge": "Silver",
          "difficulty": "Medium",
          "questions": [
            { "title": "Validate Binary Search Tree", "slug": "validate-binary-search-tree" },
            { "title": "Binary Tree Level Order Traversal", "slug": "binary-tree-level-order-traversal" }
          ]
        },
        {
          "level": 3,
          "badge": "Gold",
          "difficulty": "Medium",
          "questions": [
            { "title": "Lowest Common Ancestor of a Binary Search Tree", "slug": "lowest-common-ancestor-of-a-binary-search-tree" },
            { "title": "Kth Smallest Element in a BST", "slug": "kth-smallest-element-in-a-bst" }
          ]
        },
        {
          "level": 4,
          "badge": "Platinum",
          "difficulty": "Medium/Hard",
          "questions": [
            { "title": "Construct Binary Tree from Preorder and Inorder Traversal", "slug": "construct-binary-tree-from-preorder-and-inorder-traversal" },
            { "title": "Binary Tree Maximum Path Sum", "slug": "binary-tree-maximum-path-sum" }
          ]
        },
        {
          "level": 5,
          "badge": "Diamond",
          "difficulty": "Hard",
          "questions": [
            { "title": "Serialize and Deserialize Binary Tree", "slug": "serialize-and-deserialize-binary-tree" },
            { "title": "Binary Tree Cameras", "slug": "binary-tree-cameras" }
          ]
        }
      ]
    },
    {
      "name": "Heaps / Priority Queue",
      "badges": [
        {
          "level": 1,
          "badge": "Bronze",
          "difficulty": "Easy",
          "questions": [
            { "title": "Kth Largest Element in a Stream", "slug": "kth-largest-element-in-a-stream" },
            { "title": "Last Stone Weight", "slug": "last-stone-weight" }
          ]
        },
        {
          "level": 2,
          "badge": "Silver",
          "difficulty": "Medium",
          "questions": [
            { "title": "Kth Largest Element in an Array", "slug": "kth-largest-element-in-an-array" },
            { "title": "K Closest Points to Origin", "slug": "k-closest-points-to-origin" }
          ]
        },
        {
          "level": 3,
          "badge": "Gold",
          "difficulty": "Medium",
          "questions": [
            { "title": "Task Scheduler", "slug": "task-scheduler" },
            { "title": "Reorganize String", "slug": "reorganize-string" }
          ]
        },
        {
          "level": 4,
          "badge": "Platinum",
          "difficulty": "Medium/Hard",
          "questions": [
            { "title": "IPO", "slug": "ipo" },
            { "title": "Find Median from Data Stream", "slug": "find-median-from-data-stream" }
          ]
        },
        {
          "level": 5,
          "badge": "Diamond",
          "difficulty": "Hard",
          "questions": [
            { "title": "Smallest Range Covering Elements from K Lists", "slug": "smallest-range-covering-elements-from-k-lists" },
            { "title": "Maximum Performance of a Team", "slug": "maximum-performance-of-a-team" }
          ]
        }
      ]
    },
    {
      "name": "Graphs",
      "badges": [
        {
          "level": 1,
          "badge": "Bronze",
          "difficulty": "Easy",
          "questions": [
            { "title": "Find if Path Exists in Graph", "slug": "find-if-path-exists-in-graph" },
            { "title": "Flood Fill", "slug": "flood-fill" }
          ]
        },
        {
          "level": 2,
          "badge": "Silver",
          "difficulty": "Medium",
          "questions": [
            { "title": "Number of Islands", "slug": "number-of-islands" },
            { "title": "Clone Graph", "slug": "clone-graph" }
          ]
        },
        {
          "level": 3,
          "badge": "Gold",
          "difficulty": "Medium",
          "questions": [
            { "title": "Course Schedule", "slug": "course-schedule" },
            { "title": "Pacific Atlantic Water Flow", "slug": "pacific-atlantic-water-flow" }
          ]
        },
        {
          "level": 4,
          "badge": "Platinum",
          "difficulty": "Medium/Hard",
          "questions": [
            { "title": "Course Schedule II", "slug": "course-schedule-ii" },
            { "title": "Word Ladder", "slug": "word-ladder" }
          ]
        },
        {
          "level": 5,
          "badge": "Diamond",
          "difficulty": "Hard",
          "questions": [
            { "title": "Swim in Rising Water", "slug": "swim-in-rising-water" },
            { "title": "Reconstruct Itinerary", "slug": "reconstruct-itinerary" }
          ]
        }
      ]
    },
    {
      "name": "Dynamic Programming",
      "badges": [
        {
          "level": 1,
          "badge": "Bronze",
          "difficulty": "Easy",
          "questions": [
            { "title": "House Robber", "slug": "house-robber" },
            { "title": "Maximum Subarray", "slug": "maximum-subarray" }
          ]
        },
        {
          "level": 2,
          "badge": "Silver",
          "difficulty": "Medium",
          "questions": [
            { "title": "Coin Change", "slug": "coin-change" },
            { "title": "Longest Increasing Subsequence", "slug": "longest-increasing-subsequence" }
          ]
        },
        {
          "level": 3,
          "badge": "Gold",
          "difficulty": "Medium",
          "questions": [
            { "title": "Unique Paths", "slug": "unique-paths" },
            { "title": "Word Break", "slug": "word-break" }
          ]
        },
        {
          "level": 4,
          "badge": "Platinum",
          "difficulty": "Medium/Hard",
          "questions": [
            { "title": "Longest Common Subsequence", "slug": "longest-common-subsequence" },
            { "title": "Palindrome Partitioning II", "slug": "palindrome-partitioning-ii" }
          ]
        },
        {
          "level": 5,
          "badge": "Diamond",
          "difficulty": "Hard",
          "questions": [
            { "title": "Burst Balloons", "slug": "burst-balloons" },
            { "title": "Distinct Subsequences", "slug": "distinct-subsequences" }
          ]
        }
      ]
    },
    {
      "name": "Greedy",
      "badges": [
        {
          "level": 1,
          "badge": "Bronze",
          "difficulty": "Easy",
          "questions": [
            { "title": "Assign Cookies", "slug": "assign-cookies" },
            { "title": "Lemonade Change", "slug": "lemonade-change" }
          ]
        },
        {
          "level": 2,
          "badge": "Silver",
          "difficulty": "Medium",
          "questions": [
            { "title": "Jump Game", "slug": "jump-game" },
            { "title": "Gas Station", "slug": "gas-station" }
          ]
        },
        {
          "level": 3,
          "badge": "Gold",
          "difficulty": "Medium",
          "questions": [
            { "title": "Jump Game II", "slug": "jump-game-ii" },
            { "title": "Partition Labels", "slug": "partition-labels" }
          ]
        },
        {
          "level": 4,
          "badge": "Platinum",
          "difficulty": "Medium/Hard",
          "questions": [
            { "title": "Queue Reconstruction by Height", "slug": "queue-reconstruction-by-height" },
            { "title": "Candy", "slug": "candy" }
          ]
        },
        {
          "level": 5,
          "badge": "Diamond",
          "difficulty": "Hard",
          "questions": [
            { "title": "Create Maximum Number", "slug": "create-maximum-number" },
            { "title": "Split Array into Consecutive Subsequences", "slug": "split-array-into-consecutive-subsequences" }
          ]
        }
      ]
    },
    {
      "name": "Trie & Bit Manipulation",
      "badges": [
        {
          "level": 1,
          "badge": "Bronze",
          "difficulty": "Easy",
          "questions": [
            { "title": "Implement Trie (Prefix Tree)", "slug": "implement-trie-prefix-tree" },
            { "title": "Single Number", "slug": "single-number" }
          ]
        },
        {
          "level": 2,
          "badge": "Silver",
          "difficulty": "Medium",
          "questions": [
            { "title": "Design Add and Search Words Data Structure", "slug": "design-add-and-search-words-data-structure" },
            { "title": "Counting Bits", "slug": "counting-bits" }
          ]
        },
        {
          "level": 3,
          "badge": "Gold",
          "difficulty": "Medium",
          "questions": [
            { "title": "Map Sum Pairs", "slug": "map-sum-pairs" },
            { "title": "Maximum XOR of Two Numbers in an Array", "slug": "maximum-xor-of-two-numbers-in-an-array" }
          ]
        },
        {
          "level": 4,
          "badge": "Platinum",
          "difficulty": "Medium/Hard",
          "questions": [
            { "title": "Word Search II", "slug": "word-search-ii" },
            { "title": "Concatenated Words", "slug": "concatenated-words" }
          ]
        },
        {
          "level": 5,
          "badge": "Diamond",
          "difficulty": "Hard",
          "questions": [
            { "title": "Palindrome Pairs", "slug": "palindrome-pairs" },
            { "title": "Design Search Autocomplete System", "slug": "design-search-autocomplete-system" }
          ]
        }
      ]
    }
  ]
}

COMPANIES_DATA = {
  "companies": [
    {
      "name": "Google",
      "questions": [
        { "title": "LRU Cache", "slug": "lru-cache", "difficulty": "Medium" },
        { "title": "Word Search II", "slug": "word-search-ii", "difficulty": "Hard" },
        { "title": "Merge Intervals", "slug": "merge-intervals", "difficulty": "Medium" }
      ]
    },
    {
      "name": "Amazon",
      "questions": [
        { "title": "Two Sum", "slug": "two-sum", "difficulty": "Easy" },
        { "title": "Number of Islands", "slug": "number-of-islands", "difficulty": "Medium" },
        { "title": "Trapping Rain Water", "slug": "trapping-rain-water", "difficulty": "Hard" }
      ]
    },
    {
      "name": "Microsoft",
      "questions": [
        { "title": "Reverse Linked List", "slug": "reverse-linked-list", "difficulty": "Easy" },
        { "title": "Copy List with Random Pointer", "slug": "copy-list-with-random-pointer", "difficulty": "Medium" },
        { "title": "Serialize and Deserialize Binary Tree", "slug": "serialize-and-deserialize-binary-tree", "difficulty": "Hard" }
      ]
    },
    {
      "name": "Meta",
      "questions": [
        { "title": "Valid Palindrome II", "slug": "valid-palindrome-ii", "difficulty": "Easy" },
        { "title": "Merge Intervals", "slug": "merge-intervals", "difficulty": "Medium" },
        { "title": "Binary Tree Maximum Path Sum", "slug": "binary-tree-maximum-path-sum", "difficulty": "Hard" }
      ]
    },
    {
      "name": "Apple",
      "questions": [
        { "title": "Merge Two Sorted Lists", "slug": "merge-two-sorted-lists", "difficulty": "Easy" },
        { "title": "Kth Largest Element in an Array", "slug": "kth-largest-element-in-an-array", "difficulty": "Medium" },
        { "title": "Design Circular Queue", "slug": "design-circular-queue", "difficulty": "Medium" }
      ]
    },
    {
      "name": "Adobe",
      "questions": [
        { "title": "Word Break", "slug": "word-break", "difficulty": "Medium" },
        { "title": "Lowest Common Ancestor of a Binary Tree", "slug": "lowest-common-ancestor-of-a-binary-tree", "difficulty": "Medium" },
        { "title": "Trapping Rain Water", "slug": "trapping-rain-water", "difficulty": "Hard" }
      ]
    },
    {
      "name": "Uber",
      "questions": [
        { "title": "Meeting Rooms II", "slug": "meeting-rooms-ii", "difficulty": "Medium" },
        { "title": "Number of Islands", "slug": "number-of-islands", "difficulty": "Medium" },
        { "title": "Course Schedule", "slug": "course-schedule", "difficulty": "Medium" }
      ]
    },
    {
      "name": "Flipkart",
      "questions": [
        { "title": "Two Sum", "slug": "two-sum", "difficulty": "Easy" },
        { "title": "Rotate Array", "slug": "rotate-array", "difficulty": "Medium" },
        { "title": "Longest Palindromic Substring", "slug": "longest-palindromic-substring", "difficulty": "Medium" }
      ]
    },
    {
      "name": "Goldman Sachs",
      "questions": [
        { "title": "Search in Rotated Sorted Array", "slug": "search-in-rotated-sorted-array", "difficulty": "Medium" },
        { "title": "Merge Intervals", "slug": "merge-intervals", "difficulty": "Medium" },
        { "title": "Longest Common Subsequence", "slug": "longest-common-subsequence", "difficulty": "Medium" }
      ]
    },
    {
      "name": "Atlassian",
      "questions": [
        { "title": "Group Anagrams", "slug": "group-anagrams", "difficulty": "Medium" },
        { "title": "Course Schedule II", "slug": "course-schedule-ii", "difficulty": "Medium" },
        { "title": "Design Add and Search Words Data Structure", "slug": "design-add-and-search-words-data-structure", "difficulty": "Medium" }
      ]
    },
    {
      "name": "Salesforce",
      "questions": [
        { "title": "Valid Parentheses", "slug": "valid-parentheses", "difficulty": "Easy" },
        { "title": "Clone Graph", "slug": "clone-graph", "difficulty": "Medium" },
        { "title": "Word Ladder", "slug": "word-ladder", "difficulty": "Hard" }
      ]
    },
    {
      "name": "Walmart Labs",
      "questions": [
        { "title": "Linked List Cycle", "slug": "linked-list-cycle", "difficulty": "Easy" },
        { "title": "Subarray Sum Equals K", "slug": "subarray-sum-equals-k", "difficulty": "Medium" },
        { "title": "Top K Frequent Elements", "slug": "top-k-frequent-elements", "difficulty": "Medium" }
      ]
    },
    {
      "name": "Sabre",
      "focus_note": "Travel/booking-systems SDE round proxy, not confirmed company-tagged data",
      "questions": [
        { "title": "Two Sum", "slug": "two-sum", "difficulty": "Easy" },
        { "title": "Meeting Rooms II", "slug": "meeting-rooms-ii", "difficulty": "Medium" },
        { "title": "LRU Cache", "slug": "lru-cache", "difficulty": "Medium" }
      ]
    },
    {
      "name": "Couchbase",
      "focus_note": "Distributed-systems/QE round proxy, not confirmed company-tagged data",
      "questions": [
        { "title": "Implement Trie (Prefix Tree)", "slug": "implement-trie-prefix-tree", "difficulty": "Medium" },
        { "title": "Design Hit Counter", "slug": "design-hit-counter", "difficulty": "Medium" },
        { "title": "LRU Cache", "slug": "lru-cache", "difficulty": "Medium" }
      ]
    },
    {
      "name": "Oracle",
      "questions": [
        { "title": "Binary Search", "slug": "binary-search", "difficulty": "Easy" },
        { "title": "Add Two Numbers", "slug": "add-two-numbers", "difficulty": "Medium" },
        { "title": "Longest Substring Without Repeating Characters", "slug": "longest-substring-without-repeating-characters", "difficulty": "Medium" }
      ]
    },
    {
      "name": "Cisco",
      "questions": [
        { "title": "Rotting Oranges", "slug": "rotting-oranges", "difficulty": "Medium" },
        { "title": "Design Circular Queue", "slug": "design-circular-queue", "difficulty": "Medium" },
        { "title": "Network Delay Time", "slug": "network-delay-time", "difficulty": "Medium" }
      ]
    },
    {
      "name": "Intuit",
      "questions": [
        { "title": "Product of Array Except Self", "slug": "product-of-array-except-self", "difficulty": "Medium" },
        { "title": "Coin Change", "slug": "coin-change", "difficulty": "Medium" },
        { "title": "Minimum Window Substring", "slug": "minimum-window-substring", "difficulty": "Hard" }
      ]
    },
    {
      "name": "ServiceNow",
      "questions": [
        { "title": "Design Hit Counter", "slug": "design-hit-counter", "difficulty": "Medium" },
        { "title": "Task Scheduler", "slug": "task-scheduler", "difficulty": "Medium" },
        { "title": "Course Schedule", "slug": "course-schedule", "difficulty": "Medium" },
        { "title": "Number of Islands", "slug": "number-of-islands", "difficulty": "Medium" },
        { "title": "LRU Cache", "slug": "lru-cache", "difficulty": "Medium" },
        { "title": "Valid Parentheses", "slug": "valid-parentheses", "difficulty": "Easy" },
        { "title": "Two Sum", "slug": "two-sum", "difficulty": "Easy" }
      ]
    },
    {
      "name": "PayPal",
      "questions": [
        { "title": "Two Sum", "slug": "two-sum", "difficulty": "Easy" },
        { "title": "Best Time to Buy and Sell Stock", "slug": "best-time-to-buy-and-sell-stock", "difficulty": "Easy" },
        { "title": "Design Underground System", "slug": "design-underground-system", "difficulty": "Medium" },
        { "title": "Longest Substring Without Repeating Characters", "slug": "longest-substring-without-repeating-characters", "difficulty": "Medium" },
        { "title": "Merge Two Sorted Lists", "slug": "merge-two-sorted-lists", "difficulty": "Easy" },
        { "title": "Valid Parentheses", "slug": "valid-parentheses", "difficulty": "Easy" },
        { "title": "Reverse Linked List", "slug": "reverse-linked-list", "difficulty": "Easy" },
        { "title": "Coin Change", "slug": "coin-change", "difficulty": "Medium" }
      ]
    },
    {
      "name": "VMware",
      "questions": [
        { "title": "Merge k Sorted Lists", "slug": "merge-k-sorted-lists", "difficulty": "Hard" },
        { "title": "Design Circular Deque", "slug": "design-circular-deque", "difficulty": "Medium" },
        { "title": "Number of Connected Components in an Undirected Graph", "slug": "number-of-connected-components-in-an-undirected-graph", "difficulty": "Medium" },
        { "title": "Course Schedule", "slug": "course-schedule", "difficulty": "Medium" },
        { "title": "LRU Cache", "slug": "lru-cache", "difficulty": "Medium" },
        { "title": "Number of Islands", "slug": "number-of-islands", "difficulty": "Medium" }
      ]
    },
    {
      "name": "Qualcomm",
      "questions": [
        { "title": "Reverse Bits", "slug": "reverse-bits", "difficulty": "Easy" },
        { "title": "Single Number", "slug": "single-number", "difficulty": "Easy" },
        { "title": "Sliding Window Maximum", "slug": "sliding-window-maximum", "difficulty": "Hard" },
        { "title": "Counting Bits", "slug": "counting-bits", "difficulty": "Easy" },
        { "title": "Rotate Image", "slug": "rotate-image", "difficulty": "Medium" },
        { "title": "Power of Two", "slug": "power-of-two", "difficulty": "Easy" }
      ]
    },
    {
      "name": "Samsung",
      "questions": [
        { "title": "Rotate Image", "slug": "rotate-image", "difficulty": "Medium" },
        { "title": "Spiral Matrix", "slug": "spiral-matrix", "difficulty": "Medium" },
        { "title": "Set Matrix Zeroes", "slug": "set-matrix-zeroes", "difficulty": "Medium" },
        { "title": "Word Search", "slug": "word-search", "difficulty": "Medium" },
        { "title": "Number of Islands", "slug": "number-of-islands", "difficulty": "Medium" }
      ]
    },
    {
      "name": "Zoho",
      "focus_note": "Freshers-round pattern proxy, common data structure and string questions",
      "questions": [
        { "title": "Valid Anagram", "slug": "valid-anagram", "difficulty": "Easy" },
        { "title": "Reverse Words in a String", "slug": "reverse-words-in-a-string", "difficulty": "Medium" },
        { "title": "Implement Stack using Queues", "slug": "implement-stack-using-queues", "difficulty": "Easy" },
        { "title": "Two Sum", "slug": "two-sum", "difficulty": "Easy" },
        { "title": "Remove Duplicates from Sorted Array", "slug": "remove-duplicates-from-sorted-array", "difficulty": "Easy" },
        { "title": "Move Zeroes", "slug": "move-zeroes", "difficulty": "Easy" },
        { "title": "Valid Parentheses", "slug": "valid-parentheses", "difficulty": "Easy" },
        { "title": "Reverse Linked List", "slug": "reverse-linked-list", "difficulty": "Easy" },
        { "title": "Longest Common Prefix", "slug": "longest-common-prefix", "difficulty": "Easy" },
        { "title": "Sort Colors", "slug": "sort-colors", "difficulty": "Medium" }
      ]
    },
    {
      "name": "Freshworks",
      "focus_note": "SDE-1 freshers round proxy, not confirmed company-tagged data",
      "questions": [
        { "title": "Group Anagrams", "slug": "group-anagrams", "difficulty": "Medium" },
        { "title": "Longest Consecutive Sequence", "slug": "longest-consecutive-sequence", "difficulty": "Medium" },
        { "title": "Word Break", "slug": "word-break", "difficulty": "Medium" },
        { "title": "Valid Anagram", "slug": "valid-anagram", "difficulty": "Easy" },
        { "title": "Two Sum", "slug": "two-sum", "difficulty": "Easy" },
        { "title": "Merge Intervals", "slug": "merge-intervals", "difficulty": "Medium" },
        { "title": "Top K Frequent Elements", "slug": "top-k-frequent-elements", "difficulty": "Medium" }
      ]
    },
    {
      "name": "Swiggy",
      "focus_note": "SDE freshers round proxy, not confirmed company-tagged data",
      "questions": [
        { "title": "Design Twitter", "slug": "design-twitter", "difficulty": "Medium" },
        { "title": "K Closest Points to Origin", "slug": "k-closest-points-to-origin", "difficulty": "Medium" },
        { "title": "LRU Cache", "slug": "lru-cache", "difficulty": "Medium" },
        { "title": "Merge Intervals", "slug": "merge-intervals", "difficulty": "Medium" },
        { "title": "Top K Frequent Elements", "slug": "top-k-frequent-elements", "difficulty": "Medium" },
        { "title": "Course Schedule", "slug": "course-schedule", "difficulty": "Medium" },
        { "title": "Subarray Sum Equals K", "slug": "subarray-sum-equals-k", "difficulty": "Medium" }
      ]
    },
    {
      "name": "Zomato",
      "focus_note": "SDE freshers round proxy, not confirmed company-tagged data",
      "questions": [
        { "title": "Find Median from Data Stream", "slug": "find-median-from-data-stream", "difficulty": "Hard" },
        { "title": "Minimum Cost to Connect Sticks", "slug": "minimum-cost-to-connect-sticks", "difficulty": "Medium" },
        { "title": "Subarray Sum Equals K", "slug": "subarray-sum-equals-k", "difficulty": "Medium" },
        { "title": "LRU Cache", "slug": "lru-cache", "difficulty": "Medium" },
        { "title": "Top K Frequent Elements", "slug": "top-k-frequent-elements", "difficulty": "Medium" },
        { "title": "Two Sum", "slug": "two-sum", "difficulty": "Easy" }
      ]
    },
    {
      "name": "Paytm",
      "questions": [
        { "title": "Two Sum", "slug": "two-sum", "difficulty": "Easy" },
        { "title": "Longest Substring Without Repeating Characters", "slug": "longest-substring-without-repeating-characters", "difficulty": "Medium" },
        { "title": "Coin Change", "slug": "coin-change", "difficulty": "Medium" },
        { "title": "Maximum Subarray", "slug": "maximum-subarray", "difficulty": "Medium" },
        { "title": "3Sum", "slug": "3sum", "difficulty": "Medium" },
        { "title": "Merge Intervals", "slug": "merge-intervals", "difficulty": "Medium" },
        { "title": "Reverse Linked List", "slug": "reverse-linked-list", "difficulty": "Easy" },
        { "title": "Valid Parentheses", "slug": "valid-parentheses", "difficulty": "Easy" }
      ]
    },
    {
      "name": "PhonePe",
      "focus_note": "SDE freshers/off-campus round proxy, not confirmed company-tagged data",
      "questions": [
        { "title": "3Sum", "slug": "3sum", "difficulty": "Medium" },
        { "title": "Merge Intervals", "slug": "merge-intervals", "difficulty": "Medium" },
        { "title": "Word Ladder", "slug": "word-ladder", "difficulty": "Hard" },
        { "title": "Subarray Sum Equals K", "slug": "subarray-sum-equals-k", "difficulty": "Medium" },
        { "title": "Top K Frequent Elements", "slug": "top-k-frequent-elements", "difficulty": "Medium" },
        { "title": "Course Schedule", "slug": "course-schedule", "difficulty": "Medium" },
        { "title": "LRU Cache", "slug": "lru-cache", "difficulty": "Medium" },
        { "title": "Two Sum", "slug": "two-sum", "difficulty": "Easy" }
      ]
    },
    {
      "name": "Razorpay",
      "focus_note": "SDE round proxy, not confirmed company-tagged data",
      "questions": [
        { "title": "Design Parking System", "slug": "design-parking-system", "difficulty": "Easy" },
        { "title": "Top K Frequent Elements", "slug": "top-k-frequent-elements", "difficulty": "Medium" },
        { "title": "Course Schedule II", "slug": "course-schedule-ii", "difficulty": "Medium" },
        { "title": "LRU Cache", "slug": "lru-cache", "difficulty": "Medium" },
        { "title": "Two Sum", "slug": "two-sum", "difficulty": "Easy" },
        { "title": "Merge Intervals", "slug": "merge-intervals", "difficulty": "Medium" }
      ]
    },
    {
      "name": "LinkedIn",
      "questions": [
        { "title": "Random Pick with Weight", "slug": "random-pick-with-weight", "difficulty": "Medium" },
        { "title": "Insert Delete GetRandom O(1)", "slug": "insert-delete-getrandom-o1", "difficulty": "Medium" },
        { "title": "Alien Dictionary", "slug": "alien-dictionary", "difficulty": "Hard" },
        { "title": "Two Sum", "slug": "two-sum", "difficulty": "Easy" },
        { "title": "Max Points on a Line", "slug": "max-points-on-a-line", "difficulty": "Hard" }
      ]
    },
    {
      "name": "Bloomberg",
      "questions": [
        { "title": "Valid Parentheses", "slug": "valid-parentheses", "difficulty": "Easy" },
        { "title": "K Closest Points to Origin", "slug": "k-closest-points-to-origin", "difficulty": "Medium" },
        { "title": "Time Based Key-Value Store", "slug": "time-based-key-value-store", "difficulty": "Medium" },
        { "title": "LRU Cache", "slug": "lru-cache", "difficulty": "Medium" },
        { "title": "Two Sum", "slug": "two-sum", "difficulty": "Easy" },
        { "title": "Two City Scheduling", "slug": "two-city-scheduling", "difficulty": "Medium" }
      ]
    },
    {
      "name": "Nutanix",
      "focus_note": "SDE freshers round proxy, not confirmed company-tagged data",
      "questions": [
        { "title": "Design Circular Queue", "slug": "design-circular-queue", "difficulty": "Medium" },
        { "title": "LFU Cache", "slug": "lfu-cache", "difficulty": "Hard" },
        { "title": "Number of Islands", "slug": "number-of-islands", "difficulty": "Medium" },
        { "title": "Course Schedule", "slug": "course-schedule", "difficulty": "Medium" },
        { "title": "LRU Cache", "slug": "lru-cache", "difficulty": "Medium" }
      ]
    },
    {
      "name": "Intel",
      "focus_note": "SDE freshers round proxy, not confirmed company-tagged data",
      "questions": [
        { "title": "Reverse Integer", "slug": "reverse-integer", "difficulty": "Medium" },
        { "title": "Counting Bits", "slug": "counting-bits", "difficulty": "Easy" },
        { "title": "Maximum Subarray", "slug": "maximum-subarray", "difficulty": "Medium" },
        { "title": "Single Number", "slug": "single-number", "difficulty": "Easy" },
        { "title": "Reverse Bits", "slug": "reverse-bits", "difficulty": "Easy" }
      ]
    },
    {
      "name": "TCS Digital",
      "focus_note": "Off-campus/campus digital hiring round proxy, common patterns not confirmed company-tagged data",
      "questions": [
        { "title": "Two Sum", "slug": "two-sum", "difficulty": "Easy" },
        { "title": "Merge Two Sorted Lists", "slug": "merge-two-sorted-lists", "difficulty": "Easy" },
        { "title": "Longest Palindromic Substring", "slug": "longest-palindromic-substring", "difficulty": "Medium" },
        { "title": "Valid Palindrome", "slug": "valid-palindrome", "difficulty": "Easy" },
        { "title": "Reverse String", "slug": "reverse-string", "difficulty": "Easy" },
        { "title": "Valid Anagram", "slug": "valid-anagram", "difficulty": "Easy" },
        { "title": "Climbing Stairs", "slug": "climbing-stairs", "difficulty": "Easy" },
        { "title": "Maximum Subarray", "slug": "maximum-subarray", "difficulty": "Medium" },
        { "title": "Best Time to Buy and Sell Stock", "slug": "best-time-to-buy-and-sell-stock", "difficulty": "Easy" },
        { "title": "Valid Parentheses", "slug": "valid-parentheses", "difficulty": "Easy" },
        { "title": "Linked List Cycle", "slug": "linked-list-cycle", "difficulty": "Easy" },
        { "title": "Longest Common Prefix", "slug": "longest-common-prefix", "difficulty": "Easy" },
        { "title": "Remove Duplicates from Sorted Array", "slug": "remove-duplicates-from-sorted-array", "difficulty": "Easy" },
        { "title": "Move Zeroes", "slug": "move-zeroes", "difficulty": "Easy" },
        { "title": "Single Number", "slug": "single-number", "difficulty": "Easy" },
        { "title": "Majority Element", "slug": "majority-element", "difficulty": "Easy" },
        { "title": "3Sum", "slug": "3sum", "difficulty": "Medium" },
        { "title": "Container With Most Water", "slug": "container-with-most-water", "difficulty": "Medium" },
        { "title": "Product of Array Except Self", "slug": "product-of-array-except-self", "difficulty": "Medium" },
        { "title": "Group Anagrams", "slug": "group-anagrams", "difficulty": "Medium" },
        { "title": "Coin Change", "slug": "coin-change", "difficulty": "Medium" },
        { "title": "Longest Substring Without Repeating Characters", "slug": "longest-substring-without-repeating-characters", "difficulty": "Medium" },
        { "title": "Search in Rotated Sorted Array", "slug": "search-in-rotated-sorted-array", "difficulty": "Medium" },
        { "title": "Sort Colors", "slug": "sort-colors", "difficulty": "Medium" },
        { "title": "Rotate Image", "slug": "rotate-image", "difficulty": "Medium" },
        { "title": "Spiral Matrix", "slug": "spiral-matrix", "difficulty": "Medium" },
        { "title": "House Robber", "slug": "house-robber", "difficulty": "Medium" },
        { "title": "Word Break", "slug": "word-break", "difficulty": "Medium" }
      ]
    },
    {
      "name": "Cognizant",
      "focus_note": "Campus GenC round proxy, common patterns not confirmed company-tagged data",
      "questions": [
        { "title": "Valid Anagram", "slug": "valid-anagram", "difficulty": "Easy" },
        { "title": "Reverse Linked List", "slug": "reverse-linked-list", "difficulty": "Easy" },
        { "title": "Maximum Depth of Binary Tree", "slug": "maximum-depth-of-binary-tree", "difficulty": "Easy" },
        { "title": "Two Sum", "slug": "two-sum", "difficulty": "Easy" },
        { "title": "Climbing Stairs", "slug": "climbing-stairs", "difficulty": "Easy" },
        { "title": "Valid Palindrome", "slug": "valid-palindrome", "difficulty": "Easy" },
        { "title": "Reverse String", "slug": "reverse-string", "difficulty": "Easy" },
        { "title": "Merge Two Sorted Lists", "slug": "merge-two-sorted-lists", "difficulty": "Easy" },
        { "title": "Valid Parentheses", "slug": "valid-parentheses", "difficulty": "Easy" },
        { "title": "Linked List Cycle", "slug": "linked-list-cycle", "difficulty": "Easy" }
      ]
    }
  ]
}

def get_company_slug(name):
    mapping = {
        "Meta": "meta",
        "Goldman Sachs": "goldman-sachs",
        "Walmart Labs": "walmart-labs",
        "TCS Digital": "tcs",
    }
    if name in mapping:
        return mapping[name]
    return name.lower().replace(" ", "-")

def fetch_company_csv_from_github(company_slug):
    url = f"https://raw.githubusercontent.com/snehasishroy/leetcode-companywise-interview-questions/master/{company_slug}/all.csv"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"[Info] GitHub fetch skipped for {company_slug}: {e}")
        return None

def parse_company_csv(csv_data):
    # CSV fields: ID,URL,Title,Difficulty,Acceptance %,Frequency %,Is Premium
    f = io.StringIO(csv_data)
    reader = csv.DictReader(f)
    questions = []
    for row in reader:
        url = row.get('URL', '').strip()
        slug = url.split('/')[-1] if url else None
        if not slug:
            slug = row.get('Title', '').lower().replace(' ', '-')
        
        difficulty = row.get('Difficulty', 'Medium').strip()
        if difficulty not in ["Easy", "Medium", "Hard"]:
            difficulty = "Medium"

        is_prem_raw = str(row.get('Is Premium', row.get('Paid Only', row.get('is_paid_only', row.get('Is Paid', ''))))).strip().lower()
        is_premium = is_prem_raw in ['1', 'true', 'yes', 'y']

        questions.append({
            'slug': slug.strip(),
            'title': row.get('Title', '').strip(),
            'difficulty': difficulty,
            'url': url if url else f"https://leetcode.com/problems/{slug}/",
            'is_premium': is_premium
        })
    return questions

def seed_db():
    print("Clearing tables for fresh re-seed...")
    db = SessionLocal()
    try:
        # Delete dependent tables first to avoid FK constraints
        db.query(MockInterviewSession).delete()
        db.query(SpacedRepetition).delete()
        db.query(Attempt).delete()
        db.query(BadgeTest).delete()
        db.query(TopicMastery).delete()
        db.query(DailyActivity).delete()
        db.query(CompanyMetadata).delete()
        db.query(Problem).delete()
        db.commit()
        print("Existing data cleaned successfully!")

        # 1. Parse base problems from the 14-topic JSON data structure
        problems_dict = {}
        unique_topics = set()
        
        for topic in SEED_DATA["topics"]:
            topic_name = topic["name"]
            unique_topics.add(topic_name)
            
            for badge in topic["badges"]:
                level = badge["level"]
                for idx, q in enumerate(badge["questions"]):
                    slug = q["slug"]
                    title = q["title"]
                    
                    # Map level & order to appropriate DB difficulty
                    if level == 1:
                        assigned_diff = "Easy"
                    elif level in [2, 3]:
                        assigned_diff = "Medium"
                    elif level == 5:
                        assigned_diff = "Hard"
                    elif level == 4:
                        assigned_diff = "Medium" if idx == 0 else "Hard"
                    else:
                        assigned_diff = "Medium"
                    
                    if slug not in problems_dict:
                        problems_dict[slug] = {
                            "id": slug,
                            "title": title,
                            "url": f"https://leetcode.com/problems/{slug}/",
                            "difficulty": assigned_diff,
                            "topics": {topic_name},
                            "companies": set(),
                            "is_premium": q.get("is_premium", False)
                        }
                    else:
                        problems_dict[slug]["topics"].add(topic_name)

        print(f"Parsed {len(problems_dict)} unique base topic problems.")

        # 2. Add Company Metadata and fetch dynamic GitHub questions
        print("Processing company-specific questions (GitHub fetch & local fallback)...")
        for comp in COMPANIES_DATA["companies"]:
            comp_name = comp["name"]
            focus_note = comp.get("focus_note")
            
            # Save focus note metadata
            meta = CompanyMetadata(name=comp_name, focus_note=focus_note)
            db.add(meta)

            # Try to fetch additional questions from GitHub repo
            slug = get_company_slug(comp_name)
            csv_data = fetch_company_csv_from_github(slug)
            questions_to_load = []

            if csv_data:
                try:
                    questions_to_load = parse_company_csv(csv_data)
                    print(f" -> Fetched {len(questions_to_load)} questions from GitHub for {comp_name}")
                except Exception as ex:
                    print(f" -> Error parsing CSV for {comp_name}, falling back: {ex}")
                    csv_data = None

            if not csv_data:
                # Fallback to local hardcoded questions list
                for q in comp["questions"]:
                    questions_to_load.append({
                        'slug': q['slug'],
                        'title': q['title'],
                        'difficulty': q['difficulty'],
                        'url': f"https://leetcode.com/problems/{q['slug']}/",
                        'is_premium': q.get('is_premium', False)
                    })
                print(f" -> Using local fallback list ({len(questions_to_load)} questions) for {comp_name}")

            # Register questions into problems dict
            for q_data in questions_to_load:
                q_slug = q_data['slug']
                if q_slug in problems_dict:
                    problems_dict[q_slug]["companies"].add(comp_name)
                    if q_data.get('is_premium'):
                        problems_dict[q_slug]["is_premium"] = True
                else:
                    problems_dict[q_slug] = {
                        "id": q_slug,
                        "title": q_data['title'],
                        "url": q_data['url'],
                        "difficulty": q_data['difficulty'],
                        "topics": {"Company Practice"},
                        "companies": {comp_name},
                        "is_premium": q_data.get('is_premium', False)
                    }

        # Seed Problems
        print("Inserting problems into database...")
        for p_id, p_data in problems_dict.items():
            prob = Problem(
                id=p_id,
                title=p_data["title"],
                url=p_data["url"],
                difficulty=p_data["difficulty"],
                topics=",".join(sorted(list(p_data["topics"]))),
                companies=",".join(sorted(list(p_data["companies"]))) if p_data["companies"] else None,
                is_premium=p_data.get("is_premium", False)
            )
            db.add(prob)

        # Seed TopicMastery for 14 main topics
        print("Inserting topic mastery records...")
        for topic_name in sorted(list(unique_topics)):
            mastery = TopicMastery(
                topic=topic_name,
                rating=1200.0,
                attempts_count=0,
                success_count=0,
                level=0
            )
            db.add(mastery)

        # Seed "Company Practice" mastery so it renders if needed
        company_practice_mastery = TopicMastery(
            topic="Company Practice",
            rating=1200.0,
            attempts_count=0,
            success_count=0,
            level=0
        )
        db.add(company_practice_mastery)

        db.commit()
        print("Database seeding completed successfully!")
    except Exception as e:
        db.rollback()
        print(f"Error during database seeding: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_db()
