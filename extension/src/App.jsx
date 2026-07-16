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
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm1 14h-2v-2h2zm0-4h-2V7h2z"/>
        </svg>
      </div>
    );
  }

  return (
    <div id="dsa-tutor-panel-container">
      {/* Header */}
      <div className="tutor-header">
        <h3 className="tutor-title">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: '#818cf8' }}>
            <polygon points="12 2 2 7 12 12 22 7 12 2" />
            <polyline points="2 17 12 22 22 17" />
            <polyline points="2 12 12 17 22 12" />
          </svg>
          DSA Tutor Agent
        </h3>
        <button className="close-btn" onClick={() => setIsOpen(false)}>
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
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
          Mastery
        </button>
        <button
          className={`tab-btn ${activeTab === 'coach' ? 'active' : ''}`}
          onClick={() => setActiveTab('coach')}
        >
          Code Coach
        </button>
        <button
          className={`tab-btn ${activeTab === 'recommendation' ? 'active' : ''}`}
          onClick={() => setActiveTab('recommendation')}
        >
          Next Problem
        </button>
        <button
          className={`tab-btn ${activeTab === 'history' ? 'active' : ''}`}
          onClick={() => setActiveTab('history')}
        >
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
                    <span>Score: {(data.mastery_score * 100).toFixed(0)}%</span>
                    <button
                      className={`focus-pick-btn ${data.topic === focusTopic ? 'active' : ''}`}
                      onClick={() => setFocus(data.topic)}
                      title={data.topic === focusTopic ? 'Remove focus' : 'Set as focus topic'}
                    >
                      {data.topic === focusTopic ? '★ Focused' : '☆ Focus'}
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
              Ask the tutor about the code currently in your editor. Each action analyzes your live submission.
            </p>

            {/* Action buttons */}
            <div className="coach-actions">
              <button
                className={`coach-btn ${coachLoading === 'approach' ? 'loading' : ''}`}
                disabled={!!coachLoading}
                onClick={() => runCoachAction('approach', 'check_approach')}
              >
                {coachLoading === 'approach' ? 'Analyzing…' : 'Analyze Approach'}
              </button>
              <button
                className={`coach-btn secondary ${coachLoading === 'hint' ? 'loading' : ''}`}
                disabled={!!coachLoading}
                onClick={() => runCoachAction('hint', 'get_hint')}
              >
                {coachLoading === 'hint' ? 'Thinking…' : 'Get a Hint'}
              </button>
              <button
                className={`coach-btn secondary ${coachLoading === 'edge' ? 'loading' : ''}`}
                disabled={!!coachLoading}
                onClick={() => runCoachAction('edge', 'get_edge_cases')}
              >
                {coachLoading === 'edge' ? 'Checking…' : 'Check Edge Cases'}
              </button>
            </div>

            {/* Loading / error states */}
            {coachLoading && (
              <div className="loading-container">
                <div className="spinner" />
                <p style={{ margin: 0, fontWeight: 500 }}>Consulting the tutor…</p>
              </div>
            )}
            {coachError && (
              <div className="info-section error-section">
                <div className="section-label error-label">Error</div>
                <div className="section-content">{coachError}</div>
              </div>
            )}

            {/* Live submission auto-diagnosis (kept from the original Diagnosis tab) */}
            {loading && (
              <div className="loading-container">
                <div className="spinner" />
                <p style={{ margin: 0, fontWeight: 500 }}>Analyzing code submission...</p>
                <p className="loading-sub">Consulting local agent diagnostics</p>
              </div>
            )}
            {error && (
              <div className="info-section error-section">
                <div className="section-label error-label">Error</div>
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
                        {coachResult.data.is_optimal ? '✓ Optimal' : '⚠ Can be optimized'}
                      </span>
                    </div>
                    <div className="complexity-row">
                      <div><span className="complexity-label">Your complexity</span><br />{coachResult.data.current_complexity}</div>
                      <div><span className="complexity-label">Optimal</span><br />{coachResult.data.optimal_complexity}</div>
                    </div>
                    <div className="info-section">
                      <div className="section-label">Feedback</div>
                      <div className="section-content">{coachResult.data.feedback}</div>
                    </div>
                    <div className="info-section alt-section">
                      <div className="section-label alt-label">Alternative Approach</div>
                      <div className="section-content">{coachResult.data.alternative_approach}</div>
                    </div>
                  </>
                )}

                {/* Hint */}
                {coachResult.type === 'hint' && (
                  <div className="info-section alt-section">
                    <div className="section-label alt-label">💡 Hint</div>
                    <div className="section-content">{coachResult.data.hint}</div>
                  </div>
                )}

                {/* Edge cases */}
                {coachResult.type === 'edge' && (
                  <>
                    <div className="info-section">
                      <div className="section-label">Edge Cases</div>
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
                      <div className="section-label alt-label">Constraints Critique</div>
                      <div className="section-content">{coachResult.data.constraints_critique}</div>
                    </div>
                  </>
                )}

                {/* Ask help answer */}
                {coachResult.type === 'ask' && (
                  <div className="info-section alt-section">
                    <div className="section-label alt-label">Answer</div>
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
                        {coachResult.data.verdict || 'Submission Verdict'}
                      </span>
                      {coachResult.data.verdict !== 'Accepted' && coachResult.data.root_cause_category && CATEGORY_MAP[coachResult.data.root_cause_category] && (
                        <span
                          className="category-tag"
                          style={{
                            color: CATEGORY_MAP[coachResult.data.root_cause_category].color,
                            borderColor: `${CATEGORY_MAP[coachResult.data.root_cause_category].color}40`,
                            background: `${CATEGORY_MAP[coachResult.data.root_cause_category].color}15`
                          }}
                        >
                          {CATEGORY_MAP[coachResult.data.root_cause_category].emoji} {CATEGORY_MAP[coachResult.data.root_cause_category].label}
                        </span>
                      )}
                    </div>
                    <div className="info-section">
                      <div className="section-label">Root Cause Analysis</div>
                      <div className="section-content">{coachResult.data.explanation}</div>
                    </div>
                    {coachResult.data.suggested_action && (
                      <div className="info-section alt-section">
                        <div className="section-label alt-label">Suggested Action</div>
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
                <div className="section-heading" style={{ marginTop: '8px' }}>Ask a question</div>
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
                🎯 Focusing on: <strong>{focusTopic}</strong>
                <button className="focus-change-btn-inline" onClick={() => setFocus('')}>✕</button>
              </div>
            )}
            <h4 className="section-heading">Adaptive Recommendation</h4>
            {recommendation ? (
              <div className="rec-card">
                <div className="rec-title-row">
                  <h5 className="rec-title">{recommendation.title}</h5>
                  <span className={`difficulty-badge ${recommendation.difficulty.toLowerCase()}`}>
                    {recommendation.difficulty}
                  </span>
                </div>
                <div className="rec-reason">
                  <strong>Why this problem:</strong><br />
                  {recommendation.reason}
                </div>
                <a
                  className="rec-link"
                  href={recommendation.url}
                  target="_top" /* Use _top to navigate the outer LeetCode frame */
                >
                  Attempt Problem
                </a>
              </div>
            ) : (
              <div className="empty-state">Loading recommendation...</div>
            )}
          </div>
        )}

        {/* TAB 4: HISTORY SYNC */}
        {activeTab === 'history' && (
          <div>
            <h4 className="section-heading">LeetCode History Sync</h4>
            <p className="coach-intro">
              Import <strong>all</strong> your LeetCode solved problems so the tutor knows what you've already covered. This registers every solved problem and adds their topics to your mastery tracker without inflating your scores.
            </p>

            <button
              className={`coach-btn ${syncStatus && syncStatus.phase !== 'done' && syncStatus.phase !== 'error' ? 'loading' : ''}`}
              disabled={!!syncStatus && ['fetching', 'syncing'].includes(syncStatus.phase)}
              onClick={runHistorySync}
            >
              {syncStatus && ['fetching', 'syncing'].includes(syncStatus.phase)
                ? 'Syncing…'
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
                        <span className="sync-stat-label">New Topics</span>
                      </div>
                    )}
                    {syncStatus.counts.seeded_topics !== undefined && (
                      <div className="sync-stat">
                        <span className="sync-stat-num">{syncStatus.counts.seeded_topics}</span>
                        <span className="sync-stat-label">Seeded</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Analysis card: shown after sync completes */}
            {analysisData && (
              <div className="analysis-card">
                <h4 className="section-heading" style={{ margin: '0 0 14px 0' }}>Your LeetCode Profile</h4>

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
                <div className="total-solved-line">Total Solved: <strong>{analysisData.total_solved}</strong></div>

                {/* Top topics */}
                <div className="analysis-section">
                  <div className="section-label">Top Topics</div>
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
                    <div className="section-label" style={{ color: '#f59e0b' }}>Weakest Topics (by mastery)</div>
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
                              ☆ Focus
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
          Backend: {backendOnline === null ? '…' : backendOnline ? 'Online' : 'Offline'}
        </span>
        <span>Manifest v3</span>
      </div>
    </div>
  );
}
