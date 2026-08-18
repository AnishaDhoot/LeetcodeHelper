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

window.__dsaTutorInitialModelValues = window.__dsaTutorInitialModelValues || new Map();

const captureModelInitialValues = () => {
  try {
    const models = window.monaco?.editor?.getModels() || [];
    models.forEach(model => {
      const uriStr = model.uri ? model.uri.toString() : "";
      if (!uriStr.includes("input") && !uriStr.includes("testcase")) {
        if (!window.__dsaTutorInitialModelValues.has(uriStr)) {
          const val = model.getValue();
          if (val && val.trim().length > 0) {
            window.__dsaTutorInitialModelValues.set(uriStr, val);
          }
        }
      }
    });
  } catch (e) {}
};

// Monkey-patch Monaco model setValue to prevent LeetCode from injecting past solutions during assessments
const patchMonacoModel = (model) => {
  if (!model || model.__dsaPatched) return;
  model.__dsaPatched = true;

  const originalSetValue = model.setValue.bind(model);
  model.setValue = function(newValue) {
    if (window.__dsaTutorAssessmentLocked || window.__dsaTutorReadOnly) {
      const uriStr = model.uri ? model.uri.toString() : "";
      if (!uriStr.includes("input") && !uriStr.includes("testcase")) {
        const cleaned = cleanStarterCode(newValue);
        return originalSetValue(cleaned);
      }
    }
    return originalSetValue(newValue);
  };

  if (window.__dsaTutorAssessmentLocked || window.__dsaTutorReadOnly) {
    const uriStr = model.uri ? model.uri.toString() : "";
    if (!uriStr.includes("input") && !uriStr.includes("testcase")) {
      const current = model.getValue();
      if (current) {
        const cleaned = cleanStarterCode(current);
        if (cleaned !== current) {
          originalSetValue(cleaned);
        }
      }
    }
  }
};

// Poll and subscribe to new Monaco editors to lock them automatically
const initMonacoListeners = () => {
  if (window.monaco && window.monaco.editor) {
    const models = window.monaco.editor.getModels() || [];
    models.forEach(patchMonacoModel);

    // Intercept future editor and model creations
    window.monaco.editor.onDidCreateEditor((editor) => {
      if (window.__dsaTutorReadOnly) {
        editor.updateOptions({ readOnly: true });
      }
      const model = editor.getModel();
      if (model) patchMonacoModel(model);
      setTimeout(captureModelInitialValues, 500);
    });

    if (window.monaco.editor.onDidCreateModel) {
      window.monaco.editor.onDidCreateModel((model) => {
        patchMonacoModel(model);
      });
    }

    captureModelInitialValues();
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
        a[href*="/solutions"], a[href*="/editorial"], a[href*="/discussion"], a[href*="/submissions"],
        a[href*="/solutions/"], a[href*="/editorial/"], a[href*="/discussion/"], a[href*="/submissions/"],
        div[data-layout-path*="solutions"], div[data-layout-path*="editorial"], div[data-layout-path*="discussion"], div[data-layout-path*="submissions"] {
          display: none !important;
          visibility: hidden !important;
          pointer-events: none !important;
        }
      `;
      document.head.appendChild(styleEl);
    }
  } else {
    if (styleEl) styleEl.remove();
  }
};

const applyAssessmentTabLocking = (isLocked, reason = "Assessment Mode") => {
  window.__dsaTutorAssessmentLocked = !!isLocked;
  window.__dsaTutorLockReason = reason || "Assessment Mode";

  injectLockCSS(isLocked);

  try {
    const pathname = window.location.pathname.toLowerCase();
    const isForbiddenRoute = (
      pathname.includes("/solutions") ||
      pathname.includes("/editorial") ||
      pathname.includes("/discussion") ||
      pathname.includes("/submissions") ||
      pathname.includes("/community")
    );

    let lockOverlay = document.getElementById("dsa-tutor-tab-lock-overlay");

    if (window.monaco?.editor?.getModels) {
      const models = window.monaco.editor.getModels();
      models.forEach(patchMonacoModel);
    }

    if (isLocked) {
      // Find all tab links / buttons matching Solutions, Editorial, Discussion, or Submissions
      const allElements = Array.from(
        document.querySelectorAll('a, button, div, span, li')
      );

      allElements.forEach(el => {
        if (el.children.length > 5) return;

        const text = (el.textContent || "").trim().toLowerCase();
        const href = (el.getAttribute("href") || "").toLowerCase();
        const dataPath = (el.getAttribute("data-layout-path") || "").toLowerCase();
        const idStr = (el.id || "").toLowerCase();

        const isForbiddenTab = (
          text === "editorial" || text === "solutions" || text === "solution" || text === "discussion" || text === "discussions" ||
          text === "submissions" || text === "submission" || text === "my submissions" ||
          text.includes("official solution") || text.includes("community solutions") ||
          href.includes("/editorial") || href.includes("/solutions") || href.includes("/discussion") || href.includes("/submissions") ||
          dataPath.includes("editorial") || dataPath.includes("solutions") || dataPath.includes("discussion") || dataPath.includes("submissions") ||
          idStr.includes("editorial") || idStr.includes("solutions") || idStr.includes("discussion") || idStr.includes("submissions")
        );

        if (isForbiddenTab) {
          el.style.setProperty("display", "none", "important");
          el.style.setProperty("visibility", "hidden", "important");
          el.style.setProperty("pointer-events", "none", "important");
          el.setAttribute("data-dsa-tab-locked", "true");
        }
      });

      // If user is currently on an Editorial/Solutions/Discussion/Submissions URL route or panel:
      if (isForbiddenRoute) {
        // Try to click the Description / Problem tab to revert
        const descTab = Array.from(document.querySelectorAll('a, button, div, span')).find(el => {
          const txt = (el.textContent || "").trim().toLowerCase();
          const href = (el.getAttribute("href") || "").toLowerCase();
          return txt === "description" || txt === "problem" || href.includes("/description");
        });
        if (descTab) {
          descTab.click();
        }

        // Add a cover overlay over the solutions / editorial container if rendered
        const panelContainer = document.querySelector(
          "[class*='editorial'], [class*='solution'], [class*='discussion'], [class*='submission'], div[data-track-load='editorial_content'], div[class*='description-container']"
        ) || document.querySelector("#qd-content, .flex-col");

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
              <div style="font-size: 15px; font-weight: 700; color: #ef4444; margin-bottom: 8px;">Solutions, Editorial, Discussion & Submissions Locked</div>
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
        el.removeAttribute("data-dsa-tab-locked");
      });
    }
  } catch (e) {
    console.warn("[DSA Tutor Injected] Error applying tab locking:", e);
  }
};

// Intercept clicks on Solutions / Editorial / Discussion / Submissions tabs when locked
document.addEventListener("click", (e) => {
  if (!window.__dsaTutorAssessmentLocked) return;

  const target = e.target;
  const closestNav = target ? target.closest("a, button, [role='tab'], div, span, li") : null;
  if (!closestNav) return;

  const text = (closestNav.textContent || "").trim().toLowerCase();
  const href = (closestNav.getAttribute("href") || "").toLowerCase();
  const dataPath = (closestNav.getAttribute("data-layout-path") || "").toLowerCase();

  const isForbidden = (
    text === "editorial" || text === "solutions" || text === "solution" || text === "discussion" || text === "discussions" ||
    text === "submissions" || text === "submission" || text === "my submissions" ||
    text.includes("official solution") || text.includes("community solutions") ||
    href.includes("/editorial") || href.includes("/solutions") || href.includes("/discussion") || href.includes("/submissions") ||
    dataPath.includes("editorial") || dataPath.includes("solutions") || dataPath.includes("discussion") || dataPath.includes("submissions")
  );

  if (isForbidden) {
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    applyAssessmentTabLocking(true, window.__dsaTutorLockReason);
    return false;
  }
}, true);

const cleanStarterCode = (codeText) => {
  if (!codeText || typeof codeText !== "string") return "";
  
  const lines = codeText.split("\n");
  const cleanedLines = [];
  let insideCommentBlock = false;
  let inMethodBody = false;
  let methodBraceDepth = 0;
  const isPython = lines.some(l => l.trim().startsWith("def "));

  if (isPython) {
    let inDef = false;
    for (let line of lines) {
      const trimmed = line.trim();
      if (line.startsWith("#") || trimmed.startsWith("class ") || trimmed.startsWith("from ") || trimmed.startsWith("import ")) {
        cleanedLines.push(line);
        inDef = false;
      } else if (trimmed.startsWith("def ")) {
        cleanedLines.push(line);
        cleanedLines.push("        pass");
        inDef = true;
      } else if (!inDef) {
        cleanedLines.push(line);
      }
    }
    return cleanedLines.join("\n");
  }

  // C-style languages (Java, C++, JS, TS, C#, Go, Rust, Swift)
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    // Preserve comments
    if (trimmed.startsWith("/*")) insideCommentBlock = true;
    if (insideCommentBlock || trimmed.startsWith("//") || trimmed.startsWith("*")) {
      cleanedLines.push(line);
      if (trimmed.endsWith("*/")) insideCommentBlock = false;
      continue;
    }

    // Preserve class / struct / header definitions
    if (
      trimmed.startsWith("class ") ||
      trimmed.startsWith("struct ") ||
      trimmed.startsWith("impl ") ||
      trimmed.startsWith("public class ") ||
      trimmed.startsWith("import ") ||
      trimmed.startsWith("#include") ||
      trimmed.startsWith("package ")
    ) {
      cleanedLines.push(line);
      continue;
    }

    // Detect method signature line ending with { or starting method
    if (!inMethodBody && (trimmed.endsWith("{") || (trimmed.includes("(") && trimmed.includes(")")))) {
      cleanedLines.push(line);
      if (line.includes("{")) {
        inMethodBody = true;
        methodBraceDepth = 1;
        cleanedLines.push("        "); // Blank starter space inside method
      }
      continue;
    }

    if (inMethodBody) {
      if (trimmed.includes("{")) methodBraceDepth++;
      if (trimmed.includes("}")) methodBraceDepth--;

      if (methodBraceDepth <= 0) {
        inMethodBody = false;
        cleanedLines.push(line); // Keep closing brace
      }
      // Skip inner previous solution lines
      continue;
    }

    cleanedLines.push(line);
  }

  return cleanedLines.join("\n");
};

window.addEventListener("message", (event) => {
  // Only accept messages from ourselves
  if (event.source !== window) return;

  if (event.data && event.data.type === "REQUEST_CODE") {
    try {
      const models = window.monaco?.editor?.getModels();
      let code = "";
      if (models && models.length > 0) {
        // Select the model with the largest code payload that isn't a testcase input
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
      // Clear cached initial model values so previous solution isn't re-applied
      window.__dsaTutorInitialModelValues = new Map();

      // Unlock Monaco editor models temporarily to allow setting starter code
      const editors = window.monaco?.editor?.getEditors() || [];
      editors.forEach(ed => ed.updateOptions({ readOnly: false }));

      // 1. Try to click LeetCode's native Reset Code button in DOM
      const resetCandidates = Array.from(document.querySelectorAll(
        'button, div[role="button"], span[role="button"], [data-keyup="reset-code"], [data-track-name="reset_code"], [aria-label*="Reset"], [title*="Reset"], [data-cypress="ResetCode"]'
      ));
      const resetBtn = resetCandidates.find(el => {
        const title = (el.getAttribute('title') || el.getAttribute('aria-label') || el.getAttribute('data-cy') || el.getAttribute('data-track-name') || el.textContent || '').toLowerCase();
        return title.includes('reset') || title.includes('restore') || title.includes('revert');
      });

      if (resetBtn) {
        resetBtn.click();
        setTimeout(() => {
          const confirmBtns = Array.from(document.querySelectorAll('button, div[role="button"]'));
          const confirmBtn = confirmBtns.find(b => {
            const txt = (b.textContent || '').trim().toLowerCase();
            return txt === 'confirm' || txt === 'reset' || txt === 'restore' || txt === 'yes';
          });
          if (confirmBtn) confirmBtn.click();
        }, 150);
      }

      // 2. Clean previous solution code from Monaco models, leaving pristine stubs
      const models = window.monaco?.editor?.getModels();
      if (models && models.length > 0) {
        models.forEach(model => {
          const uriStr = model.uri ? model.uri.toString() : "";
          if (!uriStr.includes("input") && !uriStr.includes("testcase")) {
            const currentVal = model.getValue() || "";
            if (currentVal) {
              const cleaned = cleanStarterCode(currentVal);
              if (cleaned && cleaned.trim().length > 0) {
                model.setValue(cleaned);
              }
            }
          }
        });
      }

      // Re-apply readOnly state if locked
      if (window.__dsaTutorReadOnly) {
        editors.forEach(ed => ed.updateOptions({ readOnly: true }));
      }
    } catch (e) {
      console.error("[DSA Tutor Injected] Error resetting editor:", e);
    }
  }
});

// Continuously enforce readOnly & overlay state while readOnly is active and record initial model values
setInterval(() => {
  if (window.__dsaTutorReadOnly) {
    applyReadOnlyState(true);
  }
  if (window.__dsaTutorAssessmentLocked) {
    applyAssessmentTabLocking(true, window.__dsaTutorLockReason);
  }
  captureModelInitialValues();
}, 400);

console.log("[DSA Tutor Injected] Scraper script loaded in page context.");
