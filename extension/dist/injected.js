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
              <div style="font-size: 11px; color: #a1a1aa; line-height: 1.4;">Submit your verbal strategy in the Kode panel to unlock the code editor.</div>
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
        a[href*="/solution"], a[href*="/editorial"], a[href*="/discussion"], a[href*="/discussions"], a[href*="/comments"], a[href*="/community"],
        div[data-layout-path*="solution"], div[data-layout-path*="editorial"], div[data-layout-path*="discussion"], div[data-layout-path*="community"],
        [data-track-load*="discussion"], [data-track-load*="discussions"], [data-track-load*="solution"], [data-track-load*="editorial"],
        [data-key*="solution"], [data-key*="editorial"], [data-key*="discussion"],
        div[class*="hint-"], details[class*="hint"], div[class*="Hint"],
        div[class*="discussion-"], div[class*="discussions-"], div[class*="comment-"], div[class*="comments-"],
        section[class*="discussion"], section[class*="comment"], section[class*="community"] {
          display: none !important;
          visibility: hidden !important;
          pointer-events: none !important;
          opacity: 0 !important;
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

// Function to hide / disable forbidden tabs in LeetCode during Assessment / Mock Mode
const applyAssessmentTabLocking = (isLocked, reason = "Assessment Mode") => {
  window.__dsaTutorAssessmentLocked = !!isLocked;
  window.__dsaTutorLockReason = reason || "";
  injectLockCSS(isLocked);

  try {
    const isForbiddenRoute = (
      window.location.href.includes("/solution") ||
      window.location.href.includes("/editorial") ||
      window.location.href.includes("/discussion") ||
      window.location.href.includes("/community")
    );

    let lockOverlay = document.getElementById("dsa-tutor-tab-lock-overlay");

    if (isLocked) {
      // Find and hide LeetCode tab buttons strictly
      const tabs = Array.from(document.querySelectorAll('a, button, [role="tab"], [data-layout-path]'));
      tabs.forEach(el => {
        // NEVER lock anything inside our extension
        if (el.closest("#dsa-tutor-panel-root, #dsa-tutor-root")) return;

        const text = (el.textContent || "").trim().toLowerCase();
        const href = (el.getAttribute("href") || "").toLowerCase();
        const dataPath = (el.getAttribute("data-layout-path") || "").toLowerCase();
        const ariaLabel = (el.getAttribute("aria-label") || "").toLowerCase();
        const idStr = (el.id || "").toLowerCase();
        const classStr = (typeof el.className === "string" ? el.className : "").toLowerCase();

        const isForbiddenTab = (
          (href.includes("/solution") || href.includes("/editorial") || href.includes("/discussion") || href.includes("/community")) ||
          (dataPath.includes("solution") || dataPath.includes("editorial") || dataPath.includes("discussion") || dataPath.includes("submissions")) ||
          (el.getAttribute("role") === "tab" && (text.includes("editorial") || text.includes("solution") || text.includes("discussion") || text.includes("community") || text.includes("submissions"))) ||
          (ariaLabel.includes("editorial") || (ariaLabel.includes("solution") && !ariaLabel.includes("submit")) || ariaLabel.includes("discussion")) ||
          (idStr.includes("editorial") || idStr.includes("discussion"))
        );

        if (isForbiddenTab) {
          el.style.setProperty("display", "none", "important");
          el.style.setProperty("visibility", "hidden", "important");
          el.style.setProperty("pointer-events", "none", "important");
          el.style.setProperty("opacity", "0", "important");
          el.setAttribute("data-dsa-tab-locked", "true");
        }
      });

      // If user is currently on an Editorial/Solutions/Discussion URL route:
      if (isForbiddenRoute) {
        const descTab = Array.from(document.querySelectorAll('a, button, [role="tab"]')).find(el => {
          const txt = (el.textContent || "").trim().toLowerCase();
          const href = (el.getAttribute("href") || "").toLowerCase();
          return (txt.includes("description") || txt.includes("problem") || href.includes("/description")) && !txt.includes("solution") && !txt.includes("editorial");
        });
        if (descTab) {
          descTab.click();
        }

        const panelContainer = document.querySelector(
          "div[data-layout-path*='editorial'], div[data-layout-path*='solution'], div[data-layout-path*='solutions'], div[data-layout-path*='discussion']"
        );

        if (panelContainer && !document.getElementById("dsa-tutor-tab-lock-overlay")) {
          lockOverlay = document.createElement("div");
          lockOverlay.id = "dsa-tutor-tab-lock-overlay";
          Object.assign(lockOverlay.style, {
            position: "absolute",
            top: "0",
            left: "0",
            width: "100%",
            height: "100%",
            backgroundColor: "rgba(14, 14, 16, 0.95)",
            backdropFilter: "blur(6px)",
            webkitBackdropFilter: "blur(6px)",
            zIndex: "9999",
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
              <div style="font-size: 15px; font-weight: 700; color: #ef4444; margin-bottom: 8px;">Solutions, Editorial & Discussion Locked</div>
              <div style="font-size: 12px; color: #a1a1aa; line-height: 1.5;">
                Access to official solutions, editorials, community discussions, and past submissions is disabled during <strong>${reason}</strong> to maintain test integrity.
              </div>
            </div>
          `;
          if (getComputedStyle(panelContainer).position === "static") {
            panelContainer.style.position = "relative";
          }
          panelContainer.appendChild(lockOverlay);
        }
      } else {
        if (lockOverlay) lockOverlay.remove();
      }
    } else {
      if (lockOverlay) lockOverlay.remove();

      document.querySelectorAll('[data-dsa-tab-locked="true"]').forEach(el => {
        el.style.removeProperty("display");
        el.style.removeProperty("visibility");
        el.style.removeProperty("pointer-events");
        el.style.removeProperty("opacity");
        el.removeAttribute("data-dsa-tab-locked");
      });
    }
  } catch (e) {
    console.warn("[DSA Tutor Injected] Error applying tab locking:", e);
  }
};

// Intercept clicks strictly on navigation tabs when locked (Never block question description or code editor)
document.addEventListener("click", (e) => {
  if (!window.__dsaTutorAssessmentLocked) return;

  const target = e.target;
  // Ignore clicks inside our extension panel, monaco editor, console runner, and description text container
  if (target && target.closest("#dsa-tutor-panel-root, #dsa-tutor-root, .monaco-editor, .CodeMirror, [class*='console-'], [class*='description_content'], .elfjS, [data-track-load='description_content']")) {
    return;
  }

  const closestNav = target ? target.closest("a, button, [role='tab'], [data-layout-path]") : null;
  if (!closestNav) return;

  const text = (closestNav.textContent || "").trim().toLowerCase();
  const href = (closestNav.getAttribute("href") || "").toLowerCase();
  const dataPath = (closestNav.getAttribute("data-layout-path") || "").toLowerCase();
  const ariaLabel = (closestNav.getAttribute("aria-label") || "").toLowerCase();
  const idStr = (closestNav.id || "").toLowerCase();

  const isForbiddenTab = (
    href.includes("/editorial") ||
    href.includes("/solution") ||
    href.includes("/solutions") ||
    href.includes("/discussion") ||
    href.includes("/discussions") ||
    href.includes("/comments") ||
    href.includes("/community") ||
    dataPath.includes("editorial") ||
    dataPath.includes("solution") ||
    dataPath.includes("solutions") ||
    dataPath.includes("discussion") ||
    dataPath.includes("submissions") ||
    (ariaLabel.includes("solution") && !ariaLabel.includes("submit")) ||
    ariaLabel.includes("editorial") ||
    ariaLabel.includes("discussion") ||
    idStr.includes("editorial") ||
    idStr.includes("discussion") ||
    (closestNav.getAttribute("role") === "tab" && (
      text.includes("editorial") ||
      text.includes("solution") ||
      text.includes("discussion") ||
      text.includes("comment") ||
      text.includes("community")
    ))
  );

  if (isForbiddenTab) {
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    applyAssessmentTabLocking(true, window.__dsaTutorLockReason);
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
      // 1. Click LeetCode's native Reset Code button in DOM to restore official starter template
      const resetCandidates = Array.from(document.querySelectorAll(
        'button, div[role="button"], span[role="button"], [data-keyup="reset-code"], [data-track-name="reset_code"], [aria-label*="Reset"], [title*="Reset"], [data-cypress="ResetCode"], [data-cy="reset-code-btn"]'
      ));
      const resetBtn = resetCandidates.find(el => {
        const title = (el.getAttribute('title') || el.getAttribute('aria-label') || el.getAttribute('data-cy') || el.getAttribute('data-track-name') || el.textContent || '').toLowerCase();
        return title.includes('reset') || title.includes('restore') || title.includes('revert');
      });

      if (resetBtn) {
        resetBtn.click();
        
        // Multi-attempt confirmation click to handle variable modal animation delays
        [100, 250, 450].forEach(delay => {
          setTimeout(() => {
            const confirmBtns = Array.from(document.querySelectorAll('button, div[role="button"], [data-cy="confirm-btn"]'));
            const confirmBtn = confirmBtns.find(b => {
              const txt = (b.textContent || '').trim().toLowerCase();
              return txt === 'confirm' || txt === 'reset' || txt === 'restore' || txt === 'yes';
            });
            if (confirmBtn) confirmBtn.click();
          }, delay);
        });
      }

      // Re-apply readOnly state if locked
      if (window.__dsaTutorReadOnly) {
        setTimeout(() => {
          applyReadOnlyState(true);
        }, 300);
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
