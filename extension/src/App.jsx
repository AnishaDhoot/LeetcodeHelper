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

  // Code Coach state
  const [coachResult, setCoachResult] = useState(null); // {type, data}
  const [coachLoading, setCoachLoading] = useState(null); // current action id or null
  const [coachError, setCoachError] = useState(null);
  const [askInput, setAskInput] = useState('');

  // History sync state
  const [syncStatus, setSyncStatus] = useState(null); // {phase, message, counts}

  // Backend health state
  const [backendOnline, setBackendOnline] = useState(null); // null=unknown, true/false

  // Focus topic state
  const [focusTopic, setFocusTopic] = useState(null);

  // Topic analysis state (loaded after sync or on mount)
  const [analysisData, setAnalysisData] = useState(null);

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
    setCoachResult(null);
    setCoachLoading(actionId);
    try {
      const ctx = await gatherContext(true);
      chrome.runtime.sendMessage({ action: messageAction, payload: ctx }, (response) => {
        setCoachLoading(null);
        if (response && response.success) {
          setCoachResult({ type: actionId, data: response.data });
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
    setCoachError(null);
    setCoachResult(null);
    setCoachLoading('ask');
    try {
      const ctx = await gatherContext(true);
      const payload = { ...ctx, question: askInput.trim() };
      chrome.runtime.sendMessage({ action: 'ask_help', payload }, (response) => {
        setCoachLoading(null);
        if (response && response.success) {
          setCoachResult({ type: 'ask', data: response.data, question: askInput.trim() });
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

  // Fetch data on mount
  useEffect(() => {
    fetchMastery();
    fetchRecommendation();
    checkBackendHealth();
    fetchFocus();
    fetchAnalysis();

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
        setCoachResult({ type: 'diagnosis', data: diagResult });
        setCoachError(null);
        setCoachLoading(null);
        // Refresh mastery & recommendations as they might have changed
        fetchMastery();
        fetchRecommendation();
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

  const fetchRecommendation = () => {
    chrome.runtime.sendMessage({ action: 'get_recommendation' }, (response) => {
      if (response && response.success) {
        setRecommendation(response.data);
      } else {
        console.error('Failed to fetch recommendation:', response?.error);
      }
    });
  };

  if (!isOpen) {
    return (
      <div className="tutor-trigger" onClick={() => setIsOpen(true)} title="Open DSA Tutor Agent">
        <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/>
        </svg>
      </div>
    );
  }

  return (
    <div id="dsa-tutor-panel-container">
      {/* Header */}
      <div className="tutor-header">
        <h3 className="tutor-title">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: '#a78bfa' }}>
            <polygon points="12 2 2 7 12 12 22 7 12 2" />
            <polyline points="2 17 12 22 22 17" />
            <polyline points="2 12 12 17 22 12" />
          </svg>
          DSA Tutor Agent
        </h3>
        <button className="close-btn" onClick={() => setIsOpen(false)}>
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      {/* Tabs Menu */}
      <div className="tabs-container">
        <button
          className={`tab-btn ${activeTab === 'mastery' ? 'active' : ''}`}
          onClick={() => setActiveTab('mastery')}
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 3v18h18" />
            <path d="m19 9-5 5-4-4-3 3" />
          </svg>
          Mastery
        </button>
        <button
          className={`tab-btn ${activeTab === 'coach' ? 'active' : ''}`}
          onClick={() => setActiveTab('coach')}
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/>
          </svg>
          Coach
        </button>
        <button
          className={`tab-btn ${activeTab === 'recommendation' ? 'active' : ''}`}
          onClick={() => setActiveTab('recommendation')}
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" />
          </svg>
          Next
        </button>
        <button
          className={`tab-btn ${activeTab === 'history' ? 'active' : ''}`}
          onClick={() => setActiveTab('history')}
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21.5 2v6h-6" />
            <path d="M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
          </svg>
          History
        </button>
      </div>

      {/* Content Area */}
      <div className="tutor-content">
        {/* TAB 1: MASTERY OVERVIEW */}
        {activeTab === 'mastery' && (
          <div>
            {/* Focus banner */}
            {focusTopic && (
              <div className="focus-banner">
                <div className="focus-banner-text">
                  <span className="focus-icon">🎯</span>
                  <span>Focus Topic: <strong>{focusTopic}</strong></span>
                </div>
                <button className="focus-change-btn" onClick={() => setFocus('')}>
                  Clear Focus
                </button>
              </div>
            )}

            <h4 className="section-heading">Per-Topic Mastery Levels</h4>
            {masteryData.length === 0 ? (
              <div className="empty-state">
                No topic data loaded. Backend offline or database empty.
              </div>
            ) : (
              masteryData.map((data) => (
                <div
                  key={data.topic}
                  className={`mastery-card ${data.topic === focusTopic ? 'mastery-card-focus' : ''}`}
                >
                  <div className="mastery-header">
                    <span className="mastery-name">{data.topic}</span>
                    <span className="mastery-score">{(data.mastery_score * 100).toFixed(0)}%</span>
                  </div>
                  <div className="progress-bar-bg">
                    <div
                      className="progress-bar-fg"
                      style={{ width: `${data.mastery_score * 100}%` }}
                    />
                  </div>
                  <div className="mastery-meta">
                    <span>Solved: {data.attempts_count}</span>
                    <button
                      className={`focus-pick-btn ${data.topic === focusTopic ? 'active' : ''}`}
                      onClick={() => setFocus(data.topic)}
                      title={data.topic === focusTopic ? 'Remove focus' : 'Set as focus topic'}
                    >
                      {data.topic === focusTopic ? (
                        <>
                          <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                          Focused
                        </>
                      ) : (
                        <>
                          <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                          Focus
                        </>
                      )}
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* TAB 2: CODE COACH */}
        {activeTab === 'coach' && (
          <div>
            <h4 className="section-heading">Code Coach</h4>
            <p className="coach-intro">
              Analyze the code currently inside LeetCode's editor using autonomous diagnostic tools.
            </p>

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
                disabled={!!coachLoading}
                onClick={() => runCoachAction('hint', 'get_hint')}
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{marginRight: '6px', verticalAlign: 'middle'}}><path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A5 5 0 0 0 8 8c0 1 .3 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/></svg>
                {coachLoading === 'hint' ? 'Thinking…' : 'Get a Hint'}
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
                <p style={{ margin: 0, fontWeight: 700, color: '#f1f5f9' }}>Consulting the tutor…</p>
                <p className="loading-sub">Analyzing submission framework context</p>
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
                <p style={{ margin: 0, fontWeight: 700, color: '#f1f5f9' }}>Analyzing code submission...</p>
                <p className="loading-sub">Generating conceptual diagnostics</p>
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

            {/* Results */}
            {!coachLoading && coachResult && (
              <div className="coach-result">
                {/* Approach critique */}
                {coachResult.type === 'approach' && (
                  <>
                    <div className="coach-result-head">
                      <span className={`tag-pill ${coachResult.data.is_optimal ? 'tag-good' : 'tag-bad'}`}>
                        {coachResult.data.is_optimal ? (
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
                        <span>{coachResult.data.current_complexity}</span>
                      </div>
                      <div>
                        <span className="complexity-label">Optimal Complexity</span>
                        <span>{coachResult.data.optimal_complexity}</span>
                      </div>
                    </div>
                    <div className="info-section">
                      <div className="section-label">
                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{marginRight: '4px'}}><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                        Feedback
                      </div>
                      <div className="section-content">{coachResult.data.feedback}</div>
                    </div>
                    <div className="info-section alt-section">
                      <div className="section-label alt-label">
                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{marginRight: '4px'}}><polygon points="5 3 19 12 5 21 5 3"/></svg>
                        Alternative Approach
                      </div>
                      <div className="section-content">{coachResult.data.alternative_approach}</div>
                    </div>
                  </>
                )}

                {/* Hint */}
                {coachResult.type === 'hint' && (
                  <div className="info-section alt-section">
                    <div className="section-label alt-label">
                      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{marginRight: '4px'}}><path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A5 5 0 0 0 8 8c0 1 .3 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/></svg>
                      💡 Conceptual Hint
                    </div>
                    <div className="section-content">{coachResult.data.hint}</div>
                  </div>
                )}

                {/* Edge cases */}
                {coachResult.type === 'edge' && (
                  <>
                    <div className="info-section">
                      <div className="section-label">
                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{marginRight: '4px'}}><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                        Edge Cases Detected
                      </div>
                      {(coachResult.data.edge_cases || []).map((ec, i) => (
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
                      <div className="section-content">{coachResult.data.constraints_critique}</div>
                    </div>
                  </>
                )}

                {/* Ask help answer */}
                {coachResult.type === 'ask' && (
                  <div className="info-section alt-section">
                    <div className="section-label alt-label">
                      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{marginRight: '4px'}}><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                      Tutor Response
                    </div>
                    {coachResult.question && (
                      <div className="ask-question">Q: {coachResult.question}</div>
                    )}
                    <div className="section-content">{coachResult.data.answer}</div>
                  </div>
                )}

                {/* Auto-diagnosis on failed submission */}
                {coachResult.type === 'diagnosis' && (
                  <>
                    <div className="diagnosis-badges">
                      <span className={`verdict-badge ${coachResult.data.verdict === 'Accepted' ? 'success' : 'failure'}`}>
                        {coachResult.data.verdict === 'Accepted' ? (
                          <>
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" style={{marginRight: '6px'}}><polyline points="20 6 9 17 4 12"/></svg>
                            Accepted
                          </>
                        ) : (
                          <>
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{marginRight: '6px'}}><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                            {coachResult.data.verdict || 'Failed'}
                          </>
                        )}
                      </span>
                      {coachResult.data.verdict !== 'Accepted' && coachResult.data.root_cause_category && CATEGORY_MAP[coachResult.data.root_cause_category] && (
                        <span
                          className="category-tag"
                          style={{
                            color: CATEGORY_MAP[coachResult.data.root_cause_category].color,
                            borderColor: `${CATEGORY_MAP[coachResult.data.root_cause_category].color}30`,
                            background: `${CATEGORY_MAP[coachResult.data.root_cause_category].color}12`
                          }}
                        >
                          {CATEGORY_MAP[coachResult.data.root_cause_category].emoji} {CATEGORY_MAP[coachResult.data.root_cause_category].label}
                        </span>
                      )}
                    </div>
                    <div className="info-section">
                      <div className="section-label">
                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{marginRight: '4px'}}><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                        Root Cause Analysis
                      </div>
                      <div className="section-content">{coachResult.data.explanation}</div>
                    </div>
                    {coachResult.data.suggested_action && (
                      <div className="info-section alt-section">
                        <div className="section-label alt-label">
                          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{marginRight: '4px'}}><polygon points="5 3 19 12 5 21 5 3"/></svg>
                          Suggested Action
                        </div>
                        <div className="section-content">{coachResult.data.suggested_action}</div>
                      </div>
                    )}
                  </>
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
          </div>
        )}

        {/* TAB 3: RECOMMENDATION */}
        {activeTab === 'recommendation' && (
          <div>
            {focusTopic && (
              <div className="rec-focus-note">
                <span>🎯 Focus Topic: <strong>{focusTopic}</strong></span>
                <button className="focus-change-btn-inline" onClick={() => setFocus('')}>✕</button>
              </div>
            )}
            
            <h4 className="section-heading">Adaptive Recommendations</h4>
            {recommendation && recommendation.recommendations ? (
              <div className="rec-list-container">
                {recommendation.recommendations.map((rec) => (
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
                    <a
                      className="rec-item-link"
                      href={rec.url}
                      target="_top"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                      Attempt Problem
                    </a>
                  </div>
                ))}
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
                  recommendation.reviews.map((rev) => (
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
                  ))
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
                  <div className="diff-segment diff-easy" style={{ flex: Math.max(1, analysisData.difficulty_breakdown.Easy || 0) }}>
                    {analysisData.difficulty_breakdown.Easy || 0} Easy
                  </div>
                  <div className="diff-segment diff-medium" style={{ flex: Math.max(1, analysisData.difficulty_breakdown.Medium || 0) }}>
                    {analysisData.difficulty_breakdown.Medium || 0} Med
                  </div>
                  <div className="diff-segment diff-hard" style={{ flex: Math.max(1, analysisData.difficulty_breakdown.Hard || 0) }}>
                    {analysisData.difficulty_breakdown.Hard || 0} Hard
                  </div>
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
                            <span className="weak-score">{(t.mastery_score * 100).toFixed(0)}%</span>
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
          Backend: {backendOnline === null ? 'Checking…' : backendOnline ? 'Online' : 'Offline'}
        </span>
        <span>Manifest v3</span>
      </div>
    </div>
  );
}
