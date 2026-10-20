// background.js: the "messenger". It is the only file that talks to the internet.

// Leave empty to test with FAKE keywords. Later: your backend URL that calls the LLM.
const BACKEND_URL = "";

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type !== "llm") return;

  (async () => {
    if (!BACKEND_URL) {
      sendResponse(JSON.stringify({
        keywords: [
          { term: "test keyword", weight: 1 },
          { term: "another topic", weight: 0.6 }
        ]
      }));
      return;
    }
    const res = await fetch(BACKEND_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ system: msg.system, user: msg.user })
    });
    const data = await res.json();
    sendResponse(data.text); // your backend should return { "text": "<the LLM's JSON string>" }
  })();

  return true; // keeps the channel open for the async answer
});
