# 🧠 DSA Tutor Agent — Autonomous LeetCode Companion

> An intelligent, autonomous Data Structures & Algorithms (DSA) tutor overlay for LeetCode. Features conceptual failure diagnostics, Elo-based topic mastery scoring, progressive hint revealing, timed mock interviews, spaced repetition reviews, and real-time interactive Code Coaching.

---

## 🌟 Key Features

### 🎯 1. Conceptual Failure Diagnostics (AI Agent Layer)
- **Automatic Submission Interception**: Listens to LeetCode submission verdicts in real time (Wrong Answer, Time Limit Exceeded, Runtime Error, Compile Error).
- **LLM Root-Cause Classification**: Automatically classifies failures into exact conceptual categories:
  - `wrong_approach`: Fundamental algorithmic flaw (e.g. using Greedy instead of Dynamic Programming).
  - `implementation_bug`: Structural syntax/logic issue (off-by-one errors, pointer mismanagement).
  - `edge_case_miss`: Fails on boundary conditions (empty arrays, duplicate elements, large values).
  - `complexity_issue`: Solution is correct but exceeds time/space limits (TLE / OOM).
- **Actionable Guidance**: Provides plain-language explanations of *why* the logic fails without spoiling the exact code solution.

### 🧠 2. Elo-Based Topic Mastery & Adaptive Recommender
- **Dynamic Skill Scoring**: Employs an Elo rating algorithm ($R_{\text{new}} = R_{\text{old}} + K \times (S - E)$) per topic (Arrays, Two Pointers, Dynamic Programming, Graphs, etc.).
- **Productive Struggle Band**: Recommends problem difficulties (Easy $\rightarrow$ Medium $\rightarrow$ Hard) matched precisely to your current Elo rating in that specific topic.
- **Difficulty Ramp for New Topics**: Restricts new topics to Easy problems until fundamental confidence is built.
- **Epsilon-Greedy Exploration**: Periodically introduces exploratory problems outside your weak zone to ensure broad skill coverage.

### 📅 3. Spaced Repetition Review Engine
- **Automated Scheduling**: Schedules review dates based on performance (Stage 1: 3 days, Stage 2: 7 days, Stage 3: 14 days, Stage 4: Mastered).
- **Badge Notifications**: Automatically alerts you via the extension icon badge when review items are due today.

### 🚀 4. Interactive Code Coach
- **Approach Critique**: Analyzes your code efficiency before submission and suggests optimal alternatives.
- **3-Stage Levelled Hints**:
  - **Level 1**: Core Concept & Invariant Insight
  - **Level 2**: Data Structure & Algorithmic Strategy
  - **Level 3**: Step-by-Step Pseudocode & Logic Breakdown
- **Edge Case Generator**: Identifies missing edge cases and critiques constraint boundaries ($N \le 10^5$).
- **Explain-Back Verification**: Analyzes your plain-English explanation against your code implementation to ensure true conceptual comprehension.
- **Complexity Self-Estimate**: Predicts time/space complexities and compares them against AI benchmark analysis.

### 🎙️ 5. Timed Mock Interview Mode
- **Approach Gating**: Enforces real interview flow by locking the code editor until you submit your initial verbal strategy.
- **Company Filtering**: Selects real interview questions tagged by major tech companies (Google, Meta, Amazon, etc.).
- **Live Session Timer**: Tracks remaining time and logs session analytics upon completion.

### 📊 6. Analytics & Export Tools
- **Weekly Mistake Journal**: Generates a Markdown digest summarizing your past week's attempts, error categories, and review candidates.
- **Detailed Solved CSV Export**: Exports comprehensive spreadsheets with problem details, review dates, attempt counts, and custom personal notes.

---

## 🛠️ Architecture & Tech Stack

```
   ┌────────────────────────────────────────────────────────┐
   │             LeetCode Page (Chrome / Firefox)            │
   │  ┌──────────────────────────────────────────────────┐  │
   │  │ DSA Tutor Overlay Panel (React 18 + Shadow DOM)  │  │
   │  └────────────────────────┬─────────────────────────┘  │
   └───────────────────────────┼────────────────────────────┘
                               │ Chrome Extension Messaging
                               ▼
   ┌────────────────────────────────────────────────────────┐
   │          Background Service Worker (background.js)      │
   └───────────────────────────┬────────────────────────────┘
                               │ HTTP / JSON API (localhost:8000)
                               ▼
   ┌────────────────────────────────────────────────────────┐
   │            FastAPI Backend Engine (Python 3.12)        │
   │   ┌─────────────────────┐    ┌─────────────────────┐   │
   │   │  Elo Recommender    │    │  Spaced Repetition  │   │
   │   └──────────┬──────────┘    └──────────┬──────────┘   │
   │              └────────────┬─────────────┘              │
   │                           ▼                            │
   │               SQLite Database (dsa_tutor.db)           │
   │                           │                            │
   │                           ▼                            │
   │            AI Agent Router (agent.py)                  │
   │             ├── Groq Cloud API (Llama 3.3 / 3.1)       │
   │             └── Local Ollama Fallback (qwen2.5:7b)     │
   └────────────────────────────────────────────────────────┘
```

---

## 🚀 Getting Started & Local Setup

### 1. Prerequisites
- **Python**: 3.10+ (Python 3.12 recommended)
- **Node.js**: v18+ and `npm`
- **Groq API Key** *(Optional, cloud LLM)* or **Ollama** *(Local LLM)*

### 2. Backend Setup
```bash
# Clone the repository
git clone https://github.com/AnishaDhoot/LeetcodeHelper.git
cd LeetcodeHelper

# Create virtual environment & install dependencies
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

# Start backend server
powershell ./run_backend.ps1
# Or manually:
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

### 3. Extension Setup (Build & Install)
```bash
cd extension
npm install
npm run build
```
This outputs the packed Chrome Manifest V3 extension inside `extension/dist/`.

#### Installing in Browser:
1. Open Chrome/Edge/Brave and navigate to `chrome://extensions`.
2. Enable **Developer mode** (top-right toggle).
3. Click **Load unpacked** and select the `extension/dist` folder.
4. Open any problem on [LeetCode](https://leetcode.com/problems/two-sum/) to start using the DSA Tutor overlay!

---

## 🧪 Running Diagnostic Tests

To verify backend routes, database integrity, and live AI Agent diagnostics:

```bash
# Run unit & API integration tests
python -m pytest backend/test_api.py

# Run live LLM diagnostic tests
python -m pytest backend/test_llm.py
```

---

## 📄 License
MIT License © 2026 Anisha Dhoot
