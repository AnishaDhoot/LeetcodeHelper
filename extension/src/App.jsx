import React, { useState, useEffect } from 'react';

// Format category names for user-friendly display
const CATEGORY_MAP = {
  wrong_approach: { label: 'Wrong Approach', color: '#f59e0b', emoji: '💡' },
  implementation_bug: { label: 'Implementation Bug', color: '#f43f5e', emoji: '🐛' },
  edge_case_miss: { label: 'Edge Case Miss', color: '#fbbf24', emoji: '⚠️' },
  complexity_issue: { label: 'Complexity/Performance', color: '#3b82f6', emoji: '⚡' },
  unclear: { label: 'Diagnostics Unclear', color: '#9ca3af', emoji: '❔' }
};

export default function App() {
  const [isOpen, setIsOpen] = useState(true);
  const [activeTab, setActiveTab] = useState('mastery');
  const [masteryData, setMasteryData] = useState([]);
  const [recommendation, setRecommendation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [diagnosis, setDiagnosis] = useState(null);
  const [error, setError] = useState(null);

  // Badge Test states
  const [activeTest, setActiveTest] = useState(null);

  // Code Coach states (persistent per tool)
  const [approachResult, setApproachResult] = useState(null);
  const [edgeResult, setEdgeResult] = useState(null);
  const [askResults, setAskResults] = useState([]);
  const [diagnosisResult, setDiagnosisResult] = useState(null);

  const getBadgeEmoji = (badge) => {
    switch (badge) {
      case 'Bronze': return '🥉';
      case 'Silver': return '🥈';
      case 'Gold': return '🥇';
      case 'Platinum': return '🛡️';
      case 'Diamond': return '💎';
      default: return '❌';
    }
  };

  const fetchActiveTest = () => {
    chrome.runtime.sendMessage({ action: 'get_active_badge_test' }, (res) => {
      if (res && res.success) {
        setActiveTest(res.data);
      }
    });
  };

  const startBadgeTest = (topic) => {
    chrome.runtime.sendMessage({ action: 'start_badge_test', payload: { topic } }, (res) => {
      if (res && res.success) {
        setActiveTest(res.data);
        setActiveTab('test');
      } else {
        alert(res?.error || 'Failed to start Badge Test.');
      }
    });
  };

  const abandonBadgeTest = () => {
    if (!window.confirm('Are you sure you want to abandon this Badge Test? All progress for this test will be lost.')) return;
    chrome.runtime.sendMessage({ action: 'abandon_badge_test' }, (res) => {
      if (res && res.success) {
        setActiveTest(null);
        setActiveTab('mastery');
        fetchMastery();
      }
    });
  };

  const [aiQuota, setAiQuota] = useState({ used: 0, limit: 15 });

  const fetchAiQuota = () => {
    chrome.runtime.sendMessage({ action: 'get_ai_quota' }, (res) => {
      if (res && res.success && res.data) {
        setAiQuota(res.data);
      }
    });
  };

  const fetchActiveMock = () => {
    chrome.runtime.sendMessage({ action: 'get_active_mock' }, (res) => {
      if (res && res.success && res.data) {
        setMockSession(res.data);
        setMockApproachSubmitted(res.data.approach_submitted);
        const remaining = res.data.time_limit_seconds - res.data.elapsed_seconds;
        setMockTimerSeconds(remaining > 0 ? remaining : 0);
        setIsMockMode(true);
        if (!res.data.approach_submitted && window.dsaTutor?.setEditorReadOnly) {
          window.dsaTutor.setEditorReadOnly(true);
        }
      }
    });
  };

  const [coachFilter, setCoachFilter] = useState('all');
  const [coachLoading, setCoachLoading] = useState(null); // current action id or null
  const [coachError, setCoachError] = useState(null);
  const [askInput, setAskInput] = useState('');

  // Progressive Hint state
  const [currentProblemId, setCurrentProblemId] = useState(null);
  const [hintsList, setHintsList] = useState([]);
  const [currentHintLevel, setCurrentHintLevel] = useState(0);

  // History sync state
  const [syncStatus, setSyncStatus] = useState(null); // {phase, message, counts}

  // Backend health state
  const [backendOnline, setBackendOnline] = useState(null); // null=unknown, true/false

  // Focus topic state
  const [focusTopic, setFocusTopic] = useState(null);

  // Topic analysis state (loaded after sync or on mount)
  const [analysisData, setAnalysisData] = useState(null);

  // New Roadmap States (Tiers 1 - 5)
  const [streakData, setStreakData] = useState({ current_streak_days: 0, problems_today: 0, solved_today: 0 });
  const [companies, setCompanies] = useState([]);
  const [selectedCompany, setSelectedCompany] = useState('');
  const [weakPairs, setWeakPairs] = useState([]);
  const [estimateTime, setEstimateTime] = useState('O(N)');
  const [estimateSpace, setEstimateSpace] = useState('O(1)');
  const [showEstimateForm, setShowEstimateForm] = useState(false);
  const [estimateSubmitted, setEstimateSubmitted] = useState(false);
  const [showExplainBack, setShowExplainBack] = useState(false);
  const [userExplanationInput, setUserExplanationInput] = useState('');
  const [explainBackResult, setExplainBackResult] = useState(null);

  // Mock Mode States
  const [isMockMode, setIsMockMode] = useState(false);
  const [mockSession, setMockSession] = useState(null);
  const [mockApproachText, setMockApproachText] = useState('');
  const [mockApproachSubmitted, setMockApproachSubmitted] = useState(false);
  const [mockTimerSeconds, setMockTimerSeconds] = useState(2700);

  const fetchStreak = () => {
    chrome.runtime.sendMessage({ action: 'get_streak' }, (res) => {
      if (res && res.success) setStreakData(res.data);
    });
  };

  const fetchCompanies = () => {
    chrome.runtime.sendMessage({ action: 'get_companies' }, (res) => {
      if (res && res.success) setCompanies(res.data || []);
    });
  };

  const fetchWeakPairs = () => {
    chrome.runtime.sendMessage({ action: 'get_weak_pairs' }, (res) => {
      if (res && res.success) setWeakPairs(res.data || []);
    });
  };

  // CSV Export state
  const [csvTimeframe, setCsvTimeframe] = useState('current_week');
  const [exportingCsv, setExportingCsv] = useState(false);

  // Problem Notes & Personal Difficulty states
  const [userNotesInput, setUserNotesInput] = useState('');
  const [personalDifficultyInput, setPersonalDifficultyInput] = useState('');
  const [savingNotesStatus, setSavingNotesStatus] = useState(false);

  const fetchProblemDetails = (probId) => {
    if (!probId) return;
    chrome.runtime.sendMessage({ action: 'get_problem_details', payload: { problem_id: probId } }, (res) => {
      if (res && res.success && res.data) {
        setUserNotesInput(res.data.user_notes || '');
        setPersonalDifficultyInput(res.data.personal_difficulty || '');
      }
    });
  };

  const saveNotes = (notes, diff) => {
    const identity = window.dsaTutor?.getIdentity ? window.dsaTutor.getIdentity() : null;
    const probId = identity?.problemId || currentProblemId;
    if (!probId) return;
    const payload = {
      problem_id: probId,
      problem_title: identity?.problemTitle || probId,
      user_notes: notes,
      personal_difficulty: diff
    };
    chrome.runtime.sendMessage({ action: 'save_problem_notes', payload }, () => {
      setSavingNotesStatus(true);
      setTimeout(() => setSavingNotesStatus(false), 2000);
    });
  };

  const exportWeeklyJournal = () => {
    chrome.runtime.sendMessage({ action: 'get_weekly_journal' }, (res) => {
      if (res && res.success && res.data.markdown_text) {
        const blob = new Blob([res.data.markdown_text], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `weekly_dsa_digest_${res.data.period_end}.md`;
        a.click();
        URL.revokeObjectURL(url);
      }
    });
  };

  const exportSolvedCsv = () => {
    setExportingCsv(true);
    chrome.runtime.sendMessage({ action: 'export_solved_csv', payload: { timeframe: csvTimeframe } }, (res) => {
      setExportingCsv(false);
      if (res && res.success && res.data) {
        const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const today = new Date().toISOString().slice(0, 10);
        a.download = `dsa_solved_problems_${csvTimeframe}_${today}.csv`;
        a.click();
        URL.revokeObjectURL(url);
      } else {
        alert(res?.error || 'Failed to export CSV.');
      }
    });
  };

  const startMockInterview = () => {
    chrome.runtime.sendMessage({ action: 'mock_start', payload: { company: selectedCompany || null } }, (res) => {
      if (res && res.success) {
        setMockSession(res.data);
        setMockApproachSubmitted(false);
        setMockTimerSeconds(res.data.time_limit_seconds || 2700);
        setIsMockMode(true);
        if (window.dsaTutor?.setEditorReadOnly) {
          window.dsaTutor.setEditorReadOnly(true);
        }
        if (res.data.problem_url) {
          window.location.href = res.data.problem_url;
        }
      }
    });
  };

  const submitMockApproach = () => {
    if (!mockApproachText.trim() || !mockSession) return;
    chrome.runtime.sendMessage({ action: 'mock_approach', payload: { session_id: mockSession.session_id, approach_text: mockApproachText } }, (res) => {
      if (res && res.success) {
        setMockApproachSubmitted(true);
        if (window.dsaTutor?.setEditorReadOnly) {
          window.dsaTutor.setEditorReadOnly(false);
        }
      }
    });
  };

  const runExplainBackCheck = async () => {
    if (!userExplanationInput.trim()) return;
    try {
      const ctx = await gatherContext(true);
      const payload = { problem_id: ctx.problem_id, code: ctx.code, language: ctx.language, user_explanation: userExplanationInput.trim() };
      chrome.runtime.sendMessage({ action: 'explain_back', payload }, (res) => {
        fetchAiQuota();
        if (res && res.success) {
          setExplainBackResult(res.data);
        }
      });
    } catch (e) {
      console.warn('Explain back failed:', e);
    }
  };

  const runComplexityWithEstimate = async () => {
    if (!estimateSubmitted) {
      setShowEstimateForm(true);
      return;
    }
    setCoachError(null);
    setCoachLoading('approach');
    try {
      const ctx = await gatherContext(true);
      const estPayload = { problem_id: ctx.problem_id, time_complexity: estimateTime, space_complexity: estimateSpace };
      chrome.runtime.sendMessage({ action: 'critique_estimate', payload: estPayload }, () => {
        chrome.runtime.sendMessage({ action: 'critique_reveal', payload: ctx }, (response) => {
          setCoachLoading(null);
          fetchAiQuota();
          if (response && response.success) {
            setApproachResult(response.data);
            setCoachFilter('approach');
            setIsOpen(true);
            setActiveTab('coach');
          } else {
            setCoachError(response?.error || 'Request failed.');
          }
        });
      });
    } catch (e) {
      setCoachLoading(null);
      setCoachError(e.message || String(e));
    }
  };

  // Helper: gather current code/lang/constraints + identity, throw on empty code.
  const gatherContext = async (requireCode = true) => {
    const identity = window.dsaTutor?.getIdentity
      ? window.dsaTutor.getIdentity()
      : { problemId: 'unknown-problem', problemTitle: 'Unknown Problem' };
    const code = window.dsaTutor?.getCode ? await window.dsaTutor.getCode() : '';
    const language = window.dsaTutor?.getLanguage ? window.dsaTutor.getLanguage() : 'python3';
    const constraints = window.dsaTutor?.getConstraints ? window.dsaTutor.getConstraints() : null;
    if (requireCode && !code) {
      throw new Error('No code found in the editor. Open a problem and write some code first.');
    }
    return {
      problem_id: identity.problemId,
      problem_title: identity.problemTitle,
      code,
      language,
      constraints
    };
  };

  // Generic Code Coach action runner.
  const runCoachAction = async (actionId, messageAction) => {
    setCoachError(null);
    setCoachLoading(actionId);
    try {
      const ctx = await gatherContext(true);
      chrome.runtime.sendMessage({ action: messageAction, payload: ctx }, (response) => {
        setCoachLoading(null);
        fetchAiQuota();
        if (response && response.success) {
          if (actionId === 'edge') {
            setEdgeResult(response.data);
            setCoachFilter('edge');
          } else if (actionId === 'approach') {
            setApproachResult(response.data);
            setCoachFilter('approach');
          }
          setIsOpen(true);
          setActiveTab('coach');
        } else {
          setCoachError(response?.error || 'Request failed.');
        }
      });
    } catch (e) {
      setCoachLoading(null);
      setCoachError(e.message || String(e));
    }
  };

  // Reveal next level of progressive hints.
  const revealNextHint = async () => {
    setCoachError(null);
    setCoachLoading('hint');
    try {
      const ctx = await gatherContext(true);
      const nextLevel = currentHintLevel + 1;
      const payload = { ...ctx, level: nextLevel };
      
      chrome.runtime.sendMessage({ action: 'reveal_hint', payload }, (response) => {
        setCoachLoading(null);
        fetchAiQuota();
        if (response && response.success) {
          const newHint = { level: response.data.level, hint: response.data.hint };
          setHintsList(prev => {
            const exists = prev.some(h => h.level === newHint.level);
            if (exists) return prev;
            return [...prev, newHint];
          });
          setCurrentHintLevel(response.data.level);
          setCoachFilter('hints');
          if (window.dsaTutor) {
            window.dsaTutor.hintsUsed = response.data.level;
          }
          setIsOpen(true);
          setActiveTab('coach');
        } else {
          setCoachError(response?.error || 'Request failed.');
        }
      });
    } catch (e) {
      setCoachLoading(null);
      setCoachError(e.message || String(e));
    }
  };

  // Ask a free-form question about the current code.
  const runAskHelp = async () => {
    if (!askInput.trim()) return;
    const currentQ = askInput.trim();
    setCoachError(null);
    setCoachLoading('ask');
    try {
      const ctx = await gatherContext(true);
      const payload = { ...ctx, question: currentQ };
      chrome.runtime.sendMessage({ action: 'ask_help', payload }, (response) => {
        setCoachLoading(null);
        fetchAiQuota();
        if (response && response.success) {
          setAskResults(prev => [...prev, { id: Date.now(), question: currentQ, answer: response.data.answer }]);
          setAskInput('');
          setCoachFilter('ask');
          setIsOpen(true);
          setActiveTab('coach');
        } else {
          setCoachError(response?.error || 'Request failed.');
        }
      });
    } catch (e) {
      setCoachLoading(null);
      setCoachError(e.message || String(e));
    }
  };

  const runHistorySync = async () => {
    setSyncStatus({ phase: 'fetching', message: 'Fetching all your solved problems from LeetCode… This may take a moment.' });
    chrome.runtime.sendMessage({ action: 'fetch_leetcode_history' }, (fetchRes) => {
      if (!fetchRes || !fetchRes.success) {
        setSyncStatus({ phase: 'error', message: fetchRes?.error || 'Failed to fetch LeetCode history.' });
        return;
      }
      const problems = fetchRes.data?.problems || [];
      if (problems.length === 0) {
        setSyncStatus({ phase: 'done', message: 'No solved problems found. Solve a few on LeetCode first!', counts: { synced: 0, topics: 0 } });
        return;
      }
      setSyncStatus({ phase: 'syncing', message: `Importing ${problems.length} solved problem(s) into your tutor…` });
      chrome.runtime.sendMessage({ action: 'sync_solved', payload: { problems } }, (syncRes) => {
        if (!syncRes || !syncRes.success) {
          setSyncStatus({ phase: 'error', message: syncRes?.error || 'Backend sync failed.' });
          return;
        }
        const { synced, topics, new_topics } = syncRes.data;
        setSyncStatus({
          phase: 'done',
          message: syncRes.data.message,
          counts: { synced, topics, new_topics, fetched: problems.length }
        });
        // Refresh mastery, focus, analysis, and recommendations.
        fetchMastery();
        fetchFocus();
        fetchAnalysis();
        fetchRecommendation();
        fetchStreak();
      });
    });
  };


  const checkBackendHealth = () => {
    chrome.runtime.sendMessage({ action: 'check_health' }, (response) => {
      setBackendOnline(!!(response && response.success));
    });
  };

  const fetchFocus = () => {
    chrome.runtime.sendMessage({ action: 'get_focus' }, (response) => {
      if (response && response.success) {
        setFocusTopic(response.data?.focus_topic || null);
      }
    });
  };

  const setFocus = (topic) => {
    chrome.runtime.sendMessage({ action: 'set_focus', payload: { topic: topic || '' } }, (response) => {
      if (response && response.success) {
        setFocusTopic(response.data?.focus_topic || null);
        fetchRecommendation(); // Refresh to pick up focus-based rec
      }
    });
  };

  const fetchAnalysis = () => {
    chrome.runtime.sendMessage({ action: 'get_analysis' }, (response) => {
      if (response && response.success) {
        setAnalysisData(response.data);
      }
    });
  };

  const clearCurrentCoachState = () => {
    setApproachResult(null);
    setEdgeResult(null);
    setAskResults([]);
    setDiagnosisResult(null);
    setHintsList([]);
    setCurrentHintLevel(0);
    setShowEstimateForm(false);
    setEstimateSubmitted(false);
    setUserExplanationInput('');
    setExplainBackResult(null);
    setShowExplainBack(false);
    setCoachError(null);
    setAskInput('');
    setCoachFilter('all');
    if (window.dsaTutor) {
      window.dsaTutor.hintsUsed = 0;
    }
  };

  // Instant URL change listener + fast polling to detect problem navigation
  useEffect(() => {
    let lastUrl = window.location.href;

    const checkProblemChange = () => {
      try {
        const currentUrl = window.location.href;
        const identity = window.dsaTutor?.getIdentity ? window.dsaTutor.getIdentity() : null;
        if (identity && (identity.problemId !== currentProblemId || currentUrl !== lastUrl)) {
          lastUrl = currentUrl;
          setCurrentProblemId(identity.problemId);
          clearCurrentCoachState();
          fetchProblemDetails(identity.problemId);
        }
      } catch (e) {
        // Ignore
      }
    };

    checkProblemChange();
    window.addEventListener('popstate', checkProblemChange);
    const interval = setInterval(checkProblemChange, 500);

    return () => {
      window.removeEventListener('popstate', checkProblemChange);
      clearInterval(interval);
    };
  }, [currentProblemId]);

  // Mock interview timer
  useEffect(() => {
    if (!isMockMode || !mockSession) return;
    const t = setInterval(() => {
      setMockTimerSeconds(prev => {
        if (prev <= 1) {
          clearInterval(t);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(t);
  }, [isMockMode, mockSession]);

  // Fetch data on mount
  useEffect(() => {
    fetchMastery();
    fetchRecommendation();
    checkBackendHealth();
    fetchFocus();
    fetchAnalysis();
    fetchStreak();
    fetchCompanies();
    fetchWeakPairs();
    fetchActiveTest();
    fetchAiQuota();
    fetchActiveMock();

    // Extend (do NOT overwrite) window.dsaTutor so the page-context scrapers from
    // main.jsx (getCode/getLanguage/getConstraints/getIdentity) are preserved.
    window.dsaTutor = Object.assign(window.dsaTutor || {}, {
      setLoading: (isLoading) => {
        setLoading(isLoading);
        if (isLoading) {
          setIsOpen(true);
          setActiveTab('coach');
          setDiagnosis(null);
          setError(null);
        }
      },
      setDiagnosis: (diagResult) => {
        setLoading(false);
        setDiagnosis(diagResult);
        setIsOpen(true);
        setActiveTab('coach');
        // Auto-diagnosis results go into the Code Coach result area too.
        setDiagnosisResult(diagResult);
        setCoachError(null);
        setCoachLoading(null);
        if (diagResult.verdict === 'Accepted') {
          setShowExplainBack(true);
        }
        // Refresh mastery & recommendations as they might have changed
        fetchMastery();
        fetchRecommendation();
        fetchStreak();
        fetchActiveTest();
        fetchAiQuota();
      },
      setError: (errMessage) => {
        setLoading(false);
        setError(errMessage);
        setIsOpen(true);
        setActiveTab('coach');
      },
      refreshData: () => {
        fetchMastery();
        fetchRecommendation();
        fetchStreak();
        fetchActiveTest();
        fetchAiQuota();
      }
    });

    return () => {
      // Only remove our own handlers; leave the scraper helpers intact.
      if (window.dsaTutor) {
        delete window.dsaTutor.setLoading;
        delete window.dsaTutor.setDiagnosis;
        delete window.dsaTutor.setError;
        delete window.dsaTutor.refreshData;
      }
    };
  }, []);

  const fetchMastery = () => {
    chrome.runtime.sendMessage({ action: 'get_mastery' }, (response) => {
      if (response && response.success) {
        // Sort by lowest mastery score first
        const sortedData = [...response.data].sort((a, b) => a.mastery_score - b.mastery_score);
        setMasteryData(sortedData);
      } else {
        console.error('Failed to fetch mastery:', response?.error);
      }
    });
  };

  const fetchRecommendation = (comp = selectedCompany) => {
    chrome.runtime.sendMessage({ action: 'get_recommendation', payload: { company: comp || null } }, (response) => {
      if (response && response.success) {
        setRecommendation(response.data);
      } else {
        console.error('Failed to fetch recommendation:', response?.error);
      }
    });
  };

  if (!isOpen) {
    return (
      <div className="tutor-trigger" onClick={() => setIsOpen(true)} title="Open Kode">
        {/* Bracket mark */}
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M8 3H7a2 2 0 0 0-2 2v5a2 2 0 0 1-2 2 2 2 0 0 1 2 2v5a2 2 0 0 0 2 2h1"/>
          <path d="M16 3h1a2 2 0 0 1 2 2v5a2 2 0 0 0 2 2 2 2 0 0 0-2 2v5a2 2 0 0 1-2 2h-1"/>
        </svg>
      </div>
    );
  }

  return (
    <div id="dsa-tutor-panel-container">
      {/* Header */}
      <div className="tutor-header">
        <h3 className="tutor-title">
          <span className="logo-mark">
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#71717a" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M8 3H7a2 2 0 0 0-2 2v5a2 2 0 0 1-2 2 2 2 0 0 1 2 2v5a2 2 0 0 0 2 2h1"/>
              <path d="M16 3h1a2 2 0 0 1 2 2v5a2 2 0 0 0 2 2 2 2 0 0 0-2 2v5a2 2 0 0 1-2 2h-1"/>
            </svg>
          </span>
          Kode
          <span style={{ fontSize: '11px', background: '#27272a', padding: '2px 6px', borderRadius: '10px', color: '#f59e0b', fontWeight: '500' }}>
            🔥 {streakData.current_streak_days}d
          </span>
        </h3>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            onClick={() => {
              if (!isMockMode) {
                startMockInterview();
              } else {
                setIsMockMode(false);
                if (window.dsaTutor?.setEditorReadOnly) {
                  window.dsaTutor.setEditorReadOnly(false);
                }
              }
            }}
            style={{
              background: isMockMode ? '#ef444422' : '#27272a',
              color: isMockMode ? '#f87171' : '#a1a1aa',
              border: `1px solid ${isMockMode ? '#ef444455' : '#3f3f46'}`,
              borderRadius: '6px',
              padding: '2px 8px',
              fontSize: '11px',
              cursor: 'pointer',
              fontWeight: '500'
            }}
          >
            {isMockMode ? '⏱ Mocking' : 'Practice'}
          </button>

          <button className="close-btn" onClick={() => setIsOpen(false)} title="Close">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
      </div>

      {/* Tabs Menu */}
      {!activeTest && (
        <div className="tabs-container">
          <button
            className={`tab-btn ${activeTab === 'mastery' ? 'active' : ''}`}
            onClick={() => setActiveTab('mastery')}
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 3v18h18" />
              <path d="m19 9-5 5-4-4-3 3" />
            </svg>
            Mastery
          </button>
          <button
            className={`tab-btn ${activeTab === 'coach' ? 'active' : ''}`}
            onClick={() => setActiveTab('coach')}
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M8 3H7a2 2 0 0 0-2 2v5a2 2 0 0 1-2 2 2 2 0 0 1 2 2v5a2 2 0 0 0 2 2h1"/>
              <path d="M16 3h1a2 2 0 0 1 2 2v5a2 2 0 0 0 2 2 2 2 0 0 0-2 2v5a2 2 0 0 1-2 2h-1"/>
            </svg>
            Coach
          </button>
          <button
            className={`tab-btn ${activeTab === 'recommendation' ? 'active' : ''}`}
            onClick={() => setActiveTab('recommendation')}
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
            Next
          </button>
          <button
            className={`tab-btn ${activeTab === 'history' ? 'active' : ''}`}
            onClick={() => setActiveTab('history')}
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="1 4 1 10 7 10" />
              <path d="M3.51 15a9 9 0 1 0 .49-4.5" />
            </svg>
            Sync
          </button>
        </div>
      )}

      {/* Content Area */}
      <div className="tutor-content">
        {/* Mock Interview Active Session Banner (Tier 4.1) */}
        {isMockMode && mockSession && (
          <div className="info-section" style={{ borderColor: '#ef444466', background: '#ef444415', marginBottom: '14px' }}>
            <div className="section-label" style={{ color: '#f87171', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>⏱ Mock Interview Mode</span>
              <span style={{ fontFamily: 'monospace', fontSize: '13px', background: '#27272a', padding: '2px 6px', borderRadius: '4px', color: '#fff' }}>
                {Math.floor(mockTimerSeconds / 60)}:{String(mockTimerSeconds % 60).padStart(2, '0')}
              </span>
            </div>
            <div style={{ fontSize: '12px', marginTop: '6px', color: '#e4e4e7' }}>
              Problem: <strong>{mockSession.problem_title}</strong> ({mockSession.difficulty})
            </div>
            {!mockApproachSubmitted ? (
              <div style={{ marginTop: '8px' }}>
                <div style={{ fontSize: '11px', color: '#fbbf24', marginBottom: '4px' }}>
                  🔒 Code Editor Locked! Write your approach first to unlock:
                </div>
                <textarea
                  className="ask-input"
                  rows={2}
                  placeholder="Outline your algorithm approach, data structures, and edge cases..."
                  value={mockApproachText}
                  onChange={(e) => setMockApproachText(e.target.value)}
                  style={{ fontSize: '12px' }}
                />
                <button className="coach-btn" style={{ marginTop: '6px', width: '100%' }} onClick={submitMockApproach}>
                  Submit Approach & Unlock Editor
                </button>
              </div>
            ) : (
              <div style={{ fontSize: '11px', color: '#4ade80', marginTop: '6px' }}>
                ✓ Approach accepted! Code editor unlocked. Solve and submit on LeetCode before time expires.
              </div>
            )}
          </div>
        )}

        {/* TAB 1: MASTERY OVERVIEW */}
        {activeTab === 'mastery' && (
          <div>
            {/* Focus banner */}
            {focusTopic && (
              <div className="focus-banner">
                <div className="focus-banner-text">
                  <span className="focus-icon">◎</span>
                  <span>Focus: <strong style={{color:'#d4d4d8'}}>{focusTopic}</strong></span>
                </div>
                <button className="focus-change-btn" onClick={() => setFocus('')}>
                  Clear
                </button>
              </div>
            )}

            {/* Badge Test Mode view */}
        {activeTest && (
          <div className="test-mode-container">
            <div className="test-mode-header">
              <div className="test-mode-title">
                🏆 Badge Test: {activeTest.topic} Level {activeTest.level}
              </div>
              <p style={{ fontSize: '11px', color: '#a1a1aa', margin: '4px 0 0 0' }}>
                Solve both problems in LeetCode to unlock the <strong>{activeTest.level === 1 ? 'Bronze' : activeTest.level === 2 ? 'Silver' : activeTest.level === 3 ? 'Gold' : activeTest.level === 4 ? 'Platinum' : 'Diamond'}</strong> badge. Hints and Code Coach assistance are locked.
              </p>
            </div>
            
            <div className="test-mode-problem-list">
              <div className={`test-problem-card ${activeTest.problem1_solved ? 'solved' : 'unsolved'}`}>
                <div>
                  <a
                    href={activeTest.problem1.url}
                    target="_blank"
                    rel="noreferrer"
                    className="badge-quest-link"
                    style={{ fontSize: '13px', fontWeight: '600' }}
                  >
                    1. {activeTest.problem1.title}
                  </a>
                  <div style={{ fontSize: '11px', color: '#71717a', marginTop: '2px' }}>
                    Difficulty: {activeTest.problem1.difficulty}
                  </div>
                </div>
                <div>
                  {activeTest.problem1_solved ? (
                    <span style={{ fontSize: '12px', color: '#22c55e', fontWeight: 'bold' }}>🟢 Solved</span>
                  ) : (
                    <span style={{ fontSize: '12px', color: '#f59e0b', fontWeight: 'bold' }}>🔴 Unsolved</span>
                  )}
                </div>
              </div>

              <div className={`test-problem-card ${activeTest.problem2_solved ? 'solved' : 'unsolved'}`}>
                <div>
                  <a
                    href={activeTest.problem2.url}
                    target="_blank"
                    rel="noreferrer"
                    className="badge-quest-link"
                    style={{ fontSize: '13px', fontWeight: '600' }}
                  >
                    2. {activeTest.problem2.title}
                  </a>
                  <div style={{ fontSize: '11px', color: '#71717a', marginTop: '2px' }}>
                    Difficulty: {activeTest.problem2.difficulty}
                  </div>
                </div>
                <div>
                  {activeTest.problem2_solved ? (
                    <span style={{ fontSize: '12px', color: '#22c55e', fontWeight: 'bold' }}>🟢 Solved</span>
                  ) : (
                    <span style={{ fontSize: '12px', color: '#f59e0b', fontWeight: 'bold' }}>🔴 Unsolved</span>
                  )}
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '12px' }}>
              <button className="abandon-btn" onClick={abandonBadgeTest}>
                Abandon Test
              </button>
            </div>
          </div>
        )}
          </div>
        )}

        {/* TAB 1: MASTERY OVERVIEW */}
        {!activeTest && activeTab === 'mastery' && (
          <div>
            {weakPairs && weakPairs.length > 0 && (
              <div className="info-section alt-section" style={{ marginBottom: '14px', borderLeftColor: '#fbbf24' }}>
                <div className="section-label alt-label" style={{ color: '#fbbf24' }}>
                  💡 Prerequisite Review Suggestion
                </div>
                <div className="section-content" style={{ fontSize: '12px', color: '#d4d4d8' }}>
                  Review <strong>{weakPairs[0].topic_a}</strong> before tackling <strong>{weakPairs[0].topic_b}</strong> (co-occurred {weakPairs[0].co_occurrence} times).
                </div>
              </div>
            )}

            <h4 className="section-heading">Per-Topic Mastery</h4>
            {masteryData.length === 0 ? (
              <div className="empty-state">
                No topic data loaded. Backend offline or database empty.
              </div>
            ) : (
              masteryData.map((data) => {
                const pct = data.mastery_score * 100;
                const levelColor = pct >= 65 ? 'high' : pct >= 35 ? 'mid' : 'low';
                return (
                  <div
                    key={data.topic}
                    className={`mastery-card ${data.topic === focusTopic ? 'mastery-card-focus' : ''}`}
                    data-level={levelColor}
                  >
                    <div className="mastery-header">
                      <span className="mastery-name">{data.topic}</span>
                      {data.badge !== 'None' ? (
                        <span className="badge-status-pill earned">
                          {getBadgeEmoji(data.badge)} {data.badge}
                        </span>
                      ) : (
                        <span className="badge-status-pill locked">
                          🔒 Locked
                        </span>
                      )}
                    </div>
                    <div className="progress-bar-bg">
                      <div
                        className="progress-bar-fg"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <div className="mastery-meta" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: '11px', color: '#a1a1aa' }}>Level {data.level}/5</span>
                      <div style={{ display: 'flex', gap: '6px' }}>
                        {data.level < 5 ? (
                          <button className="badge-btn" onClick={() => startBadgeTest(data.topic)}>
                            🚀 Test L{data.level + 1}
                          </button>
                        ) : (
                          <span style={{ color: '#22c55e', fontWeight: '600', fontSize: '11px' }}>🏆 Max Tier!</span>
                        )}
                        <button
                          className={`focus-pick-btn ${data.topic === focusTopic ? 'active' : ''}`}
                          onClick={() => setFocus(data.topic)}
                          title={data.topic === focusTopic ? 'Remove focus' : 'Set as focus topic'}
                        >
                          {data.topic === focusTopic ? 'Focused' : 'Focus'}
                        </button>
                      </div>
                    </div>

                    {data.level < 5 && data.next_questions && data.next_questions.length > 0 && (
                      <div style={{ marginTop: '6px', paddingTop: '6px', borderTop: '1px dashed #27272a' }}>
                        <div style={{ fontSize: '10px', color: '#71717a', marginBottom: '2px' }}>💡 Practice interview questions:</div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                          {data.next_questions.map(q => (
                            <a key={q.id} href={q.url} target="_blank" rel="noreferrer" className="badge-quest-link">
                              🚀 {q.title} <span style={{ fontSize: '9px', color: '#71717a' }}>({q.difficulty})</span>
                            </a>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        )}

        {/* TAB 2: CODE COACH */}
        {activeTab === 'coach' && (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
              <h4 className="section-heading" style={{ margin: 0 }}>Code Coach</h4>
              {(approachResult || hintsList.length > 0 || edgeResult || askResults.length > 0 || diagnosisResult || coachError) && (
                <button
                  onClick={clearCurrentCoachState}
                  style={{ background: 'transparent', color: '#71717a', border: 'none', fontSize: '11px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
                  title="Clear all results for current problem"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
                  Reset View
                </button>
              )}
            </div>
            <p className="coach-intro">
              Analyze the code currently inside LeetCode's editor using autonomous diagnostic tools.
            </p>

            {/* Post-Solve Explain-Back Check (Tier 3.2) */}
            {showExplainBack && (
              <div className="info-section alt-section" style={{ marginBottom: '14px', borderColor: '#22c55e44', background: '#22c55e11' }}>
                <div className="section-label alt-label" style={{ color: '#4ade80' }}>
                  🎉 Problem Solved! Explain your approach
                </div>
                <textarea
                  className="ask-input"
                  rows={2}
                  placeholder="Briefly explain how your solution works in 1-2 sentences..."
                  value={userExplanationInput}
                  onChange={(e) => setUserExplanationInput(e.target.value)}
                  style={{ marginTop: '6px', fontSize: '12px' }}
                />
                <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                  <button className="coach-btn" style={{ flex: 1 }} onClick={runExplainBackCheck}>
                    Verify Explanation
                  </button>
                  <button className="coach-btn secondary" style={{ flex: 'none' }} onClick={() => setShowExplainBack(false)}>
                    Skip
                  </button>
                </div>
                {explainBackResult && (
                  <div style={{ marginTop: '8px', fontSize: '12px', color: explainBackResult.matches ? '#4ade80' : '#fbbf24' }}>
                    {explainBackResult.matches ? '✓ Great explanation! Perfectly matches your code.' : `⚠️ ${explainBackResult.discrepancy_note}`}
                  </div>
                )}
              </div>
            )}

            {/* Action buttons */}
            <div className="coach-actions">
              <button
                className={`coach-btn ${coachLoading === 'approach' ? 'loading' : ''}`}
                disabled={!!coachLoading}
                onClick={() => runCoachAction('approach', 'check_approach')}
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{marginRight: '6px', verticalAlign: 'middle'}}><circle cx="12" cy="12" r="10"/><line x1="22" y1="12" x2="18" y2="12"/><line x1="6" y1="12" x2="2" y2="12"/><line x1="12" y1="6" x2="12" y2="2"/><line x1="12" y1="22" x2="12" y2="18"/></svg>
                {coachLoading === 'approach' ? 'Analyzing approach…' : 'Analyze Approach'}
              </button>
              <button
                className={`coach-btn secondary ${coachLoading === 'hint' ? 'loading' : ''}`}
                disabled={!!coachLoading || currentHintLevel >= 3}
                onClick={revealNextHint}
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{marginRight: '6px', verticalAlign: 'middle'}}><path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A5 5 0 0 0 8 8c0 1 .3 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/></svg>
                {coachLoading === 'hint' 
                  ? 'Thinking…' 
                  : currentHintLevel >= 3 
                    ? 'All Hints Unlocked' 
                    : currentHintLevel > 0 
                      ? `Get Hint (Level ${currentHintLevel + 1})` 
                      : 'Get a Hint'}
              </button>
              <button
                className={`coach-btn secondary ${coachLoading === 'edge' ? 'loading' : ''}`}
                disabled={!!coachLoading}
                onClick={() => runCoachAction('edge', 'get_edge_cases')}
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{marginRight: '6px', verticalAlign: 'middle'}}><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                {coachLoading === 'edge' ? 'Checking…' : 'Edge Cases'}
              </button>
            </div>

            {/* Loading / error states */}
            {coachLoading && (
              <div className="loading-container">
                <div className="spinner" />
                <p style={{ margin: 0, fontSize: '12px', color: '#71717a' }}>Analyzing…</p>
              </div>
            )}
            {coachError && (
              <div className="info-section error-section">
                <div className="section-label error-label">
                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{marginRight: '4px'}}><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                  Error
                </div>
                <div className="section-content">{coachError}</div>
              </div>
            )}

            {/* Live submission auto-diagnosis */}
            {loading && (
              <div className="loading-container">
                <div className="spinner" />
                <p style={{ margin: 0, fontSize: '12px', color: '#71717a' }}>Analyzing submission…</p>
              </div>
            )}
            {error && (
              <div className="info-section error-section">
                <div className="section-label error-label">
                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{marginRight: '4px'}}><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                  Error
                </div>
                <div className="section-content">{error}</div>
              </div>
            )}

            {/* Multi-Tool Results (Stacked & Persistent) */}
            {!coachLoading && (approachResult || hintsList.length > 0 || edgeResult || askResults.length > 0 || diagnosisResult) && (
              <div className="coach-result-container" style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginTop: '12px' }}>
                
                {/* Filter bar if multiple outputs exist */}
                {((approachResult ? 1 : 0) + (hintsList.length ? 1 : 0) + (edgeResult ? 1 : 0) + (askResults.length ? 1 : 0) + (diagnosisResult ? 1 : 0)) > 1 && (
                  <div className="filter-chips-bar" style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '4px' }}>
                    <button
                      className={`filter-chip ${coachFilter === 'all' ? 'active' : ''}`}
                      onClick={() => setCoachFilter('all')}
                      style={{ background: coachFilter === 'all' ? '#3f3f46' : '#18181b', color: coachFilter === 'all' ? '#fff' : '#a1a1aa', border: '1px solid #27272a', borderRadius: '12px', padding: '3px 10px', fontSize: '11px', cursor: 'pointer' }}
                    >
                      All ({ (approachResult ? 1 : 0) + (hintsList.length ? 1 : 0) + (edgeResult ? 1 : 0) + (askResults.length ? 1 : 0) + (diagnosisResult ? 1 : 0) })
                    </button>
                    {approachResult && (
                      <button
                        className={`filter-chip ${coachFilter === 'approach' ? 'active' : ''}`}
                        onClick={() => setCoachFilter('approach')}
                        style={{ background: coachFilter === 'approach' ? '#3f3f46' : '#18181b', color: coachFilter === 'approach' ? '#fff' : '#a1a1aa', border: '1px solid #27272a', borderRadius: '12px', padding: '3px 10px', fontSize: '11px', cursor: 'pointer' }}
                      >
                        Approach
                      </button>
                    )}
                    {hintsList.length > 0 && (
                      <button
                        className={`filter-chip ${coachFilter === 'hints' ? 'active' : ''}`}
                        onClick={() => setCoachFilter('hints')}
                        style={{ background: coachFilter === 'hints' ? '#3f3f46' : '#18181b', color: coachFilter === 'hints' ? '#fff' : '#a1a1aa', border: '1px solid #27272a', borderRadius: '12px', padding: '3px 10px', fontSize: '11px', cursor: 'pointer' }}
                      >
                        Hints ({hintsList.length})
                      </button>
                    )}
                    {edgeResult && (
                      <button
                        className={`filter-chip ${coachFilter === 'edge' ? 'active' : ''}`}
                        onClick={() => setCoachFilter('edge')}
                        style={{ background: coachFilter === 'edge' ? '#3f3f46' : '#18181b', color: coachFilter === 'edge' ? '#fff' : '#a1a1aa', border: '1px solid #27272a', borderRadius: '12px', padding: '3px 10px', fontSize: '11px', cursor: 'pointer' }}
                      >
                        Edge Cases
                      </button>
                    )}
                    {askResults.length > 0 && (
                      <button
                        className={`filter-chip ${coachFilter === 'ask' ? 'active' : ''}`}
                        onClick={() => setCoachFilter('ask')}
                        style={{ background: coachFilter === 'ask' ? '#3f3f46' : '#18181b', color: coachFilter === 'ask' ? '#fff' : '#a1a1aa', border: '1px solid #27272a', borderRadius: '12px', padding: '3px 10px', fontSize: '11px', cursor: 'pointer' }}
                      >
                        Q&A ({askResults.length})
                      </button>
                    )}
                    {diagnosisResult && (
                      <button
                        className={`filter-chip ${coachFilter === 'diagnosis' ? 'active' : ''}`}
                        onClick={() => setCoachFilter('diagnosis')}
                        style={{ background: coachFilter === 'diagnosis' ? '#3f3f46' : '#18181b', color: coachFilter === 'diagnosis' ? '#fff' : '#a1a1aa', border: '1px solid #27272a', borderRadius: '12px', padding: '3px 10px', fontSize: '11px', cursor: 'pointer' }}
                      >
                        Diagnosis
                      </button>
                    )}
                  </div>
                )}

                {/* 1. Auto-diagnosis Result Section */}
                {diagnosisResult && (coachFilter === 'all' || coachFilter === 'diagnosis') && (
                  <div className="coach-result">
                    <div className="diagnosis-badges">
                      <span className={`verdict-badge ${diagnosisResult.verdict === 'Accepted' ? 'success' : 'failure'}`}>
                        {diagnosisResult.verdict === 'Accepted' ? (
                          <>
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" style={{marginRight: '6px'}}><polyline points="20 6 9 17 4 12"/></svg>
                            Accepted
                          </>
                        ) : (
                          <>
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{marginRight: '6px'}}><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                            {diagnosisResult.verdict || 'Failed'}
                          </>
                        )}
                      </span>
                      {diagnosisResult.verdict !== 'Accepted' && diagnosisResult.root_cause_category && CATEGORY_MAP[diagnosisResult.root_cause_category] && (
                        <span
                          className="category-tag"
                          style={{
                            color: CATEGORY_MAP[diagnosisResult.root_cause_category].color,
                            borderColor: `${CATEGORY_MAP[diagnosisResult.root_cause_category].color}30`,
                            background: `${CATEGORY_MAP[diagnosisResult.root_cause_category].color}12`
                          }}
                        >
                          {CATEGORY_MAP[diagnosisResult.root_cause_category].emoji} {CATEGORY_MAP[diagnosisResult.root_cause_category].label}
                        </span>
                      )}
                    </div>
                    <div className="info-section">
                      <div className="section-label">
                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{marginRight: '4px'}}><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                        Root Cause Analysis
                      </div>
                      <div className="section-content">{diagnosisResult.explanation}</div>
                    </div>
                    {diagnosisResult.suggested_action && (
                      <div className="info-section alt-section">
                        <div className="section-label alt-label">
                          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{marginRight: '4px'}}><polygon points="5 3 19 12 5 21 5 3"/></svg>
                          Suggested Action
                        </div>
                        <div className="section-content">{diagnosisResult.suggested_action}</div>
                      </div>
                    )}
                  </div>
                )}

                {/* 2. Approach Critique Section */}
                {approachResult && (coachFilter === 'all' || coachFilter === 'approach') && (
                  <div className="coach-result">
                    <div className="coach-result-head">
                      <span className={`tag-pill ${approachResult.is_optimal ? 'tag-good' : 'tag-bad'}`}>
                        {approachResult.is_optimal ? (
                          <>
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" style={{marginRight: '6px'}}><polyline points="20 6 9 17 4 12"/></svg>
                            Optimal Approach
                          </>
                        ) : (
                          <>
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{marginRight: '6px'}}><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                            Can be optimized
                          </>
                        )}
                      </span>
                    </div>
                    <div className="complexity-row">
                      <div>
                        <span className="complexity-label">Current Complexity</span>
                        <span>{approachResult.current_complexity}</span>
                      </div>
                      <div>
                        <span className="complexity-label">Optimal Complexity</span>
                        <span>{approachResult.optimal_complexity}</span>
                      </div>
                    </div>
                    <div className="info-section">
                      <div className="section-label">
                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{marginRight: '4px'}}><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                        Feedback
                      </div>
                      <div className="section-content">{approachResult.feedback}</div>
                    </div>
                    <div className="info-section alt-section">
                      <div className="section-label alt-label">
                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{marginRight: '4px'}}><polygon points="5 3 19 12 5 21 5 3"/></svg>
                        Alternative Approach
                      </div>
                      <div className="section-content">{approachResult.alternative_approach}</div>
                    </div>
                  </div>
                )}

                {/* 3. Progressive Hints Section */}
                {hintsList.length > 0 && (coachFilter === 'all' || coachFilter === 'hints') && (
                  <div className="coach-result">
                    <div className="progressive-hints-container" style={{ display: 'flex', flexDirection: 'column', gap: '12px', width: '100%' }}>
                      {hintsList.map((h) => (
                        <div key={h.level} className="info-section alt-section" style={{ margin: 0 }}>
                          <div className="section-label alt-label" style={{ display: 'flex', alignItems: 'center' }}>
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{marginRight: '4px'}}><path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A5 5 0 0 0 8 8c0 1 .3 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/></svg>
                            {h.level === 1 ? '💡 Level 1: Conceptual Strategy' : h.level === 2 ? '⚙️ Level 2: Algorithmic Strategy' : '🛠️ Level 3: Pseudocode Breakdown'}
                          </div>
                          <div className="section-content" style={{ whiteSpace: 'pre-wrap' }}>{h.hint}</div>
                        </div>
                      ))}
                      
                      {currentHintLevel < 3 && (
                        <div style={{ marginTop: '4px' }}>
                          <button
                            className={`coach-btn ${coachLoading === 'hint' ? 'loading' : ''}`}
                            disabled={!!coachLoading}
                            onClick={revealNextHint}
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{marginRight: '6px', verticalAlign: 'middle'}}><path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A5 5 0 0 0 8 8c0 1 .3 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/></svg>
                            {coachLoading === 'hint' ? 'Thinking…' : `Reveal Next Hint (Level ${currentHintLevel + 1})`}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* 4. Edge Cases Section */}
                {edgeResult && (coachFilter === 'all' || coachFilter === 'edge') && (
                  <div className="coach-result">
                    <div className="info-section">
                      <div className="section-label">
                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{marginRight: '4px'}}><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                        Edge Cases Detected
                      </div>
                      {(edgeResult.edge_cases || []).map((ec, i) => (
                        <div key={i} className="edge-case-item">
                          <span className={`handled-tag ${ec.handled ? 'handled-yes' : 'handled-no'}`}>
                            {ec.handled ? 'Handled' : 'Missing'}
                          </span>
                          <div>
                            <div className="edge-case-name">{ec.case}</div>
                            <div className="edge-case-suggestion">{ec.suggestion}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="info-section alt-section">
                      <div className="section-label alt-label">
                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{marginRight: '4px'}}><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg>
                        Constraints Critique
                      </div>
                      <div className="section-content">{edgeResult.constraints_critique}</div>
                    </div>
                  </div>
                )}

                {/* 5. Custom Q&A Section */}
                {askResults.length > 0 && (coachFilter === 'all' || coachFilter === 'ask') && (
                  <div className="coach-result" style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {askResults.map((item) => (
                      <div key={item.id} className="info-section alt-section">
                        <div className="section-label alt-label">
                          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{marginRight: '4px'}}><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                          Tutor Q&A Response
                        </div>
                        {item.question && (
                          <div className="ask-question" style={{ fontWeight: '600', color: '#e4e4e7', marginBottom: '6px' }}>Q: {item.question}</div>
                        )}
                        <div className="section-content" style={{ whiteSpace: 'pre-wrap' }}>{item.answer}</div>
                      </div>
                    ))}
                  </div>
                )}

              </div>
            )}

            {/* Ask a question */}
            {!coachLoading && !loading && (
              <div className="ask-block">
                <div className="section-heading" style={{ marginTop: '8px' }}>Ask a custom question</div>
                <textarea
                  className="ask-input"
                  rows={2}
                  placeholder="e.g. Why is my two-pointer approach failing on sorted inputs?"
                  value={askInput}
                  onChange={(e) => setAskInput(e.target.value)}
                />
                <button
                  className="coach-btn"
                  disabled={!askInput.trim() || !!coachLoading}
                  onClick={runAskHelp}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{marginRight: '6px', verticalAlign: 'middle'}}><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                  Ask Tutor
                </button>
              </div>
            )}

            {/* Personal Problem Notes & Rating */}
            {!coachLoading && !loading && (
              <div className="info-section alt-section" style={{ marginTop: '14px', background: '#18181b', border: '1px solid #27272a', borderRadius: '8px', padding: '10px 12px' }}>
                <div className="section-label alt-label" style={{ color: '#fbbf24', display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <span>📝 Personal Notes & Rating</span>
                  {savingNotesStatus && <span style={{ fontSize: '10px', color: '#4ade80' }}>✓ Saved to CSV</span>}
                </div>
                <div style={{ display: 'flex', gap: '8px', marginBottom: '8px', alignItems: 'center' }}>
                  <span style={{ fontSize: '11px', color: '#a1a1aa' }}>Difficulty Flag:</span>
                  <select
                    value={personalDifficultyInput}
                    onChange={(e) => {
                      setPersonalDifficultyInput(e.target.value);
                      saveNotes(userNotesInput, e.target.value);
                    }}
                    style={{ flex: 1, background: '#09090b', color: '#f4f4f5', border: '1px solid #3f3f46', borderRadius: '6px', padding: '4px 8px', fontSize: '11px', cursor: 'pointer' }}
                  >
                    <option value="">Not Rated</option>
                    <option value="Hard for me">🔥 Hard for me</option>
                    <option value="Tricky Edge Cases">⚠️ Tricky Edge Cases</option>
                    <option value="Medium">⚡ Medium</option>
                    <option value="Easy">✅ Easy</option>
                  </select>
                </div>
                <textarea
                  className="ask-input"
                  rows={2}
                  placeholder="Add custom notes or comments for this problem (saved to CSV)..."
                  value={userNotesInput}
                  onChange={(e) => {
                    setUserNotesInput(e.target.value);
                    saveNotes(e.target.value, personalDifficultyInput);
                  }}
                  style={{ fontSize: '11px' }}
                />
              </div>
            )}
          </div>
        )}

        {/* TAB 3: RECOMMENDATION */}
        {activeTab === 'recommendation' && (
          <div>
            {/* Company Tag Filter (Tier 1.1) */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px', background: '#141416', padding: '8px 12px', borderRadius: '8px', border: '1px solid #27272a' }}>
              <span style={{ fontSize: '11px', color: '#a1a1aa' }}>🏢 Target Company:</span>
              <select
                value={selectedCompany}
                onChange={(e) => {
                  setSelectedCompany(e.target.value);
                  fetchRecommendation(e.target.value);
                }}
                style={{ background: '#18181b', color: '#f4f4f5', border: '1px solid #3f3f46', borderRadius: '6px', padding: '4px 8px', fontSize: '12px', cursor: 'pointer' }}
              >
                <option value="">All Companies</option>
                {companies.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>

            {focusTopic && (
              <div className="rec-focus-note">
                <span>🎯 Focus Topic: <strong>{focusTopic}</strong></span>
                <button className="focus-change-btn-inline" onClick={() => setFocus('')}>✕</button>
              </div>
            )}
            
            <h4 className="section-heading">Adaptive Recommendations</h4>
            {recommendation && recommendation.recommendations ? (
              <div className="rec-list-container">
                {recommendation.recommendations.map((rec) => {
                  const recTopics = rec.topics ? rec.topics.split(',').map(t => t.trim()).filter(Boolean) : [];
                  return (
                    <div key={rec.problem_id} className="rec-item-card">
                      <div className="rec-title-row">
                        <h5 className="rec-title">{rec.title}</h5>
                        <span className={`difficulty-badge ${rec.difficulty.toLowerCase()}`}>
                          {rec.difficulty}
                        </span>
                      </div>
                      <div className="rec-reason">
                        {rec.reason}
                      </div>

                      {recTopics.length > 0 && (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', margin: '8px 0' }}>
                          {recTopics.map(t => (
                            <button
                              key={t}
                              className={`focus-pick-btn ${t === focusTopic ? 'active' : ''}`}
                              onClick={() => setFocus(t === focusTopic ? '' : t)}
                              style={{ fontSize: '10px', padding: '2px 6px', border: '1px solid #27272a', borderRadius: '4px', cursor: 'pointer' }}
                            >
                              🎯 {t === focusTopic ? 'Focused' : `Focus on ${t}`}
                            </button>
                          ))}
                        </div>
                      )}

                      <a
                        className="rec-item-link"
                        href={rec.url}
                        target="_top"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                        Attempt Problem
                      </a>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="empty-state">Loading recommendations...</div>
            )}

            {/* Spaced Repetition Review Section */}
            <div className="review-section">
              <h4 className="section-heading" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                Spaced Repetition Reviews
              </h4>
              {recommendation && recommendation.reviews ? (
                recommendation.reviews.length > 0 ? (
                  recommendation.reviews.map((rev) => {
                    const revTopics = rev.topics ? rev.topics.split(',').map(t => t.trim()).filter(Boolean) : [];
                    return (
                      <div key={rev.problem_id} className="review-card">
                        <div className="review-info">
                          <div className="review-title-row">
                            <span className="review-title">{rev.title}</span>
                            <span className={`difficulty-badge ${rev.difficulty.toLowerCase()}`}>
                              {rev.difficulty}
                            </span>
                          </div>
                          <div className="review-meta">
                            <span className={`review-badge stage-${rev.stage}`}>
                              Review {rev.stage} ({rev.stage === 1 ? '3d' : rev.stage === 2 ? '7d' : '14d'})
                            </span>
                          </div>
                          {revTopics.length > 0 && (
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '6px' }}>
                              {revTopics.map(t => (
                                <button
                                  key={t}
                                  className={`focus-pick-btn ${t === focusTopic ? 'active' : ''}`}
                                  onClick={() => setFocus(t === focusTopic ? '' : t)}
                                  style={{ fontSize: '9px', padding: '2px 5px', border: '1px solid #27272a', borderRadius: '4px', cursor: 'pointer' }}
                                >
                                  🎯 {t === focusTopic ? 'Focused' : `Focus on ${t}`}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                        <a
                          className="review-action-btn"
                          href={rev.url}
                          target="_top"
                          title="Attempt Review"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                        </a>
                      </div>
                    );
                  })
                ) : (
                  <div className="success-card">
                    <div className="success-card-icon">
                      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                    </div>
                    <div className="success-card-content">
                      <span className="success-card-title">All Caught Up!</span>
                      <span className="success-card-text">No problems are due for spaced repetition review today. Keep solving to build your queue.</span>
                    </div>
                  </div>
                )
              ) : (
                <div className="empty-state">Loading reviews...</div>
              )}
            </div>
          </div>
        )}

        {/* TAB 4: HISTORY SYNC */}
        {activeTab === 'history' && (
          <div>
            <h4 className="section-heading">LeetCode History Sync</h4>
            <p className="coach-intro">
              Synchronize your historical solved problems from LeetCode to map your topic mastery levels.
            </p>

            <button
              className={`coach-btn ${syncStatus && syncStatus.phase !== 'done' && syncStatus.phase !== 'error' ? 'loading' : ''}`}
              disabled={!!syncStatus && ['fetching', 'syncing'].includes(syncStatus.phase)}
              onClick={runHistorySync}
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{marginRight: '6px', verticalAlign: 'middle'}}><path d="M21.5 2v6h-6"/><path d="M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>
              {syncStatus && ['fetching', 'syncing'].includes(syncStatus.phase)
                ? 'Syncing history…'
                : 'Sync All LeetCode History'}
            </button>

            {/* Weekly Journal Export (Tier 5.1) */}
            <button
              className="coach-btn secondary"
              style={{ marginTop: '10px', width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
              onClick={exportWeeklyJournal}
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              Export Weekly Mistake Journal (.md)
            </button>

            {/* Solved Problems Spreadsheet Export (.csv) */}
            <div className="info-section alt-section" style={{ marginTop: '12px', background: '#18181b', border: '1px solid #27272a', padding: '10px 12px', borderRadius: '8px' }}>
              <div className="section-label alt-label" style={{ color: '#60a5fa', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', fontWeight: '600' }}>
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
                Export Solved Problems Spreadsheet (.csv)
              </div>
              <div style={{ display: 'flex', gap: '8px', marginTop: '8px', alignItems: 'center' }}>
                <select
                  value={csvTimeframe}
                  onChange={(e) => setCsvTimeframe(e.target.value)}
                  style={{ flex: 1, background: '#09090b', color: '#f4f4f5', border: '1px solid #3f3f46', borderRadius: '6px', padding: '6px 8px', fontSize: '11px', cursor: 'pointer' }}
                >
                  <option value="current_week">Current Week (Past 7 Days)</option>
                  <option value="past_30_days">Past 30 Days</option>
                  <option value="all_time">All Solved Problems</option>
                </select>
                <button
                  className={`coach-btn ${exportingCsv ? 'loading' : ''}`}
                  style={{ flex: 'none', padding: '6px 12px', fontSize: '11px' }}
                  disabled={exportingCsv}
                  onClick={exportSolvedCsv}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{marginRight: '4px', verticalAlign: 'middle'}}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                  {exportingCsv ? 'Exporting…' : 'Download .csv'}
                </button>
              </div>
            </div>

            {syncStatus && (
              <div className={`sync-card ${syncStatus.phase === 'error' ? 'sync-error' : ''}`}>
                <div className="sync-message">{syncStatus.message}</div>
                {syncStatus.counts && (
                  <div className="sync-stats">
                    {syncStatus.counts.fetched !== undefined && (
                      <div className="sync-stat">
                        <span className="sync-stat-num">{syncStatus.counts.fetched}</span>
                        <span className="sync-stat-label">Fetched</span>
                      </div>
                    )}
                    <div className="sync-stat">
                      <span className="sync-stat-num">{syncStatus.counts.synced}</span>
                      <span className="sync-stat-label">Synced</span>
                    </div>
                    <div className="sync-stat">
                      <span className="sync-stat-num">{syncStatus.counts.topics}</span>
                      <span className="sync-stat-label">Topics</span>
                    </div>
                    {syncStatus.counts.new_topics !== undefined && (
                      <div className="sync-stat">
                        <span className="sync-stat-num">{syncStatus.counts.new_topics}</span>
                        <span className="sync-stat-label">New</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Analysis card: shown after sync completes */}
            {analysisData && (
              <div className="analysis-card">
                <h4 className="section-heading" style={{ margin: '0 0 14px 0' }}>LeetCode Profile Overview</h4>

                {/* Difficulty breakdown */}
                <div className="diff-bar">
                  <div className="diff-segment diff-easy" style={{ flex: Math.max(1, analysisData.difficulty_breakdown.Easy || 0) }} />
                  <div className="diff-segment diff-medium" style={{ flex: Math.max(1, analysisData.difficulty_breakdown.Medium || 0) }} />
                  <div className="diff-segment diff-hard" style={{ flex: Math.max(1, analysisData.difficulty_breakdown.Hard || 0) }} />
                </div>
                <div className="diff-labels">
                  <span className="diff-label-easy">{analysisData.difficulty_breakdown.Easy || 0} Easy</span>
                  <span className="diff-label-medium">{analysisData.difficulty_breakdown.Medium || 0} Medium</span>
                  <span className="diff-label-hard">{analysisData.difficulty_breakdown.Hard || 0} Hard</span>
                </div>
                <div className="total-solved-line">Total Solved Problems: <strong>{analysisData.total_solved}</strong></div>

                {/* Top topics */}
                <div className="analysis-section">
                  <div className="section-label">
                    <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{marginRight: '4px'}}><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                    Top Covered Topics
                  </div>
                  <div className="topic-chips">
                    {(analysisData.top_topics || []).slice(0, 8).map((t) => (
                      <span key={t.topic} className="topic-chip">
                        {t.topic} <span className="chip-count">{t.solved_count}</span>
                      </span>
                    ))}
                  </div>
                </div>

                {/* Weakest topics */}
                {analysisData.weak_topics && analysisData.weak_topics.length > 0 && (
                  <div className="analysis-section">
                    <div className="section-label" style={{ color: '#fb7185' }}>
                      <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{marginRight: '4px'}}><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                      Weakest Mastery Areas
                    </div>
                    <div className="weak-list">
                      {analysisData.weak_topics.map((t) => (
                        <div key={t.topic} className="weak-item">
                          <span className="weak-topic-name">{t.topic}</span>
                          <div className="weak-item-right">
                            <span className="weak-score" style={{ marginRight: '6px' }}>
                              {t.badge !== 'None' ? `${getBadgeEmoji(t.badge)} ${t.badge}` : '🔒 Locked'}
                            </span>
                            <button
                              className="focus-pick-btn"
                              onClick={() => setFocus(t.topic)}
                              title="Focus on this topic"
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                              Focus
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="tutor-footer">
        <span>
          <span className={`status-dot ${backendOnline ? 'online' : backendOnline === false ? 'offline' : ''}`} />
          {backendOnline === null ? 'Connecting…' : backendOnline ? 'Online' : 'Offline'}
        </span>
        {backendOnline && (
          <span style={{ fontSize: '10px', color: '#a1a1aa' }}>
            AI Daily Limit: {aiQuota.limit - aiQuota.used}/{aiQuota.limit} left
          </span>
        )}
        <span style={{color:'#27272a'}}>Kode v1</span>
      </div>
    </div>
  );
}
