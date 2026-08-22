# 🧪 CodeCoach Agent — Production QA & SDET Testing Guide

This document defines the automated test architecture, coverage matrices, mock strategies, and execution commands for the **CodeCoach Agent** ecosystem (FastAPI Backend, SQLite Database, React 19 Shadow DOM Overlay, and Chrome Extension Manifest V3).

---

## 🏛️ Testing Pyramid Architecture

```
                 /  E2E Tests  \          -> Browser submission & Shadow DOM injection
                /----------------\
               / Integration Tests \       -> API endpoints, DB transactions, AI Router
              /----------------------\
             /       Unit Tests       \    -> Topic diversity, Spaced Repetition, Hooks
            /--------------------------\
```

### Framework Selection Matrix
| Layer | Framework | Rationale |
| :--- | :--- | :--- |
| **Backend Unit & Integration** | `pytest` + `httpx` (Starlette TestClient) + `unittest.mock` | Fast, deterministic execution, native fixture dependency injection, in-memory SQLite isolation. |
| **Frontend & UI Components** | `Vitest` + `@testing-library/react` + `jsdom` | Seamless Vite integration, native ES module support, sub-second execution speed, strict DOM verification. |
| **Extension MV3 Runtime** | Custom `chrome` API mock harness + Vitest | Tests Service Worker message routing, storage sync, alarms, and tab relays without needing headless browser overhead. |
| **CI / CD Pipeline** | GitHub Actions (`.github/workflows/tests.yml`) | Automated pull request validation, linting, type-checking, and coverage enforcement. |

---

## 📁 Test Directory Structure

```
Leetcode_helper/
├── backend/
│   ├── test_api.py                           # 24 Full API integration test suites
│   ├── test_llm.py                           # Live LLM diagnostic smoke tests
│   └── tests/
│       ├── test_recommender.py               # Topic diversity, streak stepping, spaced repetition
│       ├── test_agent_llm.py                 # AI failover, JSON mode recovery, thinking tag cleanup
│       ├── test_concurrency_security.py      # Concurrency stress, SQL injection, XSS defense
│       └── test_performance.py               # Latency & throughput benchmarks (< 50ms)
│
├── extension/
│   ├── vitest.config.js                      # Vitest configuration (jsdom, coverage)
│   └── tests/
│       ├── setupTests.js                     # Global Chrome API mocks (storage, runtime, tabs, alarms)
│       ├── extension_background.test.js      # Manifest V3 background service worker tests
│       ├── injected_hooks.test.js            # DOM interception, fetch/XHR hook extraction
│       ├── overlay_components.test.jsx       # React DiagnosticCard, Hints, Mock Interview gates
│       └── state_and_ui.test.jsx             # AI Quota bar, Fairplay locks, Review lists, Badges
│
└── .github/
    └── workflows/
        └── tests.yml                         # Automated CI pipeline for Backend & Frontend
```

---

## 🚀 Running Automated Tests

### 1. Backend Test Suites (FastAPI & SQLite)
```powershell
# Run all backend tests
$env:PYTHONPATH="."; .\.venv\Scripts\pytest backend/tests backend/test_api.py -v

# Run with coverage report
$env:PYTHONPATH="."; .\.venv\Scripts\pytest backend/tests backend/test_api.py --cov=backend --cov-report=term-missing
```

### 2. Frontend & Extension Test Suites (React 19 & MV3)
```powershell
cd extension

# Run all frontend tests
npm test

# Run with test coverage
npm run test:coverage
```

### 3. All-in-One Full Stack Validation
```powershell
# From root directory:
$env:PYTHONPATH="."; .\.venv\Scripts\pytest backend/tests backend/test_api.py -v
cd extension; npm test; cd ..
```

---

## 🎯 Test Coverage Matrix & Verified Invariants

### 1. AI Router & Failure Diagnostics (`agent.py`)
- **JSON Sanitization**: Strips `<think>...</think>` reasoning tokens from Qwen/DeepSeek and isolates JSON objects.
- **Failover Pool**: Retries with relaxed formatting on 400 (`json_validate_failed`), iterates through Groq candidate models, and falls back to local Ollama.
- **Classification**: Accurately maps `wrong_approach`, `implementation_bug`, `edge_case_miss`, `complexity_issue`, and `unclear`.

### 2. Recommendation & Diversity Engine (`recommender.py`)
- **Topic Diversity**: Enforces at most 1 problem per distinct prioritized topic in primary selection pass.
- **Streak Ramping**: 2 consecutive `Accepted` attempts upgrades difficulty (Easy -> Medium -> Hard); 2 failures steps down difficulty.
- **Spaced Repetition (5 Stages)**: Stage 1 (3 days) -> Stage 2 (7 days) -> Stage 3 (14 days) -> Stage 4 (30 days) -> Stage 5 (Mastered).
- **Topic Isolation**: Pure tags (e.g. Arrays & Hashing) exclude multi-paradigm trees/graphs/DP.

### 3. Concurrency, Security & Quota (`main.py`)
- **Atomic Daily Quota**: SQLite `UPDATE ... RETURNING` prevents race conditions across concurrent threads.
- **Fairplay Mode**: Rejects hint/solution requests (HTTP 403) during active Badge Tests and LeetCode Contests.
- **Injection Defense**: Parameterized SQL prevents SQL injection; sanitizes HTML notes/comments.

### 4. Chrome Extension & Overlay UI (`extension/`)
- **Background Worker**: Correctly proxies `FETCH_API`, manages alarm intervals, updates action badges.
- **Injected Interceptor**: Parses LeetCode submission payloads (`status_code`, `last_testcase`, `runtime_error`).
- **React Components**: Renders Diagnostic Cards, steps through Level 1 -> 2 -> 3 Progressive Hints, and locks code editor during Mock Interview verbal strategy gate.
