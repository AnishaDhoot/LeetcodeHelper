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
  document.body.appendChild(rootDiv);

  const shadowRoot = rootDiv.attachShadow({ mode: 'open' });

  // Create wrapper inside shadow root
  const reactContainer = document.createElement('div');
  reactContainer.id = 'dsa-tutor-react-container';
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
const getCodeFromPage = (timeoutMs = 1500) => {
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
    window.postMessage({ type: 'REQUEST_CODE' }, '*');

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

const checkNodeForVerdict = (node) => {
  if (!node) return;
  const text = node.textContent?.trim() || '';
  if (!text) return;

  const verdicts = ['Accepted', 'Wrong Answer', 'Time Limit Exceeded', 'Runtime Error', 'Compile Error', 'Memory Limit Exceeded'];
  for (const v of verdicts) {
    // Only match small text leaves (like status badges) to avoid match triggers on large parent divs.
    if (text === v || (text.includes(v) && text.length < 40)) {
      const now = Date.now();
      if (now - lastTriggerTime < 6000) return; // Prevent multiple triggers within 6s
      lastTriggerTime = now;
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

// ============================================================================
// 5. Expose on-demand context helpers for the React Code Coach layer
// ============================================================================
window.dsaTutor = window.dsaTutor || {};
window.dsaTutor.getCode = getCodeFromPage;
window.dsaTutor.getLanguage = scrapeCurrentLanguage;
window.dsaTutor.getConstraints = scrapeConstraints;
window.dsaTutor.getIdentity = scrapeProblemIdentity;

// Start observing
observer.observe(document.body, { childList: true, subtree: true });
console.log('[DSA Tutor Content] DOM observer and overlay UI initialized.');
