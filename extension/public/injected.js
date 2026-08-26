// Function to apply/enforce readOnly state on Monaco + DOM overlay
const applyReadOnlyState = (isReadOnly) => {
  window.__dsaTutorReadOnly = !!isReadOnly;

  // 1. Monaco Editor API
  try {
    if (window.monaco && window.monaco.editor) {
      const editors = window.monaco.editor.getEditors();
      if (editors && editors.length > 0) {
        editors.forEach((editor) => {
          editor.updateOptions({ readOnly: !!isReadOnly });
        });
      }
    }
  } catch (e) {
    console.warn("[DSA Tutor Injected] Error updating Monaco readOnly:", e);
  }

  // 2. DOM-level Overlay for LeetCode Editor Container
  try {
    const editorEl = document.querySelector(".monaco-editor, .CodeMirror, [class*='editor-container'], [class*='editor'], [data-mode-id], div[class*='monaco']");
    let lockOverlay = document.getElementById("dsa-tutor-editor-lock-overlay");

    if (isReadOnly) {
      if (editorEl) {
        if (!lockOverlay || !editorEl.contains(lockOverlay)) {
          if (lockOverlay) lockOverlay.remove();
          lockOverlay = document.createElement("div");
          lockOverlay.id = "dsa-tutor-editor-lock-overlay";
          Object.assign(lockOverlay.style, {
            position: "absolute",
            top: "0",
            left: "0",
            width: "100%",
            height: "100%",
            backgroundColor: "rgba(14, 14, 16, 0.85)",
            backdropFilter: "blur(4px)",
            webkitBackdropFilter: "blur(4px)",
            zIndex: "9999",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            color: "#f4f4f5",
            fontFamily: "'Inter', -apple-system, sans-serif",
            pointerEvents: "all",
            cursor: "not-allowed"
          });
          lockOverlay.innerHTML = `
            <div style="background: #18181b; border: 1px solid #27272a; padding: 18px 24px; border-radius: 10px; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.6); text-align: center; max-width: 320px;">
              <div style="font-size: 22px; margin-bottom: 6px;">🔒</div>
              <div style="font-size: 14px; font-weight: 700; color: #fbbf24; margin-bottom: 6px;">Mock Interview Gated</div>
              <div style="font-size: 11px; color: #a1a1aa; line-height: 1.4;">Submit your verbal strategy in the CodeCoach panel to unlock the code editor.</div>
            </div>
          `;
          const currentPos = getComputedStyle(editorEl).position;
          if (currentPos === "static") {
            editorEl.style.position = "relative";
          }
          editorEl.appendChild(lockOverlay);
        }
      }
    } else {
      if (lockOverlay) {
        lockOverlay.remove();
      }
    }
  } catch (e) {
    console.warn("[DSA Tutor Injected] Error setting DOM lock overlay:", e);
  }
};

// Poll and subscribe to new Monaco editors to lock them automatically
const initMonacoListeners = () => {
  if (window.monaco && window.monaco.editor) {
    // Intercept future editor creations
    window.monaco.editor.onDidCreateEditor((editor) => {
      if (window.__dsaTutorReadOnly) {
        editor.updateOptions({ readOnly: true });
      }
    });

    applyReadOnlyState(window.__dsaTutorReadOnly);
  }
};

const pollInterval = setInterval(() => {
  if (window.monaco && window.monaco.editor) {
    initMonacoListeners();
    clearInterval(pollInterval);
  }
}, 200);

window.__dsaTutorAssessmentLocked = false;
window.__dsaTutorLockReason = "";

const injectLockCSS = (isLocked) => {
  let styleEl = document.getElementById("dsa-tutor-fairplay-css");
  if (isLocked) {
    if (!styleEl) {
      styleEl = document.createElement("style");
      styleEl.id = "dsa-tutor-fairplay-css";
      styleEl.textContent = `
        a[href*="/solution"], a[href*="/solutions"], a[href*="/editorial"], a[href*="/editorials"], a[href*="/discussion"], a[href*="/discussions"], a[href*="/comments"], a[href*="/community"], a[href*="/submissions/detail"],
        div[data-layout-path*="solution"], div[data-layout-path*="solutions"], div[data-layout-path*="editorial"], div[data-layout-path*="editorials"], div[data-layout-path*="discussion"], div[data-layout-path*="discussions"], div[data-layout-path*="community"], div[data-layout-path*="submission"], div[data-layout-path*="submissions"],
        [data-track-load*="discussion"], [data-track-load*="discussions"], [data-track-load*="solution"], [data-track-load*="solutions"], [data-track-load*="editorial"], [data-track-load*="editorials"], [data-track-load*="submissions"],
        [data-key*="solution"], [data-key*="solutions"], [data-key*="editorial"], [data-key*="editorials"], [data-key*="discussion"], [data-key*="discussions"], [data-key*="submission"], [data-key*="submissions"],
        div[class*="hint-"], details[class*="hint"], div[class*="Hint"],
        div[class*="discussion-"], div[class*="discussions-"], div[class*="comment-"], div[class*="comments-"],
        div[class*="submissions-list"], div[class*="submission-list"], div[class*="past-submissions"], div[class*="submission-detail"],
        section[class*="discussion"], section[class*="comment"], section[class*="community"] {
          display: none !important;
          visibility: hidden !important;
          pointer-events: none !important;
          opacity: 0 !important;
          height: 0 !important;
          width: 0 !important;
          overflow: hidden !important;
        }
      `;
      document.head.appendChild(styleEl);
    }
  } else {
    if (styleEl) {
      styleEl.remove();
    }
  }
};

// Helper to determine if an element or any of its ancestors is a forbidden tab / link / panel
const isForbiddenElement = (el) => {
  if (!el || el === document.body) return false;
  if (el.closest && el.closest("#dsa-tutor-panel-root, #dsa-tutor-root, #dsa-tutor-react-container, #dsa-tutor-panel-container, .monaco-editor, .CodeMirror")) {
    return false;
  }

  let curr = el;
  let depth = 0;
  while (curr && curr !== document.body && depth < 8) {
    if (curr.id && (curr.id.startsWith("dsa-tutor") || curr.id.includes("dsa-tutor"))) return false;

    const text = (curr.textContent || "").trim().toLowerCase();
    const href = (curr.getAttribute ? curr.getAttribute("href") || "" : "").toLowerCase();
    const dataPath = (curr.getAttribute ? curr.getAttribute("data-layout-path") || "" : "").toLowerCase();
    const dataKey = (curr.getAttribute ? curr.getAttribute("data-key") || "" : "").toLowerCase();
    const dataTrack = (curr.getAttribute ? curr.getAttribute("data-track-load") || "" : "").toLowerCase();
    const ariaLabel = (curr.getAttribute ? curr.getAttribute("aria-label") || "" : "").toLowerCase();
    const title = (curr.getAttribute ? curr.getAttribute("title") || "" : "").toLowerCase();
    const idStr = (curr.id || "").toLowerCase();
    const role = (curr.getAttribute ? curr.getAttribute("role") || "" : "").toLowerCase();
    const cls = (curr.className && typeof curr.className === "string" ? curr.className : "").toLowerCase();

    // NEVER lock the real submit button
    const isSubmitActionBtn = (
      curr.getAttribute?.("data-e2e-locator") === "console-submit-button" ||
      curr.getAttribute?.("data-cypress") === "submit-code-btn" ||
      text === "submit" ||
      text === "submit code" ||
      ((ariaLabel === "submit" || title === "submit") && (curr.tagName === "BUTTON" || role === "button"))
    );
    if (isSubmitActionBtn && !dataPath.includes("submission") && !cls.includes("tab")) {
      return false;
    }

    if (
      href.includes("/editorial") || href.includes("/solution") || href.includes("/solutions") ||
      href.includes("/discussion") || href.includes("/discussions") || href.includes("/community") ||
      href.includes("/comments") || href.includes("/submissions/detail") || /\/submissions\/\d+/.test(href) ||
      dataPath.includes("editorial") || dataPath.includes("solution") || dataPath.includes("discussion") ||
      dataPath.includes("community") || dataPath.includes("submission") ||
      dataKey.includes("editorial") || dataKey.includes("solution") || dataKey.includes("discussion") ||
      dataKey.includes("community") || dataKey.includes("submission") ||
      dataTrack.includes("editorial") || dataTrack.includes("solution") || dataTrack.includes("discussion") ||
      dataTrack.includes("submissions") ||
      (ariaLabel.includes("solution") && !ariaLabel.includes("submit")) ||
      ariaLabel.includes("editorial") || ariaLabel.includes("discussion") ||
      ariaLabel.includes("community") || ariaLabel.includes("comment") ||
      (title.includes("solution") && !title.includes("submit")) ||
      title.includes("editorial") || title.includes("discussion") ||
      idStr.includes("editorial") || idStr.includes("discussion") ||
      cls.includes("editorial") || cls.includes("solution") || cls.includes("discussion") || cls.includes("submissions-list") || cls.includes("submission-list")
    ) {
      return true;
    }

    if (
      curr.tagName === "A" || curr.tagName === "BUTTON" || role === "tab" ||
      cls.includes("tab") || cls.includes("nav") || cls.includes("btn") || dataPath || dataKey
    ) {
      if (
        text === "editorial" || text.startsWith("editorial") ||
        text === "solutions" || text === "solution" || text.startsWith("solutions") ||
        text === "discussion" || text === "discussions" || text.startsWith("discussion") ||
        text === "submissions" || text === "past submissions" || text === "submission history" ||
        text === "community" || text === "comments"
      ) {
        return true;
      }
    }

    curr = curr.parentElement;
    depth++;
  }

  return false;
};

// Function to hide / disable forbidden tabs in LeetCode during Assessment / Mock Mode
const applyAssessmentTabLocking = (isLocked, reason = "Assessment Mode") => {
  window.__dsaTutorAssessmentLocked = !!isLocked;
  window.__dsaTutorLockReason = reason || "";
  injectLockCSS(isLocked);

  try {
    const isForbiddenRoute = (
      window.location.href.includes("/solution") ||
      window.location.href.includes("/solutions") ||
      window.location.href.includes("/editorial") ||
      window.location.href.includes("/editorials") ||
      window.location.href.includes("/discussion") ||
      window.location.href.includes("/discussions") ||
      window.location.href.includes("/comments") ||
      window.location.href.includes("/community") ||
      window.location.href.includes("/submissions/detail") ||
      /\/submissions\/\d+/.test(window.location.href)
    );

    // If currently on a forbidden route, immediately redirect back to /description/
    if (isLocked && isForbiddenRoute) {
      const cleanUrl = window.location.href.replace(/\/(editorial|solutions?|discussions?|community|submissions\/detail[^\s/]*|submissions\/\d+[^\s/]*)[^/]*\/?/gi, "/description/");
      if (cleanUrl !== window.location.href) {
        window.location.replace(cleanUrl);
      }
    }

    let lockOverlay = document.getElementById("dsa-tutor-tab-lock-overlay");

    if (isLocked) {
      // Find and hide LeetCode tab buttons strictly across all candidate elements
      const tabs = Array.from(document.querySelectorAll('a, button, [role="tab"], [data-layout-path], [data-key], [data-track-load], div[class*="tab"], div[class*="nav"], li'));
      tabs.forEach(el => {
        if (el.closest("#dsa-tutor-panel-root, #dsa-tutor-root, #dsa-tutor-react-container, #dsa-tutor-panel-container")) return;

        if (isForbiddenElement(el)) {
          el.style.setProperty("display", "none", "important");
          el.style.setProperty("visibility", "hidden", "important");
          el.style.setProperty("pointer-events", "none", "important");
          el.style.setProperty("opacity", "0", "important");
          el.style.setProperty("height", "0", "important");
          el.style.setProperty("width", "0", "important");
          el.style.setProperty("overflow", "hidden", "important");
          el.setAttribute("data-dsa-tab-locked", "true");
        }
      });

      // If user is currently directly viewing an Editorial/Solutions/Discussion panel:
      const panelContainer = document.querySelector(
        "div[data-layout-path*='editorial'], div[data-layout-path*='solution'], div[data-layout-path*='solutions'], div[data-layout-path*='discussion'], div[data-layout-path*='discussions']"
      );

      if ((isForbiddenRoute || panelContainer) && !document.getElementById("dsa-tutor-tab-lock-overlay")) {
        const mountTarget = panelContainer || document.querySelector(".elfjS, [data-track-load='description_content']")?.parentElement || document.body;
        if (mountTarget && mountTarget !== document.body) {
          lockOverlay = document.createElement("div");
          lockOverlay.id = "dsa-tutor-tab-lock-overlay";
          Object.assign(lockOverlay.style, {
            position: "absolute",
            top: "0",
            left: "0",
            width: "100%",
            height: "100%",
            backgroundColor: "rgba(14, 14, 16, 0.96)",
            backdropFilter: "blur(6px)",
            webkitBackdropFilter: "blur(6px)",
            zIndex: "99999",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            color: "#f4f4f5",
            fontFamily: "'Inter', -apple-system, sans-serif",
            pointerEvents: "all"
          });
          lockOverlay.innerHTML = `
            <div style="background: #18181b; border: 1px solid #27272a; padding: 24px 32px; border-radius: 12px; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7); text-align: center; max-width: 360px;">
              <div style="font-size: 32px; margin-bottom: 8px;">🔒</div>
              <div style="font-size: 15px; font-weight: 700; color: #ef4444; margin-bottom: 8px;">Solutions, Editorial, Discussion & Submissions Locked</div>
              <div style="font-size: 12px; color: #a1a1aa; line-height: 1.5;">
                Access to official solutions, editorials, community discussions, and past submissions is disabled during <strong>${reason}</strong> to maintain test integrity.
              </div>
            </div>
          `;
          if (getComputedStyle(mountTarget).position === "static") {
            mountTarget.style.position = "relative";
          }
          mountTarget.appendChild(lockOverlay);
        }
      } else if (!isForbiddenRoute && !panelContainer) {
        if (lockOverlay) lockOverlay.remove();
      }
    } else {
      if (lockOverlay) lockOverlay.remove();

      document.querySelectorAll('[data-dsa-tab-locked="true"]').forEach(el => {
        el.style.removeProperty("display");
        el.style.removeProperty("visibility");
        el.style.removeProperty("pointer-events");
        el.style.removeProperty("opacity");
        el.style.removeProperty("height");
        el.style.removeProperty("width");
        el.style.removeProperty("overflow");
        el.removeAttribute("data-dsa-tab-locked");
      });
    }
  } catch (e) {
    console.warn("[DSA Tutor Injected] Error applying tab locking:", e);
  }
};

// Intercept clicks strictly on navigation tabs when locked
document.addEventListener("click", (e) => {
  if (!window.__dsaTutorAssessmentLocked) return;

  const path = e.composedPath ? e.composedPath() : [];
  for (const el of path) {
    if (el && el.id && (el.id === "dsa-tutor-panel-root" || el.id === "dsa-tutor-react-container" || el.id === "dsa-tutor-panel-container")) {
      return; // Clicks inside extension panel must NEVER be intercepted
    }
  }

  if (isForbiddenElement(e.target)) {
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    applyAssessmentTabLocking(true, window.__dsaTutorLockReason);

    const curHref = window.location.href;
    if (curHref.includes("/editorial") || curHref.includes("/solution") || curHref.includes("/discussion") || curHref.includes("/submissions")) {
      const cleanUrl = curHref.replace(/\/(editorial|solutions?|discussions?|community|submissions?)[^/]*\/?/gi, "/description/");
      if (cleanUrl !== curHref) {
        window.location.replace(cleanUrl);
      }
    }
    return false;
  }
}, true);

window.addEventListener("message", (event) => {
  // Only accept messages from ourselves
  if (event.source !== window) return;

  if (event.data && event.data.type === "REQUEST_CODE") {
    try {
      const models = window.monaco?.editor?.getModels();
      let code = "";
      if (models && models.length > 0) {
        let bestModel = models[0];
        let maxLen = bestModel.getValue() ? bestModel.getValue().length : 0;
        for (let i = 1; i < models.length; i++) {
          const m = models[i];
          const val = m.getValue() || "";
          const uriStr = m.uri ? m.uri.toString() : "";
          if (!uriStr.includes("input") && !uriStr.includes("testcase") && val.length > maxLen) {
            maxLen = val.length;
            bestModel = m;
          }
        }
        code = bestModel.getValue();
      }

      // DOM fallback if Monaco model was missing or empty
      if (!code) {
        const viewLines = document.querySelectorAll(".view-lines .view-line");
        if (viewLines.length > 0) {
          code = Array.from(viewLines).map(el => el.textContent || "").join("\n");
        } else {
          const area = document.querySelector("textarea.inputarea, .CodeMirror");
          if (area) code = area.value || area.textContent || "";
        }
      }
      
      window.postMessage({ type: "CODE_VALUE", code: code }, window.location.origin);
    } catch (e) {
      console.error("[DSA Tutor Injected] Error reading Monaco editor:", e);
      window.postMessage({ type: "CODE_VALUE", code: "", error: e.message }, window.location.origin);
    }
  }

  if (event.data && event.data.type === "SET_READ_ONLY") {
    applyReadOnlyState(event.data.readOnly);
  }

  if (event.data && event.data.type === "SET_ASSESSMENT_LOCKED") {
    applyAssessmentTabLocking(event.data.locked, event.data.reason);
  }

  if (event.data && event.data.type === "RESET_EDITOR") {
    try {
      const executeReset = () => {
        const allButtons = Array.from(document.querySelectorAll(
          'button, [role="button"], [data-cypress="ResetCode"], [data-cy="reset-code-btn"], [data-track-name="reset_code"], [aria-label*="Reset"], [aria-label*="reset"], [title*="Reset"], [title*="reset"], [aria-label*="default code"], [title*="default code"], [aria-label*="Retrieve default"], [title*="Retrieve default"]'
        ));

        let resetBtn = allButtons.find(el => {
          if (el.closest("#dsa-tutor-panel-root, #dsa-tutor-root, #dsa-tutor-react-container, #dsa-tutor-panel-container")) return false;
          const str = (
            (el.getAttribute('title') || '') + ' ' +
            (el.getAttribute('aria-label') || '') + ' ' +
            (el.getAttribute('data-cypress') || '') + ' ' +
            (el.getAttribute('data-cy') || '') + ' ' +
            (el.getAttribute('data-track-name') || '') + ' ' +
            (el.textContent || '') + ' ' +
            (el.innerHTML || '')
          ).toLowerCase();

          return str.includes('reset') || str.includes('restore') || str.includes('revert') || str.includes('default code') || str.includes('rotate-ccw');
        });

        // Also search inside editor header toolbars specifically
        if (!resetBtn) {
          const editorToolbars = document.querySelectorAll('[class*="editor"] [class*="tools"], [class*="editor-header"], .monaco-editor, [class*="action-btn"]');
          for (const bar of editorToolbars) {
            const btns = bar.querySelectorAll('button, svg, [role="button"]');
            for (const b of btns) {
              const html = (b.outerHTML || '').toLowerCase();
              if (html.includes('reset') || html.includes('rotate') || html.includes('history') || html.includes('undo') || html.includes('default')) {
                resetBtn = b.closest('button, [role="button"]') || b;
                break;
              }
            }
            if (resetBtn) break;
          }
        }

        if (resetBtn) {
          resetBtn.click();
          // Confirm the reset modal with multiple attempts
          [100, 250, 450, 700, 1100].forEach(delay => {
            setTimeout(() => {
              const confirmBtns = Array.from(document.querySelectorAll(
                'button, div[role="button"], [data-cy="confirm-btn"], [class*="modal"] button, [class*="dialog"] button, [class*="popup"] button'
              ));
              const confirmBtn = confirmBtns.find(b => {
                if (b.closest("#dsa-tutor-panel-root, #dsa-tutor-root, #dsa-tutor-react-container, #dsa-tutor-panel-container")) return false;
                const txt = (b.textContent || '').trim().toLowerCase();
                const cls = (b.className || '').toLowerCase();
                return txt === 'confirm' || txt === 'reset' || txt === 'restore' || txt === 'yes' || txt.includes('reset code') || txt.includes('confirm') || cls.includes('confirm');
              });
              if (confirmBtn) confirmBtn.click();
            }, delay);
          });
        }
      };

      // Run immediate and staggered attempts to catch DOM readiness
      executeReset();
      setTimeout(executeReset, 350);
      setTimeout(executeReset, 800);
      setTimeout(executeReset, 1500);

      // Re-apply readOnly state if locked
      if (window.__dsaTutorReadOnly) {
        setTimeout(() => {
          applyReadOnlyState(true);
        }, 400);
      }
    } catch (e) {
      console.error("[DSA Tutor Injected] Error resetting editor:", e);
    }
  }
});

// Continuously enforce readOnly & overlay state while readOnly is active
setInterval(() => {
  if (window.__dsaTutorReadOnly) {
    applyReadOnlyState(true);
  }
}, 400);

// Continuously enforce assessment locking while assessment is active
setInterval(() => {
  if (window.__dsaTutorAssessmentLocked) {
    applyAssessmentTabLocking(true, window.__dsaTutorLockReason);
  }
}, 300);
