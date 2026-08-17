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

  if (event.data && event.data.type === "RESET_EDITOR") {
    try {
      // Unlock Monaco editor models temporarily to allow setting starter code
      const editors = window.monaco?.editor?.getEditors() || [];
      editors.forEach(ed => ed.updateOptions({ readOnly: false }));

      // 1. Try to click LeetCode's native Reset Code button in DOM
      const resetCandidates = Array.from(document.querySelectorAll('button, div[role="button"], span[role="button"]'));
      const resetBtn = resetCandidates.find(el => {
        const title = (el.getAttribute('title') || el.getAttribute('aria-label') || el.textContent || '').toLowerCase();
        return title.includes('reset') || title.includes('restore') || title.includes('revert');
      });

      if (resetBtn) {
        resetBtn.click();
        setTimeout(() => {
          const confirmBtns = Array.from(document.querySelectorAll('button'));
          const confirmBtn = confirmBtns.find(b => {
            const txt = (b.textContent || '').trim().toLowerCase();
            return txt === 'confirm' || txt === 'reset' || txt === 'restore' || txt === 'yes';
          });
          if (confirmBtn) confirmBtn.click();
        }, 150);
      }

      // 2. Clear previous code from Monaco models, keeping only starter signatures
      const models = window.monaco?.editor?.getModels();
      if (models && models.length > 0) {
        models.forEach(model => {
          const uriStr = model.uri ? model.uri.toString() : "";
          if (!uriStr.includes("input") && !uriStr.includes("testcase")) {
            const val = model.getValue() || "";
            if (val) {
              const lines = val.split("\n");
              const stubLines = [];
              let headerFound = false;
              for (let line of lines) {
                const trimmed = line.trim();
                if (
                  line.includes("class ") ||
                  line.includes("def ") ||
                  line.includes("public ") ||
                  line.includes("function ") ||
                  line.includes("var ") ||
                  line.includes("func ") ||
                  line.includes("impl ") ||
                  line.includes("#include") ||
                  line.includes("import ")
                ) {
                  stubLines.push(line);
                  headerFound = true;
                } else if (headerFound && (trimmed === "}" || trimmed === "};" || trimmed === "")) {
                  stubLines.push(line);
                }
              }

              if (stubLines.length >= 2) {
                const hasPythonDef = stubLines.some(l => l.trim().startsWith("def "));
                if (hasPythonDef && !stubLines.some(l => l.includes("pass"))) {
                  const defIdx = stubLines.findIndex(l => l.trim().startsWith("def "));
                  stubLines.splice(defIdx + 1, 0, "        pass");
                }
                model.setValue(stubLines.join("\n"));
              } else {
                model.setValue("");
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

// Continuously enforce readOnly & overlay state while readOnly is active
setInterval(() => {
  if (window.__dsaTutorReadOnly) {
    applyReadOnlyState(true);
  }
}, 400);

console.log("[DSA Tutor Injected] Scraper script loaded in page context.");
