import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

// 1. Create container for the extension panel inside the Shadow DOM (to prevent style clashing)
const rootId = 'dsa-tutor-panel-root';
let rootDiv = document.getElementById(rootId);

if (!rootDiv) {
  rootDiv = document.createElement('div');
  rootDiv.id = rootId;
  rootDiv.style.position = 'fixed';
  rootDiv.style.top = '0';
  rootDiv.style.right = '0';
  rootDiv.style.width = '0';
  rootDiv.style.height = '0';
  rootDiv.style.zIndex = '2147483647';
  rootDiv.style.pointerEvents = 'none';
  (document.documentElement || document.body).appendChild(rootDiv);

  const shadowRoot = rootDiv.attachShadow({ mode: 'open' });

  // Create wrapper inside shadow root
  const reactContainer = document.createElement('div');
  reactContainer.id = 'dsa-tutor-react-container';
  reactContainer.style.pointerEvents = 'auto';
  shadowRoot.appendChild(reactContainer);

  // Load styling inside Shadow DOM
  const styleLink = document.createElement('link');
  styleLink.rel = 'stylesheet';
  styleLink.href = chrome.runtime.getURL('content.css');
  shadowRoot.appendChild(styleLink);

  // Render React App
  ReactDOM.createRoot(reactContainer).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}

// 2. Inject injected.js into the main page context to access window.monaco
const injectScript = () => {
  const scriptId = 'dsa-tutor-injected-script';
  if (document.getElementById(scriptId)) return;

  const script = document.createElement('script');
  script.id = scriptId;
  script.src = chrome.runtime.getURL('injected.js');
  (document.head || document.documentElement).appendChild(script);
};

injectScript();

// ============================================================================
// 3. On-demand context scrapers (used by the Code Coach tab in React)
//    Exposed on window.dsaTutor so the React layer can await them directly.
// ============================================================================

// Request the current editor code from the page-context script (injected.js).
// Returns a Promise<string> resolving to the Monaco editor contents.
const getCodeFromPage = (timeoutMs = 300) => {
  return new Promise((resolve) => {
    let settled = false;
    const onCodeReceived = (event) => {
      if (event.source !== window || !event.data || event.data.type !== 'CODE_VALUE') return;
      window.removeEventListener('message', onCodeReceived);
      if (settled) return;
      settled = true;
      resolve(event.data.code || '');
    };
    window.addEventListener('message', onCodeReceived);
    window.postMessage({ type: 'REQUEST_CODE' }, window.location.origin);

    // Fallback: resolve with empty string if injected.js never replies.
    setTimeout(() => {
      if (settled) return;
      settled = true;
      window.removeEventListener('message', onCodeReceived);
      resolve('');
    }, timeoutMs);
  });
};

// Detect the currently selected language from LeetCode's editor toolbar.
const scrapeCurrentLanguage = () => {
  try {
    // LeetCode renders the active language as a button label in the editor header.
    const langBtn = document.querySelector(
      '[class*="editor-language"] button, [data-mode], [class*="lang-selector"] button, button[aria-haspopup="listbox"]'
    );
    if (langBtn) {
      const txt = (langBtn.getAttribute('data-mode') || langBtn.textContent || '').trim();
      if (txt) return txt;
    }
    // Fallback: scan the editor header container text for known languages.
    const header = document.querySelector('[class*="header"] [class*="right"]');
    if (header) {
      const known = ['C++', 'Java', 'Python', 'Python3', 'JavaScript', 'TypeScript', 'Go', 'Rust', 'Ruby', 'C', 'C#', 'Swift', 'Kotlin', 'PHP', 'Scala'];
      const text = header.textContent || '';
      for (const k of known) {
        if (text.includes(k)) return k;
      }
    }
  } catch (e) {
    console.warn('[DSA Tutor Content] Language scrape failed:', e);
  }
  return 'python3';
};

// Scrape the problem's constraints list from the description pane.
const scrapeConstraints = () => {
  try {
    // Look for a heading containing "Constraints", then collect the following list items.
    const headings = Array.from(document.querySelectorAll('p, li, strong, h2, h3, div'));
    let constraintStart = null;
    for (const el of headings) {
      const t = (el.textContent || '').trim();
      if (/^Constraints:?$/i.test(t) && el.getBoundingClientRect().height > 0) {
        constraintStart = el;
        break;
      }
    }
    if (constraintStart) {
      // Constraints are typically a <ul> immediately after the heading, or siblings.
      let list = constraintStart.nextElementSibling?.querySelector?.('li')
        ? constraintStart.nextElementSibling
        : null;
      if (!list) {
        // Walk forward through siblings collecting list items.
        list = constraintStart.parentElement;
      }
      const items = list ? list.querySelectorAll('li') : [];
      const out = [];
      items.forEach((li) => {
        const text = (li.textContent || '').trim();
        // Only keep items that look like constraints (contain digits / comparisons / m/n).
        if (text && (/\d/.test(text) || /<=|>=|<|>/.test(text))) {
          out.push(text);
        }
      });
      if (out.length > 0) return out;
    }
  } catch (e) {
    console.warn('[DSA Tutor Content] Constraints scrape failed:', e);
  }
  return null;
};

// Extract current problem identity from URL + document title.
const scrapeProblemIdentity = () => {
  const urlMatch = window.location.href.match(/problems\/([^/]+)/);
  const problemId = urlMatch ? urlMatch[1] : 'unknown-problem';
  const docTitle = document.title || '';
  const problemTitle = docTitle.split('-')[0].trim() || problemId;
  return { problemId, problemTitle };
};

// ============================================================================
// 4. Observe the LeetCode DOM for submission verdicts (auto-diagnosis)
// ============================================================================

let lastTriggerTime = 0; // Prevents repeated triggers for the same verdict burst

const scrapeFailingTestcase = () => {
  let input = '';
  let expected = '';
  let actual = '';

  // Scan text elements on the page for labels
  const allElements = Array.from(document.querySelectorAll('div, span, p'));
  for (const el of allElements) {
    const text = el.textContent?.trim();
    if (text === 'Input' || text === 'Input =') {
      const next = el.nextElementSibling || el.parentElement?.nextElementSibling;
      if (next) input = next.textContent?.trim() || '';
    } else if (text === 'Output' || text === 'Output =' || text === 'Use Result') {
      const next = el.nextElementSibling || el.parentElement?.nextElementSibling;
      if (next) actual = next.textContent?.trim() || '';
    } else if (text === 'Expected' || text === 'Expected =') {
      const next = el.nextElementSibling || el.parentElement?.nextElementSibling;
      if (next) expected = next.textContent?.trim() || '';
    }
  }

  if (input || expected || actual) {
    return [{ input, expected, actual }];
  }
  return null;
};

const handleVerdictDetected = async (verdict, node) => {
  console.log(`[DSA Tutor Content] Verdict detected: ${verdict}`);

  const { problemId, problemTitle } = scrapeProblemIdentity();

  // Update React UI state to Loading
  window.dsaTutor?.setLoading(true);

  if (verdict === 'Accepted') {
    // For Accepted submissions, just notify backend to update mastery score (no LLM logic needed)
    chrome.runtime.sendMessage({
      action: 'analyze_submission',
      payload: {
        problem_id: problemId,
        problem_title: problemTitle,
        code: '',
        language: scrapeCurrentLanguage(),
        verdict: 'Accepted',
        time_taken_seconds: 0,
        hints_used: window.dsaTutor?.hintsUsed || 0
      }
    }, (response) => {
      if (response && response.success) {
        window.dsaTutor?.setDiagnosis({
          verdict: 'Accepted',
          explanation: 'Submission succeeded! Great job.',
          suggested_action: 'Proceed to your next recommended problem.'
        });
      } else {
        window.dsaTutor?.setError(response?.error || 'Failed to record success submission.');
      }
    });
    return;
  }

  // For failed submissions, request editor code from page-context (injected.js)
  const code = await getCodeFromPage();
  if (!code) {
    window.dsaTutor?.setError('Failed to retrieve code from Monaco editor: empty code');
    return;
  }

  const testCases = scrapeFailingTestcase();

  // Check for compile errors or red alert text in LeetCode page to pass as error details
  let errorDetails = '';
  const errEls = document.querySelectorAll('[class*="compile-error"], [class*="err-msg"]');
  if (errEls.length > 0) {
    errorDetails = Array.from(errEls).map(el => el.textContent?.trim()).join('\n');
  }

  // Call background script API analysis endpoint
  chrome.runtime.sendMessage({
    action: 'analyze_submission',
    payload: {
      problem_id: problemId,
      problem_title: problemTitle,
      code: code,
      language: scrapeCurrentLanguage(),
      verdict: verdict,
      error_details: errorDetails,
      test_cases: testCases,
      hints_used: window.dsaTutor?.hintsUsed || 0
    }
  }, (response) => {
    if (response && response.success) {
      window.dsaTutor?.setDiagnosis({
        verdict: verdict,
        root_cause_category: response.data.root_cause_category,
        explanation: response.data.explanation,
        suggested_action: response.data.suggested_action
      });
    } else {
      window.dsaTutor?.setError(response?.error || 'Failed to diagnose submission.');
    }
  });
};

let lastSubmitClickTimestamp = 0;

// Mouse click detection for Submit button
document.addEventListener('click', (e) => {
  const btn = e.target ? e.target.closest('button, [data-e2e-locator="console-submit-button"], [data-cypress="submit-code-btn"]') : null;
  if (!btn) return;
  const txt = (btn.textContent || '').trim().toLowerCase();
  const locator = (btn.getAttribute('data-e2e-locator') || '').toLowerCase();
  const testId = (btn.getAttribute('data-testid') || '').toLowerCase();
  
  // STRICT CHECK: ONLY track clicks on the actual "Submit" button, NOT "Run" or "Run Code"
  const isSubmitBtn = (
    locator.includes('submit') ||
    testId.includes('submit') ||
    txt === 'submit' ||
    txt === 'submit code' ||
    (txt.includes('submit') && !txt.includes('run'))
  );

  if (isSubmitBtn) {
    lastSubmitClickTimestamp = Date.now();
  }
}, true);

// Keyboard shortcut detection (Ctrl+Enter / Cmd+Enter on LeetCode)
document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    lastSubmitClickTimestamp = Date.now();
  }
}, true);

// SPA URL change listener to keep problem state in sync
let lastHref = window.location.href;
const checkUrlChange = () => {
  if (window.location.href !== lastHref) {
    lastHref = window.location.href;
    window.dispatchEvent(new CustomEvent('dsa-tutor-url-change', { detail: { url: lastHref } }));
  }
};
window.addEventListener('popstate', checkUrlChange);
window.addEventListener('hashchange', checkUrlChange);
setInterval(checkUrlChange, 1000);

const processedVerdictNodes = new WeakSet();
const lastDetectedSubmissions = new Map();

const checkNodeForVerdict = (node) => {
  if (!node || !(node instanceof HTMLElement)) return;
  if (processedVerdictNodes.has(node) || node.dataset?.dsaProcessed === "true") return;

  const text = node.textContent?.trim() || '';
  if (!text) return;

  const verdicts = ['Accepted', 'Wrong Answer', 'Time Limit Exceeded', 'Runtime Error', 'Compile Error', 'Memory Limit Exceeded'];
  for (const v of verdicts) {
    // Only match small text leaves (like status badges) to avoid match triggers on large parent divs.
    if (text === v || (text.includes(v) && text.length < 40)) {
      // Mark element as processed immediately
      processedVerdictNodes.add(node);
      try { node.dataset.dsaProcessed = "true"; } catch (e) {}

      // STRICT CHECK 1: Ignore all verdicts from sample test runner / console / testcase tabs
      const isRunSamplePanel = !!node.closest(
        '[data-e2e-locator="console-result"], [data-layout-path*="console"], [data-layout-path*="testcase"], [class*="console"], [class*="testcase"], [class*="run-code"], [class*="run-result"], [class*="test-result"], [class*="testcase-result"], div[id*="testcase"], div[id*="console"]'
      );
      if (isRunSamplePanel) {
        return;
      }

      // STRICT CHECK 2: User MUST have initiated a real submit action (Submit button or Ctrl+Enter) within the last 45 seconds
      const timeSinceSubmit = Date.now() - lastSubmitClickTimestamp;
      if (lastSubmitClickTimestamp === 0 || timeSinceSubmit > 45000) {
        return;
      }

      // Reset submission timestamp immediately to prevent duplicate triggers
      lastSubmitClickTimestamp = 0;

      const { problemId } = scrapeProblemIdentity();
      const subKey = `${problemId}_${v}`;
      const now = Date.now();
      const lastTime = lastDetectedSubmissions.get(subKey) || 0;

      // Suppress duplicate triggers for the same problem + verdict within 3 seconds
      if (now - lastTime < 3000) {
        return;
      }

      lastDetectedSubmissions.set(subKey, now);
      handleVerdictDetected(v, node);
      break;
    }
  }
};

// Set up MutationObserver to detect when submission result cards appear
const observer = new MutationObserver((mutations) => {
  for (const mutation of mutations) {
    if (mutation.addedNodes.length === 0) continue;
    for (const node of mutation.addedNodes) {
      if (node.nodeType === Node.ELEMENT_NODE) {
        // Direct checks
        checkNodeForVerdict(node);
        // Deep search
        const childVerdicts = node.querySelectorAll && node.querySelectorAll('*');
        if (childVerdicts) {
          for (const cv of childVerdicts) {
            checkNodeForVerdict(cv);
          }
        }
      }
    }
  }
});

// Direct Content Script Fairplay Locking for Solutions, Editorial, Discussions, and Submissions
const injectDirectLockCSS = (isLocked) => {
  let styleEl = document.getElementById('dsa-tutor-fairplay-css');
  if (isLocked) {
    if (!styleEl) {
      styleEl = document.createElement('style');
      styleEl.id = 'dsa-tutor-fairplay-css';
      styleEl.textContent = `
        a[href*="/solution"], a[href*="/solutions"], a[href*="/editorial"], a[href*="/editorials"], a[href*="/discussion"], a[href*="/discussions"], a[href*="/comments"], a[href*="/community"], a[href*="/submissions"], a[href*="/submission"],
        div[data-layout-path*="solution"], div[data-layout-path*="solutions"], div[data-layout-path*="editorial"], div[data-layout-path*="editorials"], div[data-layout-path*="discussion"], div[data-layout-path*="discussions"], div[data-layout-path*="community"], div[data-layout-path*="submissions"], div[data-layout-path*="submission"],
        [data-track-load*="discussion"], [data-track-load*="discussions"], [data-track-load*="solution"], [data-track-load*="solutions"], [data-track-load*="editorial"], [data-track-load*="editorials"], [data-track-load*="submissions"], [data-track-load*="submission"],
        [data-key*="solution"], [data-key*="solutions"], [data-key*="editorial"], [data-key*="editorials"], [data-key*="discussion"], [data-key*="discussions"], [data-key*="submissions"], [data-key*="submission"],
        div[class*="hint-"], details[class*="hint"], div[class*="Hint"],
        div[class*="discussion-"], div[class*="discussions-"], div[class*="comment-"], div[class*="comments-"],
        section[class*="discussion"], section[class*="comment"], section[class*="community"], section[class*="submission"], section[class*="submissions"] {
          display: none !important;
          visibility: hidden !important;
          pointer-events: none !important;
          opacity: 0 !important;
          height: 0 !important;
          width: 0 !important;
          overflow: hidden !important;
        }
      `;
      (document.head || document.documentElement).appendChild(styleEl);
    }
  } else if (styleEl) {
    styleEl.remove();
  }
};

let directAssessmentLocked = false;
let directAssessmentReason = '';

const isForbiddenDOMElement = (el) => {
  if (!el || el === document.body) return false;
  if (el.closest && el.closest('#dsa-tutor-panel-root, #dsa-tutor-root, #dsa-tutor-react-container, #dsa-tutor-panel-container, .monaco-editor, .CodeMirror')) {
    return false;
  }

  let curr = el;
  let depth = 0;
  while (curr && curr !== document.body && depth < 8) {
    if (curr.id && (curr.id.startsWith('dsa-tutor') || curr.id.includes('dsa-tutor'))) return false;

    const text = (curr.textContent || '').trim().toLowerCase();
    const href = (curr.getAttribute ? curr.getAttribute('href') || '' : '').toLowerCase();
    const dataPath = (curr.getAttribute ? curr.getAttribute('data-layout-path') || '' : '').toLowerCase();
    const dataKey = (curr.getAttribute ? curr.getAttribute('data-key') || '' : '').toLowerCase();
    const dataTrack = (curr.getAttribute ? curr.getAttribute('data-track-load') || '' : '').toLowerCase();
    const ariaLabel = (curr.getAttribute ? curr.getAttribute('aria-label') || '' : '').toLowerCase();
    const title = (curr.getAttribute ? curr.getAttribute('title') || '' : '').toLowerCase();
    const idStr = (curr.id || '').toLowerCase();
    const role = (curr.getAttribute ? curr.getAttribute('role') || '' : '').toLowerCase();
    const cls = (curr.className && typeof curr.className === 'string' ? curr.className : '').toLowerCase();

    if (
      href.includes('/editorial') || href.includes('/solution') || href.includes('/solutions') ||
      href.includes('/discussion') || href.includes('/discussions') || href.includes('/community') ||
      href.includes('/comments') || href.includes('/submission') || href.includes('/submissions') ||
      dataPath.includes('editorial') || dataPath.includes('solution') || dataPath.includes('discussion') ||
      dataPath.includes('community') || dataPath.includes('submission') ||
      dataKey.includes('editorial') || dataKey.includes('solution') || dataKey.includes('discussion') ||
      dataKey.includes('community') || dataKey.includes('submission') ||
      dataTrack.includes('editorial') || dataTrack.includes('solution') || dataTrack.includes('discussion') ||
      dataTrack.includes('submission') ||
      (ariaLabel.includes('solution') && !ariaLabel.includes('submit')) ||
      ariaLabel.includes('editorial') || ariaLabel.includes('discussion') || ariaLabel.includes('submission') ||
      ariaLabel.includes('community') || ariaLabel.includes('comment') ||
      (title.includes('solution') && !title.includes('submit')) ||
      title.includes('editorial') || title.includes('discussion') || title.includes('submission') ||
      idStr.includes('editorial') || idStr.includes('discussion') || idStr.includes('submission') ||
      cls.includes('editorial') || cls.includes('solution') || cls.includes('discussion') || cls.includes('submission')
    ) {
      return true;
    }

    if (
      curr.tagName === 'A' || curr.tagName === 'BUTTON' || role === 'tab' ||
      cls.includes('tab') || cls.includes('nav') || cls.includes('btn') || dataPath || dataKey
    ) {
      if (
        text === 'editorial' || text.startsWith('editorial') ||
        text === 'solutions' || text === 'solution' || text.startsWith('solutions') ||
        text === 'discussion' || text === 'discussions' || text.startsWith('discussion') ||
        text === 'submissions' || text === 'submission' || text.startsWith('submissions') ||
        text === 'community' || text === 'comments'
      ) {
        return true;
      }
    }

    curr = curr.parentElement;
    depth++;
  }

  return false;
};

const applyDirectTabLocking = (locked, reason = 'Badge Test') => {
  directAssessmentLocked = !!locked;
  directAssessmentReason = reason || '';
  injectDirectLockCSS(locked);

  if (locked) {
    const curHref = window.location.href;
    if (
      curHref.includes('/editorial') ||
      curHref.includes('/solution') ||
      curHref.includes('/discussion') ||
      curHref.includes('/community') ||
      curHref.includes('/submission')
    ) {
      const cleanUrl = curHref.replace(/\/(editorial|solutions?|discussions?|community|submissions?)[^/]*\/?/gi, '/description/');
      if (cleanUrl !== curHref) {
        window.location.replace(cleanUrl);
      }
    }

    const tabs = Array.from(document.querySelectorAll('a, button, [role="tab"], [data-layout-path], [data-key], [data-track-load], div[class*="tab"], div[class*="nav"], li'));
    tabs.forEach(el => {
      if (el.closest('#dsa-tutor-panel-root, #dsa-tutor-root, #dsa-tutor-react-container, #dsa-tutor-panel-container')) return;
      if (isForbiddenDOMElement(el)) {
        el.style.setProperty('display', 'none', 'important');
        el.style.setProperty('visibility', 'hidden', 'important');
        el.style.setProperty('pointer-events', 'none', 'important');
        el.style.setProperty('opacity', '0', 'important');
        el.style.setProperty('height', '0', 'important');
        el.style.setProperty('width', '0', 'important');
        el.style.setProperty('overflow', 'hidden', 'important');
        el.setAttribute('data-dsa-tab-locked', 'true');
      }
    });
  } else {
    document.querySelectorAll('[data-dsa-tab-locked="true"]').forEach(el => {
      el.style.removeProperty('display');
      el.style.removeProperty('visibility');
      el.style.removeProperty('pointer-events');
      el.style.removeProperty('opacity');
      el.style.removeProperty('height');
      el.style.removeProperty('width');
      el.style.removeProperty('overflow');
      el.removeAttribute('data-dsa-tab-locked');
    });
  }
};

document.addEventListener('click', (e) => {
  if (!directAssessmentLocked) return;

  const path = e.composedPath ? e.composedPath() : [];
  for (const el of path) {
    if (el && el.id && (el.id === 'dsa-tutor-panel-root' || el.id === 'dsa-tutor-react-container' || el.id === 'dsa-tutor-panel-container')) {
      return;
    }
  }

  if (isForbiddenDOMElement(e.target)) {
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    applyDirectTabLocking(true, directAssessmentReason);

    const curHref = window.location.href;
    if (curHref.includes('/editorial') || curHref.includes('/solution') || curHref.includes('/discussion') || curHref.includes('/submissions')) {
      const cleanUrl = curHref.replace(/\/(editorial|solutions?|discussions?|community|submissions?)[^/]*\/?/gi, '/description/');
      if (cleanUrl !== curHref) {
        window.location.replace(cleanUrl);
      }
    }
    return false;
  }
}, true);

// ============================================================================
// 5. Expose on-demand context helpers for the React Code Coach layer
// ============================================================================
window.dsaTutor = window.dsaTutor || {};
window.dsaTutor.getCode = getCodeFromPage;
window.dsaTutor.getLanguage = scrapeCurrentLanguage;
window.dsaTutor.getConstraints = scrapeConstraints;
window.dsaTutor.getIdentity = scrapeProblemIdentity;
window.dsaTutor.setEditorReadOnly = (readOnly) => {
  window.postMessage({ type: 'SET_READ_ONLY', readOnly }, '*');
};
window.dsaTutor.setAssessmentLocked = (locked, reason) => {
  applyDirectTabLocking(locked, reason);
  window.postMessage({ type: 'SET_ASSESSMENT_LOCKED', locked, reason }, '*');
};
window.dsaTutor.resetEditor = () => {
  window.postMessage({ type: 'RESET_EDITOR' }, '*');
};

// Start observing
observer.observe(document.body, { childList: true, subtree: true });
console.log('[DSA Tutor Content] DOM observer and overlay UI initialized.');

// Spaced Repetition Reminder banner injection on LeetCode page load
const injectSpacedRepetitionReminder = () => {
  chrome.runtime.sendMessage({ action: 'get_recommendation' }, (res) => {
    if (res && res.success && res.data && res.data.reviews && res.data.reviews.length > 0) {
      const dueReviews = res.data.reviews;
      
      // Prevent duplicates
      if (document.getElementById('dsa-tutor-spaced-reminder')) return;
      
      // Create container
      const reminderDiv = document.createElement('div');
      reminderDiv.id = 'dsa-tutor-spaced-reminder';
      
      // Inline styling for the premium reminder card
      Object.assign(reminderDiv.style, {
        position: 'fixed',
        bottom: '24px',
        left: '24px',
        width: '320px',
        backgroundColor: '#0e0e10',
        border: '1px solid #1f1f23',
        borderRadius: '12px',
        padding: '16px',
        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 10px 10px -5px rgba(0, 0, 0, 0.4)',
        zIndex: '999999',
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
        color: '#f4f4f5',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px'
      });
      
      const headerDiv = document.createElement('div');
      Object.assign(headerDiv.style, {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1px solid #1f1f23',
        paddingBottom: '8px'
      });
      
      const titleSpan = document.createElement('span');
      titleSpan.innerHTML = '⏰ <strong>Review Due Today</strong>';
      titleSpan.style.fontSize = '13px';
      titleSpan.style.color = '#f4f4f5';
      
      const closeBtn = document.createElement('button');
      closeBtn.innerText = '✕';
      Object.assign(closeBtn.style, {
        background: 'transparent',
        border: 'none',
        color: '#71717a',
        cursor: 'pointer',
        fontSize: '14px',
        padding: '2px 6px'
      });
      closeBtn.onclick = () => {
        reminderDiv.remove();
      };
      
      headerDiv.appendChild(titleSpan);
      headerDiv.appendChild(closeBtn);
      reminderDiv.appendChild(headerDiv);
      
      const descDiv = document.createElement('div');
      descDiv.innerText = 'Maintain your memory strength by practicing these spaced repetition items today:';
      Object.assign(descDiv.style, {
        fontSize: '11px',
        color: '#a1a1aa',
        lineHeight: '1.4'
      });
      reminderDiv.appendChild(descDiv);
      
      const listContainer = document.createElement('div');
      Object.assign(listContainer.style, {
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
        maxHeight: '180px',
        overflowY: 'auto'
      });
      
      dueReviews.forEach((rev) => {
        const itemA = document.createElement('a');
        itemA.href = rev.url;
        itemA.target = '_top';
        Object.assign(itemA.style, {
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 10px',
          backgroundColor: '#18181b',
          border: '1px solid #27272a',
          borderRadius: '6px',
          textDecoration: 'none',
          color: '#e4e4e7',
          fontSize: '12px',
          transition: 'all 0.2s'
        });
        
        itemA.onmouseenter = () => {
          itemA.style.borderColor = '#3b82f6';
          itemA.style.backgroundColor = '#1c1c21';
        };
        itemA.onmouseleave = () => {
          itemA.style.borderColor = '#27272a';
          itemA.style.backgroundColor = '#18181b';
        };
        
        const textSpan = document.createElement('span');
        textSpan.innerText = rev.title;
        textSpan.style.fontWeight = '500';
        textSpan.style.overflow = 'hidden';
        textSpan.style.textOverflow = 'ellipsis';
        textSpan.style.whiteSpace = 'nowrap';
        textSpan.style.maxWidth = '180px';
        
        const diffSpan = document.createElement('span');
        diffSpan.innerText = rev.difficulty;
        Object.assign(diffSpan.style, {
          fontSize: '9px',
          fontWeight: '700',
          padding: '2px 5px',
          borderRadius: '4px',
          textTransform: 'uppercase'
        });
        
        if (rev.difficulty.toLowerCase() === 'easy') {
          diffSpan.style.color = '#22c55e';
          diffSpan.style.backgroundColor = 'rgba(34, 197, 94, 0.1)';
        } else if (rev.difficulty.toLowerCase() === 'medium') {
          diffSpan.style.color = '#eab308';
          diffSpan.style.backgroundColor = 'rgba(234, 179, 8, 0.1)';
        } else {
          diffSpan.style.color = '#ef4444';
          diffSpan.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
        }
        
        itemA.appendChild(textSpan);
        itemA.appendChild(diffSpan);
        listContainer.appendChild(itemA);
      });
      
      reminderDiv.appendChild(listContainer);
      document.body.appendChild(reminderDiv);
    }
  });
};

// Inject when document is fully loaded or active
if (document.readyState === 'complete' || document.readyState === 'interactive') {
  injectSpacedRepetitionReminder();
} else {
  window.addEventListener('DOMContentLoaded', injectSpacedRepetitionReminder);
}
