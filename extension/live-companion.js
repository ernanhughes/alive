import { DEFAULT_BACKEND, DEFAULT_BACKENDS } from './config.js';
const el = id => document.getElementById(id);
const content = el('live-content');
let version = 0, busy = false, context = null;
async function call(type, args = {}) {
  const response = await chrome.runtime.sendMessage({ type, ...args });
  if (response.error) throw new Error(response.error);
  return response.data;
}
function text(tag, value) {
  const node = document.createElement(tag);
  node.textContent = String(value ?? '');
  return node;
}
function state(message) { el('live-state').textContent = message; }
function button(label, task) {
  const node = text('button', label);
  node.onclick = () => run(task);
  return node;
}
async function run(task) {
  if (busy) return;
  busy = true; version++;
  el('live-companion').setAttribute('aria-busy', 'true');
  el('live-error').textContent = '';
  try { await task(); }
  catch (error) {
    content.replaceChildren();
    state('Research action could not complete.');
    el('live-error').textContent = error.message;
  } finally { busy = false; el('live-companion').setAttribute('aria-busy', 'false'); }
}
function technical(label, data) {
  const detail = document.createElement('details');
  detail.append(text('summary', label), text('pre', JSON.stringify(data, null, 2)));
  return detail;
}
function clearLegacyFindings() {
  for (const id of ['evidence-cards', 'connection', 'outbound', 'relationship-feedback', 'research-results']) {
    document.getElementById(id)?.replaceChildren();
  }
}
async function assertGoal(goalId) {
  const saved = await chrome.storage.local.get('goalId');
  if (saved.goalId !== goalId) throw new Error('Investigation changed. Review the comparison again.');
}
async function withdraw(memoryId) {
  content.replaceChildren(text('p', 'Withdraw this saved source and retire its dependent findings?'));
  content.append(button('Confirm withdrawal', async () => {
    version++;
    content.replaceChildren();
    clearLegacyFindings();
    await call('withdraw-research', { researchId: memoryId });
    state('Evidence retired. Dependent findings are no longer active.');
    const current = await call('live-context');
    context = current;
    renderContext(current, true);
  }), button('Cancel withdrawal', async () => { renderContext(context); }));
}
function renderFinding(finding) {
  const data = finding.data;
  const card = document.createElement('article');
  card.dataset.findingId = finding.id;
  card.append(text('h3', 'New evidence worth reviewing'));
  card.append(text('h4', 'What remained unchanged'), text('p', data.historical_quote_retained_in_current
    ? 'The selected sentence still appears verbatim in the newer source.'
    : 'This check did not establish unchanged source text.'), text('blockquote', data.historical_quote));
  card.append(text('h4', 'What changed'), text('p', data.relation_type === 'explicit_supersession'
    ? 'The newer documentation changes this method’s recommended standing. It does not make the retained behavior description false.'
    : 'The sources suggest a change to review in the selected claim.'), text('blockquote', data.supersession_basis_quote || data.current_quote));
  card.append(text('h4', 'Why ALIVE flagged this'), text('p', data.explanation),
    text('p', 'Source interpretation, not an independent factual assessment.'), text('p', data.limitations),
    text('p', data.provider?.id === 'local_fixture_claim'
      ? 'Provider: deterministic local fixture. No external model was called.'
      : 'Provider: ' + (data.provider?.id || 'not recorded') + '. Review its recorded consent and provenance.'));
  card.append(technical('Review evidence', {
    historical_source: data.historical_source_identity, current_source: data.current_source_identity,
    historical_url: data.historical_url, current_url: data.current_url,
    historical_sha256: data.historical_sha256, current_sha256: data.current_sha256,
    reliance: data.reliance, validation: data.validation,
    payload_sha256: data.payload_sha256, request_sha256: data.request_sha256,
  }));
  card.append(button('Dismiss interpretation', async () => {
    await call('live-feedback', { connectionId: finding.id, useful: false });
    state('Interpretation dismissed. The saved source remains available.');
    content.replaceChildren();
  }), button('Keep for review', async () => {
    await call('live-feedback', { connectionId: finding.id, useful: true });
    state('Kept for review. This is still an interpretation.');
  }), button('Withdraw saved source', async () => withdraw(data.historical_memory_id)));
  return card;
}
function renderContext(value, retired = false) {
  content.replaceChildren();
  el('live-investigation').textContent = value.goal?.data?.instruction || 'Choose an investigation above.';
  if (!retired) state('Nothing significant to report.');
  if (value.current) content.append(text('p', 'Reviewed source: ' + value.current.data.title),
    text('p', 'Capture format ' + (value.current.data.capture_format_version || 1)),
    technical('Source provenance', value.current.data.source_identity || { status: 'Unverified source identity' }));
  if (value.memory?.data?.reliance_anchor?.quote) {
    content.append(text('h3', 'Saved reliance passage'), text('blockquote', value.memory.data.reliance_anchor.quote),
      text('p', 'Anchor revision ' + value.memory.data.reliance_anchor.revision),
      button('Withdraw saved source', async () => withdraw(value.memory.id)));
  }
  for (const finding of value.findings || []) content.append(renderFinding(finding));
  if (value.findings?.length && !retired) state('New evidence worth reviewing.');
  for (const memory of value.related || []) {
    content.append(text('h3', 'ALIVE remembers something related to this page.'),
      text('blockquote', memory.reliance_anchor.quote), text('p', memory.source_title || memory.source_url),
      text('p', 'Local retrieval matched: ' + memory.matched_terms.join(', ') + '. This is a retrieval suggestion, not a finding.'),
      button('Check against new evidence', async () => showPreview(memory.memory_id)));
    if (!value.findings?.length && !retired) state('Relevant saved evidence found. No comparison has been authorised.');
  }
  const displayedMemories = new Set((value.related || []).map(memory => memory.memory_id));
  if (value.memory?.data?.reliance_anchor?.quote) displayedMemories.add(value.memory.id);
  const matching = (value.analyses || []).filter(row => row.status === 'validated'
    && value.goal?.id && row.data.goal_id === value.goal.id
    && value.current?.data?.sha256 && row.data.current_sha256 === value.current.data.sha256
    && row.data.current_url === value.current.data.url
    && displayedMemories.has(row.data.historical_memory_id));
  const candidateMemories = new Set(matching.filter(row => row.data.validation?.relationship
    && row.data.validation.relationship !== 'insufficient_evidence').map(row => row.data.historical_memory_id));
  const latest = [...matching].reverse().find(row => row.data.validation?.relationship === 'insufficient_evidence'
    && !candidateMemories.has(row.data.historical_memory_id));
  if (candidateMemories.size && !value.findings?.length && !retired) {
    state('Interpretation dismissed. The saved source remains available.');
  }
  if (latest && !candidateMemories.size && !value.findings?.length && !retired) {
    state('Evidence checked · No validated change detected');
    content.append(text('p', 'Newer publication alone does not establish that the earlier claim was superseded.'),
      technical('Recorded check and limitations', latest));
  }
}
async function refresh() {
  if (busy) return;
  const currentVersion = ++version;
  try {
    const value = await call('live-context');
    if (currentVersion !== version) return;
    context = value;
    renderContext(value);
  } catch (error) {
    if (currentVersion !== version) return;
    content.replaceChildren();
    state('Connect to the local runtime to inspect saved evidence.');
  }
}
async function showPreview(memoryId) {
  const preview = await call('live-preview', { memoryId });
  content.replaceChildren();
  state('Check awaiting authorisation. Nothing has been dispatched.');
  content.append(text('h3', 'Review this exact comparison'),
    text('p', 'Deterministic local demonstration · maximum inference spend $0.'),
    text('blockquote', preview.preview.reliance.quote),
    technical('Exact instructions, input and output schema', preview.request),
    technical('Source identities, hashes, reservation and consent', {
      payload_sha256: preview.payload_sha256, request_sha256: preview.request_sha256,
      provider: preview.provider, expires_at: preview.data.expires_at,
      maximum_micro_usd: preview.estimated_max_micro_usd, reservation: preview.single_call_reservation,
    }), button('Authorise exact comparison', async () => {
      await assertGoal(preview.preview.goal_id);
      await call('authorize-relationship', { consentId: preview.id, payloadSha256: preview.payload_sha256 });
      content.replaceChildren();
      state('Comparison requested · waiting for the recorded result.');
      const result = await call('analyse-relationship', { consentId: preview.id });
      await assertGoal(preview.preview.goal_id);
      const exact = preview.preview;
      const checked = result.analysis;
      const bound = checked?.status === 'validated'
        && checked.data?.validation?.relationship === 'insufficient_evidence'
        && exact.goal_id && checked.data.goal_id === exact.goal_id
        && exact.current_sha256 && checked.data.current_sha256 === exact.current_sha256
        && exact.current_url && checked.data.current_url === exact.current_url
        && exact.historical_memory_id
        && checked.data.historical_memory_id === exact.historical_memory_id;
      if (result.connection || result.cached) {
        content.append(renderFinding(result.connection || result));
        state('New evidence worth reviewing.');
      } else if (bound) {
        state('Evidence checked · No validated change detected');
        content.append(text('p', 'Newer publication alone does not establish that the earlier claim was superseded.'),
          technical('Recorded check and limitations', checked));
      } else {
        state('Check did not complete. No finding was stored.');
        content.append(technical('Recorded outcome', result.analysis));
      }
    }), button('Cancel check', async () => {
      await call('live-cancel', { consentId: preview.id });
      content.replaceChildren();
      state('Check cancelled before dispatch.');
    }));
}
el('live-authorise').onclick = () => run(async () => {
  const { goalId } = await chrome.storage.local.get('goalId');
  await call('start');
  content.replaceChildren();
  state('Page authorised · capturing the source for local review.');
  let latest;
  for (let attempt = 0; attempt < 60; attempt++) {
    const captured = await chrome.storage.session.get(['latest', 'observedUrl']);
    if (captured.latest?.payload.url === captured.observedUrl && captured.latest?.payload.text) {
      latest = captured.latest; break;
    }
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  if (!latest) throw new Error('Capture is not available yet. Review the captured source when ready.');
  await assertGoal(goalId);
  await call('send', { reviewed: latest.payload });
  context = await call('live-context');
  renderContext(context);
});
el('live-review').onclick = () => run(async () => {
  const { latest } = await chrome.storage.session.get('latest');
  if (!latest?.payload) throw new Error('Authorise the current page and wait for its capture first.');
  await call('send', { reviewed: latest.payload });
  context = await call('live-context');
  renderContext(context);
});
el('live-remember').onclick = () => run(async () => {
  const proposal = await call('live-selection');
  content.replaceChildren(text('h3', 'Remember this passage'), text('blockquote', proposal.quote),
    text('p', proposal.reviewed.title + ' · ' + proposal.reviewed.url),
    text('p', 'Capture v2 · ' + (proposal.previous_anchor ? 'Revise existing anchor' : 'Create a reliance anchor')),
    text('p', 'Investigation: ' + (context?.goal?.data?.instruction || proposal.goal_id)),
    technical('Selection provenance and existing anchor', proposal));
  content.append(button('Confirm passage', async () => {
    const memory = await call('live-remember', { proposal });
    state('Passage remembered · anchor revision ' + memory.data.reliance_anchor.revision);
    content.replaceChildren(text('blockquote', memory.data.reliance_anchor.quote),
      button('Withdraw saved source', async () => withdraw(memory.id)));
  }), button('Cancel selection', async () => { renderContext(context); }));
});
el('live-refresh').onclick = refresh;
chrome.storage.onChanged.addListener(() => { if (!busy) void refresh(); });
const saved = await chrome.storage.local.get('backend');
for (const [id, name] of [['live-historical', 'python-3.11.html'], ['live-newer', 'python-3.12.html'], ['live-abstention', 'synthetic-no-change.html']]) {
  el(id).href = (DEFAULT_BACKENDS.includes(saved.backend) ? saved.backend : DEFAULT_BACKEND) + '/demo-live-01/' + name;
}
await refresh();
