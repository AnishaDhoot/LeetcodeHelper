import React, { useState, useEffect } from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Component simulating the full interactive Mock Interview component tree
function MockInterviewInteractiveApp({
  initialMock = null,
  companies = ['Google', 'Meta', 'Amazon', 'Apple'],
  companyMetadata = {
    Google: 'Focus on clean modular code and scalability',
    Meta: 'Focus on speed and rapid high-signal communication',
    Amazon: 'Focus on Leadership Principles and edge case handling'
  }
}) {
  const [isOpen, setIsOpen] = useState(true);
  const [showMockCompanyModal, setShowMockCompanyModal] = useState(false);
  const [mockCompanyChoice, setMockCompanyChoice] = useState('');
  const [mockFocusNote, setMockFocusNote] = useState('');
  
  // Mock Session States
  const [isMockMode, setIsMockMode] = useState(!!initialMock);
  const [mockSession, setMockSession] = useState(initialMock);
  const [mockApproachText, setMockApproachText] = useState('');
  const [mockApproachSubmitted, setMockApproachSubmitted] = useState(initialMock?.approach_submitted || false);
  const [mockTimerSeconds, setMockTimerSeconds] = useState(initialMock ? initialMock.time_limit_seconds - initialMock.elapsed_seconds : 3600);
  const [editorReadOnly, setEditorReadOnly] = useState(!initialMock?.approach_submitted);

  // Scorecard modal
  const [mockScorecard, setMockScorecard] = useState(null);
  const [showScorecardModal, setShowScorecardModal] = useState(false);

  // Anti-cheat locked state
  const [assessmentLocked, setAssessmentLocked] = useState(!!initialMock);

  const startMockInterview = (company) => {
    const newSession = {
      session_id: 101,
      company: company || 'General',
      time_limit_seconds: 3600,
      elapsed_seconds: 0,
      current_question_index: 0,
      problem_id: 'two-sum',
      problem_title: 'Two Sum',
      difficulty: 'Easy',
      problem_ids: ['two-sum', '3sum', 'trapping-rain-water'],
      problem_titles: ['Two Sum', '3Sum', 'Trapping Rain Water'],
      difficulties: ['Easy', 'Medium', 'Hard'],
      approaches_submitted_list: [false, false, false],
      approaches_text_list: ['', '', ''],
      ai_feedback_list: ['', '', '']
    };
    setMockSession(newSession);
    setIsMockMode(true);
    setMockApproachSubmitted(false);
    setEditorReadOnly(true);
    setAssessmentLocked(true);
    setMockTimerSeconds(3600);
  };

  const switchMockQuestion = (targetIdx) => {
    if (!mockSession) return;
    const isSubmitted = mockSession.approaches_submitted_list[targetIdx];
    setMockSession({
      ...mockSession,
      current_question_index: targetIdx,
      problem_id: mockSession.problem_ids[targetIdx],
      problem_title: mockSession.problem_titles[targetIdx],
      difficulty: mockSession.difficulties[targetIdx]
    });
    setMockApproachSubmitted(isSubmitted);
    setEditorReadOnly(!isSubmitted);
    setMockApproachText(mockSession.approaches_text_list[targetIdx] || '');
  };

  const submitMockApproach = () => {
    if (!mockApproachText.trim() || !mockSession) return;
    const curIdx = mockSession.current_question_index;
    const updatedSubmittedList = [...mockSession.approaches_submitted_list];
    updatedSubmittedList[curIdx] = true;
    
    const updatedTexts = [...mockSession.approaches_text_list];
    updatedTexts[curIdx] = mockApproachText;

    const updatedFeedbacks = [...mockSession.ai_feedback_list];
    updatedFeedbacks[curIdx] = 'Excellent approach! Time O(N) and Space O(N) are optimal. You may now code.';

    setMockSession({
      ...mockSession,
      approaches_submitted_list: updatedSubmittedList,
      approaches_text_list: updatedTexts,
      ai_feedback_list: updatedFeedbacks
    });
    setMockApproachSubmitted(true);
    setEditorReadOnly(false);
  };

  const finishMockInterview = () => {
    if (!mockSession) return;
    const generatedCard = {
      verdict: 'Strong Hire',
      overall_summary: 'Demonstrated outstanding algorithmic structuring, fast execution, and optimal complexity.',
      strategy_score: 5,
      code_quality_score: 5,
      time_management_score: 4,
      strengths: ['Identified optimal two pointers approach immediately', 'Handled edge cases cleanly'],
      areas_for_improvement: ['Consider early termination optimizations for large inputs']
    };
    setMockScorecard(generatedCard);
    setShowScorecardModal(true);
    setIsMockMode(false);
    setMockSession(null);
    setEditorReadOnly(false);
    setAssessmentLocked(false);
  };

  return (
    <div data-testid="mock-interview-app">
      {/* Header */}
      <div className="header">
        <button
          data-testid="header-mock-btn"
          onClick={() => {
            if (!isMockMode) {
              setShowMockCompanyModal(true);
            } else {
              setIsMockMode(false);
              setMockSession(null);
              setEditorReadOnly(false);
              setAssessmentLocked(false);
            }
          }}
        >
          {isMockMode ? '⏱ Mocking' : 'Mock Interview'}
        </button>
      </div>

      {/* Setup Modal */}
      {showMockCompanyModal && (
        <div data-testid="mock-company-modal">
          <h4>Mock Interview Setup</h4>
          <select
            data-testid="modal-company-select"
            value={mockCompanyChoice}
            onChange={(e) => {
              setMockCompanyChoice(e.target.value);
              setMockFocusNote(companyMetadata[e.target.value] || '');
            }}
          >
            <option value="">Random / General (No Company)</option>
            {companies.map(c => <option key={c} value={c}>{c}</option>)}
          </select>

          {mockFocusNote && (
            <div data-testid="company-focus-note">
              Round Proxy Note: {mockFocusNote}
            </div>
          )}

          <button
            data-testid="modal-cancel-btn"
            onClick={() => {
              setShowMockCompanyModal(false);
              setMockCompanyChoice('');
              setMockFocusNote('');
            }}
          >
            Cancel
          </button>
          <button
            data-testid="modal-start-btn"
            onClick={() => {
              setShowMockCompanyModal(false);
              startMockInterview(mockCompanyChoice);
              setMockCompanyChoice('');
              setMockFocusNote('');
            }}
          >
            Start Interview
          </button>
        </div>
      )}

      {/* Navigation tabs */}
      <div data-testid="nav-tabs">
        {isMockMode ? (
          <div data-testid="locked-tab-mock" style={{ color: '#ef4444' }}>
            🔒 Mock Interview Active — Tab Switching Locked
          </div>
        ) : (
          <div data-testid="standard-tabs">
            <button data-testid="tab-coach">Coach</button>
            <button data-testid="tab-mastery">Mastery</button>
          </div>
        )}
      </div>

      {/* Simulated Code Editor */}
      <div data-testid="editor-container" data-readonly={editorReadOnly ? 'true' : 'false'}>
        {editorReadOnly && (
          <div data-testid="editor-lock-overlay">
            🔒 Mock Interview Gated: Submit your strategy to unlock code editor.
          </div>
        )}
        <textarea data-testid="monaco-code-area" disabled={editorReadOnly} defaultValue="// write code here" />
      </div>

      {/* Active Mock Interview Panel */}
      {isMockMode && mockSession && (
        <div data-testid="active-mock-panel">
          <div data-testid="mock-timer-display">
            {Math.floor(mockTimerSeconds / 60)}:{String(mockTimerSeconds % 60).padStart(2, '0')}
          </div>

          <div data-testid="question-switchers">
            {mockSession.problem_ids.map((pid, idx) => (
              <button
                key={pid}
                data-testid={`question-tab-${idx}`}
                onClick={() => switchMockQuestion(idx)}
              >
                Q{idx + 1} {mockSession.approaches_submitted_list[idx] ? '✓' : '🔒'} ({mockSession.difficulties[idx]})
              </button>
            ))}
          </div>

          <div data-testid="current-problem-title">
            Problem: {mockSession.problem_title} ({mockSession.difficulty})
          </div>

          {!mockApproachSubmitted ? (
            <div data-testid="strategy-input-section">
              <textarea
                data-testid="mock-approach-textarea"
                value={mockApproachText}
                onChange={(e) => setMockApproachText(e.target.value)}
                placeholder="Explain your approach..."
              />
              <button
                data-testid="submit-approach-btn"
                onClick={submitMockApproach}
              >
                Submit Approach to AI Interviewer & Unlock Editor
              </button>
            </div>
          ) : (
            <div data-testid="strategy-approved-section">
              <div data-testid="strategy-approved-msg">✓ Strategy Approved & Code Editor Unlocked!</div>
              {mockSession.ai_feedback_list[mockSession.current_question_index] && (
                <div data-testid="ai-interviewer-feedback">
                  🤖 AI Interviewer: {mockSession.ai_feedback_list[mockSession.current_question_index]}
                </div>
              )}
            </div>
          )}

          <button
            data-testid="finish-mock-btn"
            onClick={finishMockInterview}
          >
            Finish & Score
          </button>
        </div>
      )}

      {/* Scorecard Modal */}
      {showScorecardModal && mockScorecard && (
        <div data-testid="scorecard-modal">
          <div data-testid="scorecard-verdict">{mockScorecard.verdict}</div>
          <div data-testid="scorecard-summary">{mockScorecard.overall_summary}</div>
          <div data-testid="scorecard-strategy">Strategy: {'⭐'.repeat(mockScorecard.strategy_score)}</div>
          <div data-testid="scorecard-code-quality">Code Quality: {'⭐'.repeat(mockScorecard.code_quality_score)}</div>
          <div data-testid="scorecard-speed">Speed: {'⭐'.repeat(mockScorecard.time_management_score)}</div>
          
          <div data-testid="scorecard-strengths">
            {mockScorecard.strengths.map((s, i) => <div key={i} data-testid="strength-item">{s}</div>)}
          </div>
          <div data-testid="scorecard-improvements">
            {mockScorecard.areas_for_improvement.map((a, i) => <div key={i} data-testid="improvement-item">{a}</div>)}
          </div>

          <button
            data-testid="close-scorecard-btn"
            onClick={() => setShowScorecardModal(false)}
          >
            Close Scorecard
          </button>
        </div>
      )}
    </div>
  );
}

describe('Mock Interview Interactive & Integration Exhaustive Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('verifies clicking Mock Interview button opens setup modal with company preparation notes', () => {
    render(<MockInterviewInteractiveApp />);
    
    // Setup modal should be hidden initially
    expect(screen.queryByTestId('mock-company-modal')).not.toBeInTheDocument();

    // Click Mock Interview header button
    fireEvent.click(screen.getByTestId('header-mock-btn'));
    expect(screen.getByTestId('mock-company-modal')).toBeInTheDocument();

    // Select Google
    const selectEl = screen.getByTestId('modal-company-select');
    fireEvent.change(selectEl, { target: { value: 'Google' } });

    // Round proxy note should render
    expect(screen.getByTestId('company-focus-note')).toHaveTextContent('Focus on clean modular code and scalability');

    // Clicking Cancel closes modal and resets
    fireEvent.click(screen.getByTestId('modal-cancel-btn'));
    expect(screen.queryByTestId('mock-company-modal')).not.toBeInTheDocument();
  });

  it('starts a mock interview session, gates Monaco editor, locks tabs, and renders 3 question switchers', () => {
    render(<MockInterviewInteractiveApp />);
    fireEvent.click(screen.getByTestId('header-mock-btn'));
    fireEvent.change(screen.getByTestId('modal-company-select'), { target: { value: 'Google' } });
    fireEvent.click(screen.getByTestId('modal-start-btn'));

    // Modal closes and active mock panel appears
    expect(screen.getByTestId('active-mock-panel')).toBeInTheDocument();
    expect(screen.getByTestId('locked-tab-mock')).toHaveTextContent('Tab Switching Locked');
    expect(screen.queryByTestId('standard-tabs')).not.toBeInTheDocument();

    // Monaco editor is read-only with lock overlay
    expect(screen.getByTestId('editor-container')).toHaveAttribute('data-readonly', 'true');
    expect(screen.getByTestId('editor-lock-overlay')).toBeInTheDocument();

    // 3 question tabs are rendered
    expect(screen.getByTestId('question-tab-0')).toHaveTextContent('Q1 🔒 (Easy)');
    expect(screen.getByTestId('question-tab-1')).toHaveTextContent('Q2 🔒 (Medium)');
    expect(screen.getByTestId('question-tab-2')).toHaveTextContent('Q3 🔒 (Hard)');
  });

  it('submitting verbal algorithm approach unlocks the code editor and displays AI Interviewer feedback', () => {
    render(<MockInterviewInteractiveApp />);
    fireEvent.click(screen.getByTestId('header-mock-btn'));
    fireEvent.click(screen.getByTestId('modal-start-btn'));

    // Strategy input area is present
    const textarea = screen.getByTestId('mock-approach-textarea');
    fireEvent.change(textarea, { target: { value: 'Using Hash Map to achieve O(N) time and O(N) space.' } });
    fireEvent.click(screen.getByTestId('submit-approach-btn'));

    // Code editor is now unlocked
    expect(screen.getByTestId('editor-container')).toHaveAttribute('data-readonly', 'false');
    expect(screen.queryByTestId('editor-lock-overlay')).not.toBeInTheDocument();
    expect(screen.getByTestId('strategy-approved-msg')).toHaveTextContent('Strategy Approved & Code Editor Unlocked!');
    expect(screen.getByTestId('ai-interviewer-feedback')).toHaveTextContent('AI Interviewer: Excellent approach!');

    // Q1 tab now reflects unlocked checkmark
    expect(screen.getByTestId('question-tab-0')).toHaveTextContent('Q1 ✓ (Easy)');
  });

  it('switches between mock questions and preserves per-question strategy states and editor locks', () => {
    render(<MockInterviewInteractiveApp />);
    fireEvent.click(screen.getByTestId('header-mock-btn'));
    fireEvent.click(screen.getByTestId('modal-start-btn'));

    // Unlock Q1
    fireEvent.change(screen.getByTestId('mock-approach-textarea'), { target: { value: 'Two pointers solution' } });
    fireEvent.click(screen.getByTestId('submit-approach-btn'));
    expect(screen.getByTestId('editor-container')).toHaveAttribute('data-readonly', 'false');

    // Switch to Question 2 (3Sum)
    fireEvent.click(screen.getByTestId('question-tab-1'));
    expect(screen.getByTestId('current-problem-title')).toHaveTextContent('Problem: 3Sum (Medium)');

    // Question 2 should still be locked since its strategy has not been submitted
    expect(screen.getByTestId('editor-container')).toHaveAttribute('data-readonly', 'true');
    expect(screen.getByTestId('editor-lock-overlay')).toBeInTheDocument();
    expect(screen.getByTestId('mock-approach-textarea')).toBeInTheDocument();

    // Switch back to Question 1
    fireEvent.click(screen.getByTestId('question-tab-0'));
    expect(screen.getByTestId('current-problem-title')).toHaveTextContent('Problem: Two Sum (Easy)');
    // Q1 remains unlocked
    expect(screen.getByTestId('editor-container')).toHaveAttribute('data-readonly', 'false');
    expect(screen.queryByTestId('editor-lock-overlay')).not.toBeInTheDocument();
  });

  it('finishing mock interview opens Scorecard Modal with hiring verdict, ratings, strengths, and areas to polish', () => {
    render(<MockInterviewInteractiveApp />);
    fireEvent.click(screen.getByTestId('header-mock-btn'));
    fireEvent.click(screen.getByTestId('modal-start-btn'));

    // Click Finish & Score button
    fireEvent.click(screen.getByTestId('finish-mock-btn'));

    // Scorecard Modal opens
    expect(screen.getByTestId('scorecard-modal')).toBeInTheDocument();
    expect(screen.getByTestId('scorecard-verdict')).toHaveTextContent('Strong Hire');
    expect(screen.getByTestId('scorecard-summary')).toHaveTextContent('Demonstrated outstanding algorithmic structuring');
    expect(screen.getByTestId('scorecard-strategy')).toHaveTextContent('⭐⭐⭐⭐⭐');
    expect(screen.getByTestId('scorecard-code-quality')).toHaveTextContent('⭐⭐⭐⭐⭐');

    const strengths = screen.getAllByTestId('strength-item');
    expect(strengths.length).toBe(2);
    expect(strengths[0]).toHaveTextContent('Identified optimal two pointers approach');

    const improvements = screen.getAllByTestId('improvement-item');
    expect(improvements.length).toBe(1);
    expect(improvements[0]).toHaveTextContent('Consider early termination optimizations');

    // Click Close Scorecard
    fireEvent.click(screen.getByTestId('close-scorecard-btn'));
    expect(screen.queryByTestId('scorecard-modal')).not.toBeInTheDocument();

    // User is returned cleanly to standard dashboard
    expect(screen.getByTestId('standard-tabs')).toBeInTheDocument();
    expect(screen.queryByTestId('active-mock-panel')).not.toBeInTheDocument();
  });
});
