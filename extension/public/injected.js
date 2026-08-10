// This script runs in the page context of leetcode.com
// It can access window.monaco to get the current code in the editor.

window.__dsaTutorReadOnly = false;

// Poll and subscribe to new Monaco editors to lock them automatically
const initMonacoListeners = () => {
  if (window.monaco && window.monaco.editor) {
    // Intercept future editor creations
    window.monaco.editor.onDidCreateEditor((editor) => {
      editor.updateOptions({ readOnly: !!window.__dsaTutorReadOnly });
    });
    // Apply to any already instantiated editors
    const editors = window.monaco.editor.getEditors();
    if (editors && editors.length > 0) {
      editors.forEach(ed => {
        ed.updateOptions({ readOnly: !!window.__dsaTutorReadOnly });
      });
    }
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
      
      window.postMessage({ type: "CODE_VALUE", code: code }, "*");
    } catch (e) {
      console.error("[DSA Tutor Injected] Error reading Monaco editor:", e);
      window.postMessage({ type: "CODE_VALUE", code: "", error: e.message }, "*");
    }
  }

  if (event.data && event.data.type === "SET_READ_ONLY") {
    try {
      window.__dsaTutorReadOnly = !!event.data.readOnly;
      const editors = window.monaco?.editor?.getEditors();
      if (editors && editors.length > 0) {
        editors.forEach(editor => {
          editor.updateOptions({ readOnly: !!event.data.readOnly });
        });
      }
    } catch (e) {
      console.error("[DSA Tutor Injected] Error setting readOnly:", e);
    }
  }

  if (event.data && event.data.type === "RESET_EDITOR") {
    try {
      const models = window.monaco?.editor?.getModels();
      if (models && models.length > 0) {
        models.forEach(model => {
          const uriStr = model.uri ? model.uri.toString() : "";
          if (!uriStr.includes("input") && !uriStr.includes("testcase")) {
            model.setValue("");
          }
        });
      }
    } catch (e) {
      console.error("[DSA Tutor Injected] Error resetting editor:", e);
    }
  }
});

// Continuously enforce readOnly state to override any LeetCode internal resets (e.g. language switches or re-renders)
setInterval(() => {
  if (window.__dsaTutorReadOnly && window.monaco && window.monaco.editor) {
    const editors = window.monaco.editor.getEditors();
    if (editors && editors.length > 0) {
      editors.forEach(editor => {
        try {
          const isReadOnly = editor.getOptions ? editor.getOptions().get(window.monaco.editor.EditorOption.readOnly) : false;
          if (!isReadOnly) {
            editor.updateOptions({ readOnly: true });
          }
        } catch (e) {
          editor.updateOptions({ readOnly: true });
        }
      });
    }
  }
}, 300);

console.log("[DSA Tutor Injected] Scraper script loaded in page context.");
