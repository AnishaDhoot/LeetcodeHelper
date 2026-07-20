// This script runs in the page context of leetcode.com
// It can access window.monaco to get the current code in the editor.

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
      } else {
        console.warn("[DSA Tutor Injected] No Monaco models found.");
      }
      
      window.postMessage({ type: "CODE_VALUE", code: code }, "*");
    } catch (e) {
      console.error("[DSA Tutor Injected] Error reading Monaco editor:", e);
      window.postMessage({ type: "CODE_VALUE", code: "", error: e.message }, "*");
    }
  }

  if (event.data && event.data.type === "SET_READ_ONLY") {
    try {
      const editors = window.monaco?.editor?.getEditors();
      if (editors && editors.length > 0) {
        editors[0].updateOptions({ readOnly: !!event.data.readOnly });
      }
    } catch (e) {
      console.error("[DSA Tutor Injected] Error setting readOnly:", e);
    }
  }
});

console.log("[DSA Tutor Injected] Scraper script loaded in page context.");
