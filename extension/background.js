chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
const allowedBackends = new Set([
  "http://127.0.0.1:8000",
  "http://localhost:8000",
]);
async function send(path, body) {
  const { backend = "http://127.0.0.1:8000", token = "" } =
    await chrome.storage.local.get(["backend", "token"]);
  if (!allowedBackends.has(backend))
    throw new Error("Use the configured local backend on port 8000");
  const response = await fetch(backend + "/api/v1" + path, {
    method: body ? "POST" : "GET",
    headers: {
      Authorization: "Bearer " + token,
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) throw new Error("Backend returned HTTP " + response.status);
  return response.json();
}
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  (async () => {
    if (message.type === "observation" && sender.tab) {
      const { observedTab } = await chrome.storage.session.get("observedTab");
      if (observedTab !== sender.tab.id) return { ignored: true };
      const observation = {
        event_id: crypto.randomUUID(),
        event_type: "browser.dom_changed",
        source: "extension",
        payload: { ...message.payload, tab_id: sender.tab.id },
      };
      // Observation stays local until explicitly sent or auto-observation is authorised.
      await chrome.storage.session.set({ latest: observation });
      const { autoSend = false } = await chrome.storage.local.get("autoSend");
      if (autoSend) await send("/events", observation);
      return { ok: true };
    }
    if (
      sender.id !== chrome.runtime.id ||
      !sender.url?.startsWith(chrome.runtime.getURL(""))
    )
      throw new Error("Only extension UI may control the connection");
    if (message.type === "connect") return send("/alive");
    if (message.type === "send") {
      const { latest } = await chrome.storage.session.get("latest");
      if (!latest) throw new Error("No observation selected");
      return send("/events", latest);
    }
    if (message.type === "start") {
      const [tab] = await chrome.tabs.query({
        active: true,
        currentWindow: true,
      });
      if (!tab?.id || !/^https?:/.test(tab.url || ""))
        throw new Error("Select an HTTP page and click the ALIVE toolbar icon");
      const { observedTab } = await chrome.storage.session.get("observedTab");
      if (observedTab && observedTab !== tab.id) await stop(observedTab);
      await chrome.storage.session.set({ observedTab: tab.id });
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ["observer.js"],
      });
      return { ok: true, tabId: tab.id };
    }
    if (message.type === "stop") {
      const { observedTab } = await chrome.storage.session.get("observedTab");
      if (observedTab) await stop(observedTab);
      await chrome.storage.session.remove(["observedTab", "latest"]);
      return { ok: true };
    }
    throw new Error("Unsupported extension command");
  })()
    .then((data) => reply({ data }))
    .catch((error) => reply({ error: error.message }));
  return true;
});
async function stop(tabId) {
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        globalThis.__aliveObserver?.disconnect();
        clearTimeout(globalThis.__aliveTimer);
        delete globalThis.__aliveObserver;
      },
    });
  } catch {
    /* tab already closed or grant revoked */
  }
}
chrome.tabs.onRemoved.addListener(async (tabId) => {
  const { observedTab } = await chrome.storage.session.get("observedTab");
  if (observedTab === tabId)
    await chrome.storage.session.remove(["observedTab", "latest"]);
});
