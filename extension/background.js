chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
const pages = new Set([
  'https://docs.python.org/3/tutorial/',
  'https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide',
]);
const backends = new Set(['http://127.0.0.1:8000', 'http://localhost:8000']);
const localDemo = url => /^http:\/\/(127\.0\.0\.1|localhost):8000\/demo$/.test(url || '');
async function send(path, body) {
  const { backend = 'http://127.0.0.1:8000', token = '' } = await chrome.storage.local.get(['backend', 'token']);
  if (!backends.has(backend)) throw new Error('Use the local backend on port 8000');
  const response = await fetch(backend + '/api/v1' + path, {
    method: body ? 'POST' : 'GET',
    headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const problem = await response.json().catch(() => ({}));
    throw new Error('Backend returned HTTP ' + response.status + ': ' +
      (problem.error?.fields?.join(', ') || problem.error?.message || 'Review consent and budget'));
  }
  return response.json();
}
async function sha(text) {
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text))))
    .map(b => b.toString(16).padStart(2, '0')).join('');
}
async function stop() {
  const { observedTab, grantId } = await chrome.storage.session.get(['observedTab', 'grantId']);
  await chrome.storage.session.remove(['observedTab', 'observedUrl', 'grantId', 'latest', 'selected', 'noteId']);
  if (grantId) await send('/browser-experience/grants/' + grantId + '/revoke', {}).catch(() => {});
  if (observedTab) {
    await chrome.scripting.executeScript({ target: { tabId: observedTab }, func: () => {
      globalThis.__aliveObserver?.disconnect();
      clearTimeout(globalThis.__aliveTimer);
      delete globalThis.__aliveObserver;
    }}).catch(() => {});
  }
}
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  (async () => {
    if (message.type === 'observation' && sender.tab) {
      const { observedTab, observedUrl } = await chrome.storage.session.get(['observedTab', 'observedUrl']);
      if (observedTab !== sender.tab.id || sender.tab.url !== observedUrl || message.payload.url !== observedUrl)
        return { ignored: true };
      const payload = { url: observedUrl, title: String(message.payload.title).slice(0, 200),
        text: String(message.payload.text).slice(0, pages.has(observedUrl) ? 3000 : 8000), tab_id: observedTab };
      const observation = { event_id: crypto.randomUUID(), event_type: 'browser.dom_changed', source: 'extension', payload };
      await chrome.storage.session.set({ latest: observation });
      // Real pages always require an explicit preview click. No background Meta calls.
      const { autoSend = false } = await chrome.storage.local.get('autoSend');
      if (autoSend && localDemo(observedUrl)) await send('/events', observation);
      return { ok: true };
    }
    if (sender.id !== chrome.runtime.id || !sender.url?.startsWith(chrome.runtime.getURL('')))
      throw new Error('Only extension UI may control the connection');
    if (message.type === 'connect') return send('/alive');
    if (message.type === 'goals') return send('/browser-experience');
    if (message.type === 'goal') {
      const goal = await send('/browser-experience/goals', { instruction: message.instruction });
      await chrome.storage.local.set({ goalId: goal.id });
      return goal;
    }
    if (message.type === 'start') {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab?.id || (!pages.has(tab.url) && !localDemo(tab.url)))
        throw new Error('Choose one of the two authorised documentation pages and click the ALIVE toolbar icon');
      await stop();
      let grantId = null;
      if (pages.has(tab.url)) {
        const { goalId } = await chrome.storage.local.get('goalId');
        if (!goalId) throw new Error('Save or resume a goal first');
        const grant = await send('/browser-experience/grants', {
          goal_id: goalId, url: tab.url, tab_key: crypto.randomUUID() + ':' + tab.id, approved: true,
        });
        grantId = grant.id;
      }
      await chrome.storage.session.set({ observedTab: tab.id, observedUrl: tab.url, grantId });
      try {
        await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['observer.js'] });
      } catch (error) { await stop(); throw error; }
      return { ok: true, tabId: tab.id };
    }
    if (message.type === 'stop') { await stop(); return { ok: true }; }
    if (message.type === 'send') {
      const { latest, grantId, observedTab, observedUrl } = await chrome.storage.session.get(['latest', 'grantId', 'observedTab', 'observedUrl']);
      if (!latest || JSON.stringify(message.reviewed) !== JSON.stringify(latest.payload))
        throw new Error('Preview changed. Review the current excerpt again');
      const tab = await chrome.tabs.get(observedTab);
      if (tab.url !== observedUrl) { await stop(); throw new Error('Page changed; authorise again'); }
      if (localDemo(latest.payload.url)) return send('/events', latest);
      const result = await send('/browser-experience/snapshots', {
        grant_id: grantId, url: latest.payload.url, title: latest.payload.title,
        text: latest.payload.text, reviewed_sha256: await sha(latest.payload.text),
      });
      await chrome.storage.session.set({ selected: result,
        noteId: result.decision.note?.id || result.decision.candidate_note?.id || null });
      return result;
    }
    if (message.type === 'analyse') {
      const { selected, grantId, latest, observedTab, observedUrl } = await chrome.storage.session.get(['selected', 'grantId', 'latest', 'observedTab', 'observedUrl']);
      if (!selected || selected.snapshot.parent_id !== grantId) throw new Error('Review and save an excerpt first');
      if (!latest || await sha(latest.payload.text) !== selected.snapshot.data.sha256 ||
          (await chrome.tabs.get(observedTab)).url !== observedUrl)
        throw new Error('Page changed. Review the current excerpt again');
      const result = await send('/browser-experience/analyse', {
        snapshot_id: selected.snapshot.id, reviewed_sha256: selected.snapshot.data.sha256, send_to_meta: true,
      });
      await chrome.storage.session.set({ noteId: result.id });
      return result;
    }
    if (message.type === 'note') {
      const { noteId } = await chrome.storage.session.get('noteId');
      return noteId ? send('/browser-experience/notes/' + noteId) : null;
    }
    if (message.type === 'feedback') {
      const { noteId } = await chrome.storage.session.get('noteId');
      if (!noteId) throw new Error('Review and select a note before rating it');
      return send('/browser-experience/feedback', { note_id: noteId, useful: message.useful });
    }
    throw new Error('Unsupported extension command');
  })().then(data => reply({ data })).catch(error => reply({ error: error.message }));
  return true;
});
chrome.tabs.onRemoved.addListener(async tabId => {
  const { observedTab } = await chrome.storage.session.get('observedTab');
  if (observedTab === tabId) await stop();
});
chrome.tabs.onUpdated.addListener(async (tabId, change) => {
  const { observedTab } = await chrome.storage.session.get('observedTab');
  if (observedTab === tabId && (change.status === 'loading' || change.url)) await stop();
});
