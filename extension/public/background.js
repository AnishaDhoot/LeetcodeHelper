// Chrome Extension Service Worker (background.js)
// Handles API calls to the local FastAPI backend to bypass CORS and extension constraints,
// and fetches the user's LeetCode solved-problem history via the GraphQL API.

const BACKEND_URL = "http://localhost:8000";

// Generic JSON POST/GET helper that resolves sendResponse.
async function backendFetch(path, { method = "GET", body } = {}) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(`${BACKEND_URL}${path}`, opts);
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return res.json();
}

// Fetch the logged-in user's solved problems from LeetCode's GraphQL endpoint.
// Runs in the service worker, so session cookies for leetcode.com are sent automatically.
async function fetchSolvedProblems() {
  // Common headers required by LeetCode's GraphQL endpoint
  const LC_HEADERS = {
    "Content-Type": "application/json",
    "Referer": "https://leetcode.com"
  };

  // 1. Resolve the signed-in username from the global badge / progress query.
  const statusQuery = {
    query: `query globalData { userStatus { username isSignedIn } }`,
    variables: {}
  };
  const statusRes = await fetch("https://leetcode.com/graphql/", {
    method: "POST",
    headers: LC_HEADERS,
    credentials: "include",
    body: JSON.stringify(statusQuery)
  });
  if (!statusRes.ok) throw new Error(`LeetCode status HTTP ${statusRes.status}`);
  const statusData = await statusRes.json();
  const username = statusData?.data?.userStatus?.username;
  const isSignedIn = statusData?.data?.userStatus?.isSignedIn;
  if (!isSignedIn || !username) {
    throw new Error("Not signed in to LeetCode. Please log in and try again.");
  }

  // 2. Fetch accepted submissions using recentAcSubmissionList (works on current LeetCode API).
  //    The API returns up to 20 per call, so we call multiple times with increasing limits
  //    to collect as many unique solved problems as possible (cap at 200 to be safe).
  const BATCH_SIZE = 20;
  const MAX_PROBLEMS = 200;
  const seenSlugs = new Set();
  const rawProblems = []; // {titleSlug, title}

  for (let limit = BATCH_SIZE; limit <= MAX_PROBLEMS; limit += BATCH_SIZE) {
    const acQuery = {
      query: `query recentAcSubmissions($username: String!, $limit: Int!) {
        recentAcSubmissionList(username: $username, limit: $limit) {
          id
          title
          titleSlug
          timestamp
        }
      }`,
      variables: { username, limit }
    };
    const acRes = await fetch("https://leetcode.com/graphql/", {
      method: "POST",
      headers: LC_HEADERS,
      credentials: "include",
      body: JSON.stringify(acQuery)
    });
    if (!acRes.ok) throw new Error(`LeetCode AC submissions HTTP ${acRes.status}`);
    const acData = await acRes.json();
    const submissions = acData?.data?.recentAcSubmissionList || [];

    // Deduplicate by titleSlug
    let newFound = 0;
    for (const s of submissions) {
      if (!seenSlugs.has(s.titleSlug)) {
        seenSlugs.add(s.titleSlug);
        rawProblems.push({ titleSlug: s.titleSlug, title: s.title });
        newFound++;
      }
    }

    // If the API returned fewer items than requested, we've got everything
    if (submissions.length < limit || newFound === 0) break;
  }

  // 3. Fetch topic tags + difficulty for each unique problem via questionData query.
  //    LeetCode's public questionData query works per-slug and doesn't require auth.
  const problems = [];
  for (const { titleSlug, title } of rawProblems) {
    try {
      const qQuery = {
        query: `query questionData($titleSlug: String!) {
          question(titleSlug: $titleSlug) {
            difficulty
            topicTags { name }
          }
        }`,
        variables: { titleSlug }
      };
      const qRes = await fetch("https://leetcode.com/graphql/", {
        method: "POST",
        headers: LC_HEADERS,
        credentials: "include",
        body: JSON.stringify(qQuery)
      });
      let difficulty = "Medium";
      let topics = ["Arrays & Hashing"];
      if (qRes.ok) {
        const qData = await qRes.json();
        const q = qData?.data?.question;
        if (q) {
          difficulty = q.difficulty || difficulty;
          const tags = (q.topicTags || []).map((t) => t.name);
          if (tags.length > 0) topics = tags;
        }
      }
      problems.push({ problem_id: titleSlug, title, difficulty, topics });
    } catch (_) {
      // If a single problem detail fetch fails, push with defaults rather than aborting.
      problems.push({ problem_id: titleSlug, title, difficulty: "Medium", topics: ["Arrays & Hashing"] });
    }
  }

  return problems;
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log("[DSA Tutor Background] Received message:", request);

  // --- Backend passthrough actions ---
  if (request.action === "analyze_submission") {
    backendFetch("/submissions/analyze", { method: "POST", body: request.payload })
      .then((data) => sendResponse({ success: true, data }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true; // Keep message channel open for async response
  }

  if (request.action === "get_mastery") {
    backendFetch("/topics/mastery")
      .then((data) => sendResponse({ success: true, data }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (request.action === "get_recommendation") {
    backendFetch("/problems/next")
      .then((data) => sendResponse({ success: true, data }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (request.action === "record_success") {
    const { problem_id, topic } = request.payload;
    backendFetch(`/submissions/success?problem_id=${problem_id}&topic=${encodeURIComponent(topic)}`, { method: "POST" })
      .then((data) => sendResponse({ success: true, data }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true;
  }

  // --- Code Coach actions ---
  if (request.action === "check_approach") {
    backendFetch("/approach/check", { method: "POST", body: request.payload })
      .then((data) => sendResponse({ success: true, data }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (request.action === "get_hint") {
    backendFetch("/hints/get", { method: "POST", body: request.payload })
      .then((data) => sendResponse({ success: true, data }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (request.action === "get_edge_cases") {
    backendFetch("/edge-cases/get", { method: "POST", body: request.payload })
      .then((data) => sendResponse({ success: true, data }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (request.action === "ask_help") {
    backendFetch("/help/ask", { method: "POST", body: request.payload })
      .then((data) => sendResponse({ success: true, data }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (request.action === "check_health") {
    backendFetch("/health")
      .then((data) => sendResponse({ success: true, data }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (request.action === "sync_solved") {
    backendFetch("/sync/solved", { method: "POST", body: request.payload })
      .then((data) => sendResponse({ success: true, data }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true;
  }

  // --- LeetCode history fetch (uses logged-in session cookies) ---
  if (request.action === "fetch_leetcode_history") {
    fetchSolvedProblems()
      .then((problems) => sendResponse({ success: true, data: { problems } }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true;
  }
});
