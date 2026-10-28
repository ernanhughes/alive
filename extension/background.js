import { AUTHORISED_PAGES, DEFAULT_BACKEND, DEFAULT_BACKENDS, isLocalDemo } from './config.js';
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
const pages = new Set(AUTHORISED_PAGES);
const backends = new Set(DEFAULT_BACKENDS);
const localDemo = isLocalDemo;
async function send(path, body) {
  const { backend = DEFAULT_BACKEND, token = '' } = await chrome.storage.local.get(['backend', 'token']);
  if (!backends.has(backend)) throw new Error('Configured local backend is not allowed');
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
      if (message.payload.capture_format_version === 2) {
        payload.text = Array.from(String(message.payload.text)).slice(0, pages.has(observedUrl) ? 3000 : 8000).join('');
        payload.capture_format_version = 2;
        payload.capture_entries = (message.payload.capture_entries || [])
          .filter(entry => entry.start < Array.from(payload.text).length)
          .map(entry => ({ ...entry, end: Math.min(entry.end, Array.from(payload.text).length) }));
      }
      const observation = { event_id: crypto.randomUUID(), event_type: 'browser.dom_changed', source: 'extension', payload };
      await chrome.storage.session.set({ latest: observation });
      // Real pages always require an explicit preview click. No background Meta calls.
      const { autoSend = false } = await chrome.storage.local.get('autoSend');
      if (autoSend && localDemo(observedUrl)) await send('/events', observation);
      return { ok: true };
    }
    if (sender.id !== chrome.runtime.id || !sender.url?.startsWith(chrome.runtime.getURL('')))
      throw new Error('Only extension UI may control the connection');
    if (message.type === 'connect') {
      const provenance = await send('/provenance');
      if (provenance.protocol_version !== 1 || !provenance.runtime_sha256)
        throw new Error('Backend identity is unavailable; update the local runtime');
      await chrome.storage.session.set({ backendProvenance: provenance });
      return { ...await send('/alive'), provenance };
    }
    if (message.type === 'goals') return send('/browser-experience');
    if (message.type === 'goal') {
      const goal = await send('/browser-experience/goals', { instruction: message.instruction });
      await chrome.storage.local.set({ goalId: goal.id });
      return goal;
    }
    if (message.type === 'start') {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab?.id || (!pages.has(tab.url) && !localDemo(tab.url)))
        throw new Error('Choose an authorised research page and click the ALIVE toolbar icon');
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
        await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['capture.js', 'observer.js'] });
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
        language: message.language || 'auto',
        ...(latest.payload.capture_format_version === 2 ? {
          capture_format_version: 2, capture_entries: latest.payload.capture_entries || [],
        } : {}),
      });
      await chrome.storage.session.set({ selected: result,
        noteId: result.decision.note?.id || null });
      return result;
    }
    if (message.type === 'analyse') {
      const { selected, grantId, latest, observedTab, observedUrl } = await chrome.storage.session.get(['selected', 'grantId', 'latest', 'observedTab', 'observedUrl']);
      if (!selected || selected.snapshot.parent_id !== grantId) throw new Error('Review and save an excerpt first');
      if (!latest || await sha(latest.payload.text) !== selected.snapshot.data.sha256 ||
          (await chrome.tabs.get(observedTab)).url !== observedUrl)
        throw new Error('Page changed. Review the current excerpt again');
      const result = await send('/browser-experience/analyse', {
        snapshot_id: selected.snapshot.id, reviewed_sha256: selected.snapshot.data.sha256,
        send_to_meta: true, allow_uncertain_analysis: !!message.allow_uncertain_analysis,
        owner_correction: !!message.owner_correction,
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
    if (message.type === 'save-research') {
      const { noteId } = await chrome.storage.session.get('noteId');
      if (!noteId) throw new Error('Review and select a validated note before saving research memory');
      const result = await send('/browser-experience/research/memories', { note_id: noteId });
      await chrome.storage.session.set({ researchId: result.id });
      return result;
    }
    if (message.type === 'find-research') {
      const { selected } = await chrome.storage.session.get('selected');
      if (!selected?.snapshot?.id) throw new Error('Review an observation before finding related research');
      return send('/browser-experience/research/retrieve', {
        snapshot_id: selected.snapshot.id, top_k: 3, mode: 'hybrid',
      });
    }
    if (message.type === 'connection') {
      const { selected } = await chrome.storage.session.get('selected');
      if (!selected?.snapshot?.id || !message.memoryId)
        throw new Error('Select a historical research item first');
      const result = await send('/browser-experience/research/connections', {
        snapshot_id: selected.snapshot.id, memory_id: message.memoryId,
      });
      await chrome.storage.session.set({ connectionId: result.id });
      return result;
    }
    if (message.type === 'connection-feedback') {
      const { connectionId } = await chrome.storage.session.get('connectionId');
      if (!connectionId) throw new Error('No research connection selected');
      return send('/browser-experience/research/connections/' + connectionId + '/feedback', message.rubric || {
        useful: message.useful,
      });
    }
    if (message.type === 'preview-relationship') {
      const { selected } = await chrome.storage.session.get('selected');
      if (!selected?.snapshot?.id || !message.memoryId)
        throw new Error('Select a historical research item first');
      return send('/browser-experience/research/outbound/preview', {
        snapshot_id: selected.snapshot.id,
        research_id: message.memoryId,
        provider: message.provider || 'local_stub',
      });
    }
    if (message.type === 'authorize-relationship') {
      if (!message.consentId || !message.payloadSha256)
        throw new Error('Preview the exact outbound payload first');
      return send('/browser-experience/research/outbound/authorize', {
        consent_id: message.consentId,
        payload_sha256: message.payloadSha256,
        approved: true,
      });
    }
    if (message.type === 'analyse-relationship') {
      if (!message.consentId) throw new Error('Authorise the outbound payload first');
      return send('/browser-experience/research/relationships', {
        consent_id: message.consentId,
      });
    }
    if (message.type === 'relationship-feedback') {
      if (!message.connectionId || !message.rubric)
        throw new Error('Select a relationship and provide an assessment');
      return send('/browser-experience/research/connections/' + message.connectionId + '/feedback', {
        ...message.rubric,
      });
    }
    if (message.type === 'evidence-findings') {
      const { goalId } = await chrome.storage.local.get('goalId');
      if (!goalId) throw new Error('Select a research goal before checking evidence');
      return send('/browser-experience/research/relationships?goal_id=' + encodeURIComponent(goalId));
    }
    if (message.type === 'live-context') {
      const { goalId } = await chrome.storage.local.get('goalId');
      const { selected, latest } = await chrome.storage.session.get(['selected', 'latest']);
      if (!goalId) return { goal: null, current: null, related: [], findings: [] };
      const [state, memoryListing, ledger] = await Promise.all([
        send('/browser-experience'),
        send('/browser-experience/research/memories?goal_id=' + encodeURIComponent(goalId)),
        send('/browser-experience/research/relationships?goal_id=' + encodeURIComponent(goalId)),
      ]);
      const memories = memoryListing.memories;
      const current = selected?.snapshot?.data?.goal_id === goalId ? selected.snapshot : null;
      let related = [];
      if (current) {
        try {
          related = (await send('/browser-experience/research/retrieve', {
            snapshot_id: current.id, mode: 'text',
          })).results.filter(row => row.reliance_anchor?.quote && !row.same_source);
        } catch { /* Expired page permission cannot grant a new comparison. */ }
      }
      return { goal: state.goals.find(row => row.id === goalId), current,
        captured: latest?.payload || null,
        memory: current ? memories.find(row => row.data.sha256 === current.data.sha256 && row.data.url === current.data.url) : null,
        related, findings: ledger.connections.filter(row => row.status === 'candidate' &&
          row.data.analysis_version === 'alive-demo01-claim-v2' && row.data.owner_useful !== false &&
          row.data.provider?.id === 'local_fixture_claim' &&
          row.data.validation?.capture_binding === 'pinned_source_entry_v2'),
        analyses: ledger.analyses.filter(row => row.data.analysis_mode === 'claim_comparison') };
    }
    if (message.type === 'live-selection') {
      const { observedTab, observedUrl, grantId, latest } = await chrome.storage.session.get(['observedTab', 'observedUrl', 'grantId', 'latest']);
      const { goalId } = await chrome.storage.local.get('goalId');
      if (!goalId || !grantId || !latest || latest.payload.capture_format_version !== 2)
        throw new Error('Select an investigation and authorise this page before remembering a passage.');
      if ((await chrome.tabs.get(observedTab)).url !== observedUrl) throw new Error('Page changed; authorise it again.');
      const values = await chrome.scripting.executeScript({ target: { tabId: observedTab }, func: () => {
        const selection = window.getSelection();
        if (!selection?.rangeCount || selection.isCollapsed) return null;
        const content = document.querySelector('main,article,[role="main"]') || document.body;
        return globalThis.__aliveCaptureV2(content, 3000, selection.getRangeAt(0));
      }});
      const value = values[0]?.result;
      if (!value?.selection?.quote) throw new Error('Select visible text inside the retained source excerpt.');
      if (value.text !== latest.payload.text) throw new Error('Capture changed; review this source again.');
      const { memories } = await send('/browser-experience/research/memories?goal_id=' + encodeURIComponent(goalId));
      const expectedSha = await sha(value.text);
      const memory = memories.find(row => row.data.sha256 === expectedSha && row.data.url === observedUrl);
      return { ...value.selection, reviewed: latest.payload, expected_sha256: expectedSha,
        expected_revision: memory?.data?.reliance_anchor?.revision || 0,
        previous_anchor: memory?.data?.reliance_anchor || null,
        goal_id: goalId, source_identity: memory?.data?.source_identity || null };
    }
    if (message.type === 'live-remember') {
      const { observedTab, observedUrl, grantId, latest } = await chrome.storage.session.get(['observedTab', 'observedUrl', 'grantId', 'latest']);
      const { goalId } = await chrome.storage.local.get('goalId');
      if (!latest || !grantId || message.proposal?.goal_id !== goalId ||
          JSON.stringify(message.proposal.reviewed) !== JSON.stringify(latest.payload) ||
          await sha(latest.payload.text) !== message.proposal.expected_sha256 ||
          (await chrome.tabs.get(observedTab)).url !== observedUrl)
        throw new Error('Source or investigation changed. Select the passage again.');
      const snapshot = await send('/browser-experience/snapshots', {
        grant_id: grantId, url: observedUrl, title: latest.payload.title,
        text: latest.payload.text, reviewed_sha256: message.proposal.expected_sha256,
        capture_format_version: 2, capture_entries: latest.payload.capture_entries || [],
      });
      if (snapshot.snapshot.data.goal_id !== goalId) throw new Error('Investigation changed; authorise the page again.');
      const memory = await send('/browser-experience/research/memories', { snapshot_id: snapshot.snapshot.id });
      const anchored = await send('/browser-experience/research/memories/' + memory.id + '/anchor', {
        quote: message.proposal.quote, occurrence_start: message.proposal.occurrence_start,
        expected_sha256: message.proposal.expected_sha256, expected_revision: message.proposal.expected_revision,
      });
      await chrome.storage.session.set({ selected: snapshot });
      return anchored;
    }
    if (message.type === 'live-preview') {
      const { selected, latest, observedTab } = await chrome.storage.session.get(['selected', 'latest', 'observedTab']);
      const { goalId } = await chrome.storage.local.get('goalId');
      if (!selected?.snapshot?.id || selected.snapshot.data.goal_id !== goalId)
        throw new Error('Review a source in the active investigation first.');
      if (!latest || await sha(latest.payload.text) !== selected.snapshot.data.sha256 ||
          (await chrome.tabs.get(observedTab)).url !== selected.snapshot.data.url)
        throw new Error('Capture changed; review this source again before checking evidence.');
      return send('/browser-experience/research/outbound/preview', {
        snapshot_id: selected.snapshot.id, research_id: message.memoryId,
        analysis_mode: 'claim_comparison', provider: 'local_fixture_claim',
      });
    }
    if (message.type === 'live-cancel')
      return send('/browser-experience/research/outbound/' + encodeURIComponent(message.consentId) + '/revoke', {});
    if (message.type === 'live-feedback') {
      const { goalId } = await chrome.storage.local.get('goalId');
      const ledger = await send('/browser-experience/research/relationships?goal_id=' + encodeURIComponent(goalId || ''));
      if (!goalId || !ledger.connections.some(row => row.id === message.connectionId && row.data.analysis_version === 'alive-demo01-claim-v2'))
        throw new Error('This finding is not active in the selected investigation.');
      return send('/browser-experience/research/connections/' + message.connectionId + '/feedback', { useful: message.useful });
    }
    if (message.type === 'campaigns') return send('/browser-experience/research/experiment/campaigns');
    if (message.type === 'campaign-state') {
      if (!message.digest) throw new Error('Select a campaign');
      return send('/browser-experience/research/experiment/campaigns/' + message.digest + '/state');
    }
    if (message.type === 'active-approval') {
      if (!message.digest) throw new Error('Select a campaign');
      return send('/browser-experience/research/experiment/approvals?campaign_digest=' + encodeURIComponent(message.digest));
    }
    if (message.type === 'approve-campaign') {
      if (!message.digest || !message.approval)
        throw new Error('Select a campaign and approval stage');
      return send('/browser-experience/research/experiment/campaigns/' + message.digest + '/approve', message.approval);
    }
    if (message.type === 'revoke-approval') {
      if (!message.approvalId) throw new Error('Select an active approval');
      return send('/browser-experience/research/experiment/approvals/' + message.approvalId + '/revoke', {});
    }
    if (message.type === 'blind-runs') return send('/browser-experience/research/blind/runs');
    if (message.type === 'blind-view') {
      if (!message.runId) throw new Error('Select a blind evaluation');
      return send('/browser-experience/research/blind/runs/' + message.runId);
    }
    if (message.type === 'blind-rate') {
      if (!message.runId || !message.outputId || !message.capability)
        throw new Error('Select an assigned output and rating capability');
      return send('/browser-experience/research/blind/runs/' + message.runId + '/ratings', {
        output_id: message.outputId,
        output_sha256: message.outputSha256,
        capability: message.capability,
        rubric: message.rubric,
        attestation: message.attestation || 'none',
        synthetic: Boolean(message.synthetic),
      });
    }
    if (message.type === 'blind-results') {
      if (!message.runId) throw new Error('Select a blind evaluation');
      return send('/browser-experience/research/blind/runs/' + message.runId + '/results');
    }
    if (message.type === 'blind-reveal') {
      if (!message.runId) throw new Error('Select a blind evaluation');
      return send('/browser-experience/research/blind/runs/' + message.runId + '/reveal', {});
    }
    if (message.type === 'blind-archive') {
      if (!message.runId) throw new Error('Select a blind evaluation');
      return send('/browser-experience/research/blind/runs/' + message.runId + '/archive', {});
    }
    if (message.type === 'revoke-relationship') {
      if (!message.consentId) throw new Error('No outbound consent selected');
      return send('/browser-experience/research/outbound/' + message.consentId + '/revoke', {});
    }
    if (message.type === 'withdraw-research') {
      if (!message.researchId) throw new Error('Select the research memory to withdraw');
      return send('/browser-experience/research/memories/' + message.researchId + '/withdraw', {});
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
