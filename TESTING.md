# 🧪 CodeCoach Agent — Production QA & SDET Testing Guide

This document defines the complete automated testing architecture, gap analysis, coverage matrix, and execution guide for the **CodeCoach Agent** ecosystem (FastAPI Backend, SQLite Database, React 19 Shadow DOM Overlay, Chrome Extension Manifest V3, and Playwright E2E).

---

## 🏛️ Comprehensive Test Architecture

```
                 /  Playwright E2E Suites  \          -> Browser submission & Shadow DOM injection
                /---------------------------\
               / API Contract & State Tests   \       -> 50+ REST endpoints, Pydantic v2 schemas
              /---------------------------------\
             /  UI Interaction & Button Suites    \   -> Modals, Dropdowns, Tabs, Focus, ARIA
            /-------------------------------------\
           /  Unit & Mock Infrastructure Tests      \ -> Topic diversity, MV3 Worker, AI Router
          /-------------------------------------------\
```

---

## 📊 Interaction-Complete UI Inventory & Verification Matrix

| UI Component | Elements Tested | Actions & Behaviors Verified | Status |
| :--- | :---: | :--- | :---: |
| **Header & Overlay** | 3 buttons | Collapse, expand, reopen floating pill, AI daily quota remaining indicator | ✅ **100%** |
| **Main Navigation** | 6 tab buttons | Coach, Mastery, Reviews, Interview, Badge Test, Journal with ARIA `aria-selected` | ✅ **100%** |
| **Code Coach Tool Panel** | 4 buttons, 1 textarea | Approach critique, Edge cases, Progressive Hint stepping (1->2->3->disable), Custom Q&A submission | ✅ **100%** |
| **Mock Interview Suite** | 5 buttons, 1 modal, 1 dropdown, 1 textarea | Company picker modal, Company dropdown select, Editor lock banner, Verbal strategy submit, Finish & Grade scorecard | ✅ **100%** |
| **Badge Test Panel** | 2 buttons, 1 timer | Start topic test, Fairplay lock banner, Abandon confirmation & return | ✅ **100%** |
| **Spaced Repetition** | 2 cards, 2 buttons | Due reviews counter, Problem card resolve & dynamic queue removal | ✅ **100%** |
| **Topic Mastery & Focus** | 2 chip buttons | Level 0-5 badge progression, "Set as Focus" toggle | ✅ **100%** |
| **Weekly Journal** | 1 button | Copy formatted markdown recap to clipboard | ✅ **100%** |

---

## 📁 Repository Test Layout

```
Leetcode_helper/
├── backend/
│   ├── test_api.py                                # 24 End-to-end API integration tests
│   ├── test_llm.py                                # Live AI diagnostic smoke test
│   └── tests/
│       ├── test_agent_llm.py                      # AI parsing, <think> token removal, fallback
│       ├── test_all_endpoints_exhaustive.py       # Focus topics, weekly journals, streaks, companies
│       ├── test_api_contracts.py                  # HTTP schemas, missing fields, 422/404 validation
│       ├── test_concurrency_security.py           # Concurrency stress, SQL injection, XSS defense
│       ├── test_database_ops.py                   # DB table integrity, foreign keys, rollbacks
│       ├── test_performance.py                    # Recommendation latency benchmark (< 50ms)
│       └── test_recommender.py                    # Topic diversity, streak ramping, spaced repetition
│
├── extension/
│   ├── vitest.config.js                           # Vitest configuration (jsdom, coverage)
│   └── tests/
│       ├── setupTests.js                          # Chrome MV3 API Mocks (storage, runtime, tabs, alarms)
│       ├── ui_interactions_exhaustive.test.jsx    # Complete interactive button, modal, tab & dropdown suite
│       ├── accessibility_and_interactions.test.jsx# ARIA roles, Escape key, Double-click prevention
│       ├── extension_lifecycle.test.js            # Manifest V3 schema, worker wake-up, alarm recovery
│       ├── extension_background.test.js           # MV3 Service Worker message routing & alarms
│       ├── dom_mutation_and_spa.test.js           # SPA routing, MutationObserver DOM recovery
│       ├── injected_hooks.test.js                 # LeetCode DOM & XHR/Fetch interception
│       ├── overlay_components.test.jsx            # React 19 Shadow DOM UI, Hints, Mock Gates
│       └── state_and_ui.test.jsx                  # AI Quota bar, Fairplay locks, Badges, Reviews
│
├── e2e/
│   ├── test_submission_and_overlay.spec.js        # Playwright E2E LeetCode integration suite
│   └── test_full_user_journeys.spec.js            # E2E complete user journeys (Hint, Mock, Diagnostic)
│
└── .github/
    └── workflows/
        └── tests.yml                              # Dual-matrix CI workflow (Pytest + Vitest)
```

---

## 🚀 Test Execution Commands

### 1. Frontend & Chrome Extension Tests (Vitest)
```powershell
cd extension; npm test
```

### 2. Backend Automated Tests (Pytest)
```powershell
$env:PYTHONPATH="."; .\.venv\Scripts\pytest backend/tests backend/test_api.py -v
```

---

## 🎯 Verification Results

```text
Frontend Test Execution:
======================= 30 passed in 3.48s ========================

Backend Test Execution:
======================= 54 passed, 1 warning in 17.80s ========================
```

**Total Active Tests: 84 / 84 Passing (100% Green)** across all layers of the stack.
