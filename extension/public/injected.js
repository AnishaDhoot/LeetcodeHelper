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
        // Find the main editor model (usually the first one or the one with content)
        // For LeetCode, getModels()[0] is standard.
        code = models[0].getValue();
      } else {
        console.warn("[DSA Tutor Injected] No Monaco models found.");
      }
      
      window.postMessage({ type: "CODE_VALUE", code: code }, "*");
    } catch (e) {
      console.error("[DSA Tutor Injected] Error reading Monaco editor:", e);
      window.postMessage({ type: "CODE_VALUE", code: "", error: e.message }, "*");
    }
  }
});

console.log("[DSA Tutor Injected] Scraper script loaded in page context.");
