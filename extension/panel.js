import { DEFAULT_BACKEND } from './config.js';
const $ = id => document.getElementById(id);
const saved = await chrome.storage.local.get(['backend', 'token', 'autoSend', 'goalId']);
$('backend').value = saved.backend || DEFAULT_BACKEND;
$('token').value = saved.token || '';
$('auto').checked = !!saved.autoSend;
let reviewed = null;
let polling = null;
let currentDecision = null;
let reviewedSignature = null;
let noteGeneration = 0;
let currentResearchId = null;
let currentSavedResearchId = null;
let currentConnectionId = null;
let outboundConsent = null;
async function command(type, args = {}) {
  const response = await chrome.runtime.sendMessage({ type, ...args });
  if (response.error) throw new Error(response.error);
  return response.data;
}
async function action(fn) {
  try { await fn(); } catch (e) { $('status').textContent = e.message; }
}
function setFeedback(note, allowFeedback = true) {
  const enabled = allowFeedback && note?.status === 'validated';
  $('useful').disabled = $('needs-work').disabled = !enabled;
}
function clearCurrentNote(message) {
  setFeedback(null, false);
  $('save-research').disabled = true;
  $('note-heading').textContent = 'No current note';
  $('note').textContent = message;
  $('cost').textContent = '';
}
function clearOutbound() {
  outboundConsent = null;
  $('outbound').replaceChildren();
  $('relationship-feedback').replaceChildren();
}
function resetResearch() {
  currentResearchId = null;
  currentSavedResearchId = null;
  currentConnectionId = null;
  clearOutbound();
  $('research-results').replaceChildren();
  $('research-status').textContent = 'No related research memory selected.';
  $('connection').textContent = '';
  $('withdraw-research').disabled = true;
  $('connect-research').disabled = true;
  $('connection-useful').disabled = true;
  $('connection-not-useful').disabled = true;
}
function invalidateNote() {
  clearCurrentNote('Reviewed observation changed - no current note.');
  resetResearch();
  noteGeneration += 1;
  clearInterval(polling);
  polling = null;
  setFeedback(null, false);
  $('analyse').disabled = true;
  return noteGeneration;
}
function showNote(note, allowFeedback = true, historical = false) {
  $('note').replaceChildren();
  const output = note?.data?.output;
  if (output) {
    for (const [tag, text] of [['p', output.summary], ['blockquote', output.evidence_quote], ['p', 'Limits: ' + output.limitations]]) {
      const element = document.createElement(tag); element.textContent = text; $('note').append(element);
    }
  } else $('note').textContent = note ? 'Note ' + note.status : 'No note yet.';
  $('note-heading').textContent = allowFeedback
    ? 'Current note - rate this note, not the subject'
    : historical
      ? 'Previous note - historical, not a feedback target'
      : 'Previous note - not a feedback target';
  setFeedback(note, allowFeedback);
  $('save-research').disabled = !(note?.status === 'validated' && allowFeedback);
  $('cost').textContent = note ? `${note.status} · ${note.data.model} · ${note.data.usage?.total_tokens ?? 'pending'} tokens · estimated $${note.data.estimated_usd ?? '?'} · ${Math.round(note.data.latency_ms || 0)} ms` : '';
  if (historical && $('cost').textContent) $('cost').textContent = 'Previous note usage: ' + $('cost').textContent;
}
async function pollNote(generation = noteGeneration) {
  let note;
  try { note = await command('note'); }
  catch (error) { if (generation !== noteGeneration) return; throw error; }
  if (generation !== noteGeneration) return;
  showNote(note);
  if (note && note.status !== 'reserved') { clearInterval(polling); polling = null;
    $('status').textContent = note.status === 'validated' ? 'Meta note ready · review its evidence and limitations' : 'Meta note failed · failure retained in ledger'; }
}
$('connect').onclick = () => action(async () => {
  await chrome.storage.local.set({ backend: $('backend').value.replace(/\/$/, ''), token: $('token').value });
  const state = await command('connect');
  $('state').textContent = JSON.stringify({ identity: state.identity, lifecycle: state.lifecycle,
    provenance: state.provenance }, null, 2);
  $('connection-proof').textContent = 'Verified local runtime · ' + (state.provenance.source_commit?.slice(0, 7) || 'source fingerprint available');
  $('status').textContent = 'Connected · ' + state.identity.name;
  const { goals } = await command('goals');
  $('resume').replaceChildren(new Option('Choose a saved goal', ''));
  for (const goal of goals) $('resume').add(new Option(goal.data.instruction, goal.id));
  const { goalId } = await chrome.storage.local.get('goalId');
  if (goals.some(g => g.id === goalId)) {
    $('resume').value = goalId;
    $('goal').value = goals.find(g => g.id === goalId).data.instruction;
    $('instruction').textContent = $('goal').value;
  }
});
$('resume').onchange = () => action(async () => {
  invalidateNote();
  await command('stop');
  await chrome.storage.local.set({ goalId: $('resume').value });
  $('goal').value = $('resume').selectedOptions[0].textContent;
  $('instruction').textContent = $('goal').value;
  $('status').textContent = 'Goal resumed; authorise this tab again.';
});
$('save-goal').onclick = () => action(async () => {
  invalidateNote();
  await command('stop');
  const goal = await command('goal', { instruction: $('goal').value });
  $('instruction').textContent = goal.data.instruction;
  $('status').textContent = 'Goal saved locally. It survives browser and backend restarts.';
});
$('auto').onchange = () => chrome.storage.local.set({ autoSend: $('auto').checked });
$('language').onchange = () => {
  invalidateNote();
  currentDecision = null;
  $('status').textContent = 'Language changed - save the reviewed observation again';
};
$('start').onclick = () => action(async () => {
  invalidateNote();
  await command('start');
  $('status').textContent = 'Observing this page · explicit permission active for up to 30 minutes';
});
$('stop').onclick = () => action(async () => {
  invalidateNote();
  await command('stop');
  setFeedback(null, false);
  $('note-heading').textContent = 'No current note';
  $('note').textContent = 'Observation stopped and permission revoked.';
  $('cost').textContent = '';
  $('status').textContent = 'Stopped - page observation revoked';
});
$('send').onclick = () => action(async () => {
  const generation = invalidateNote();
  const language = $('language').value;
  const result = await command('send', { reviewed, language });
  if (generation !== noteGeneration) return;
  currentDecision = result.decision || null;
  $('status').textContent = 'Observation persisted by ALIVE';
  $('find-research').disabled = !result.snapshot?.id;
  if (result.decision) {
    const action = result.decision.action;
    const relevance = result.decision.goal_relevance;
    const adaptive = result.decision.adaptive_policy;
    const uncertain = action === 'uncertain';
    const probe = !!(result.decision.probe || adaptive?.probe);
    const suppressed = action === 'no_action' && result.decision.no_action_source === 'feedback_policy';
    const probeBlocked = !!(result.decision.probe_blocked || adaptive?.probe_blocked);
    setFeedback(null, false);
    $('decision-label').textContent = action === 'recall'
      ? 'Recall a note you rated useful - no new inference'
      : action === 'no_action'
        ? suppressed
          ? probeBlocked
            ? 'Recovery probe due - this excerpt is not fresh; review a new excerpt'
            : 'Automatic analysis paused by feedback - analyse anyway if this matters'
          : 'No action warranted - observation does not match your goal'
        : uncertain
          ? 'Language uncertain - choose a language or explicitly analyse'
          : probe
            ? 'Periodic re-evaluation - one fresh analysis is eligible'
            : 'Fresh analysis recommended - no useful exact evidence yet';
    $('relevance').textContent = relevance
      ? `Language: ${relevance.language} (${relevance.language_source}) - policy ${result.decision.relevance_policy || relevance.policy} - ${relevance.relevant ? 'matched' : 'no match'}${relevance.matched_terms?.length ? ' - ' + relevance.matched_terms.join(', ') : ''}. ${relevance.basis}`
      : '';
    $('policy').textContent = adaptive
      ? `Decision policy v${result.decision.policy_version} - ${adaptive.distinct_evidence} distinct rated excerpt(s) (${adaptive.useful} useful / ${adaptive.not_useful} not useful) - ${adaptive.suppressions}/${adaptive.probe_after_suppressions} distinct paused excerpt(s). ${adaptive.reason}`
      : '';
    $('decision').textContent = JSON.stringify({ ...result.decision,
      note: result.decision.note?.id || null, candidate_note: result.decision.candidate_note?.id || null }, null, 2);
    $('fact').textContent = `${result.snapshot.data.text_status} - SHA-256 ${result.snapshot.data.sha256}. Observed text; not verified factual truth.`;
    $('preference').textContent = suppressed
      ? probeBlocked
        ? 'A recovery probe is due, but this exact excerpt was already paused, rated or probed. Review a new excerpt, or use Analyse anyway as an explicit correction.'
        : adaptive?.repeated_suppression
          ? 'This exact excerpt was already paused; repetition did not advance the recovery probe counter.'
          : `Automatic analysis is paused for this goal and page. ${adaptive.suppressions}/${adaptive.probe_after_suppressions} distinct paused excerpts; a periodic re-evaluation follows after the limit. You can analyse anyway now.`
      : probe
        ? 'The pause limit was reached. This bounded re-evaluation gives the context one fresh chance without changing permissions or budgets.'
        : action === 'no_action'
          ? 'No model call was made. Revise the goal or use the explicit owner correction if this page matters.'
          : uncertain
            ? 'No model call was made. Confirming the page language or using Analyse anyway is an explicit override.'
            : result.decision.feedback_id
              ? 'Recall follows exact useful evidence. No new model call was made.'
              : 'No useful exact evidence yet. Fresh analysis is eligible.';
    $('analyse').disabled = action === 'recall';
    $('analyse').textContent = action === 'recall'
      ? 'Exact recall in use'
      : action === 'uncertain'
        ? 'Analyse anyway (language override)'
        : action === 'no_action'
          ? 'Analyse anyway (owner correction)'
          : probe
            ? 'Run periodic re-evaluation'
            : 'Send reviewed excerpt to Meta';
    if (action === 'uncertain') {
      clearCurrentNote('No model note. Choose a language or use Analyse anyway.');
      $('status').textContent = 'Language uncertain - no automatic model call';
    } else if (suppressed) {
      clearCurrentNote('No model note. Automatic analysis is paused; Analyse anyway is an explicit correction.');
      $('status').textContent = 'Analysis paused by owner feedback';
    } else if (action === 'no_action') {
      clearCurrentNote('No model note. No Meta call was made.');
      $('status').textContent = 'No action warranted - the observation was not analysed';
    } else if (result.decision.note) {
      showNote(result.decision.note, true, false); $('status').textContent = 'Recalled useful evidence - 0 new Meta calls';
    } else if (result.decision.candidate_note) {
      showNote(result.decision.candidate_note, false, true);
      $('status').textContent = probe ? 'Periodic re-evaluation is ready' : 'Fresh analysis is eligible';
    } else {
      clearCurrentNote('No note yet.');
      $('status').textContent = probe ? 'Periodic re-evaluation is ready' : 'Fresh analysis is eligible';
    }
  }
});
$('analyse').onclick = () => action(async () => {
  const generation = invalidateNote();
  $('analyse').disabled = true;
  setFeedback(null, false);
  $('note-heading').textContent = 'Analysis running';
  $('note').textContent = 'One bounded model request is running.';
  await command('analyse', {
    allow_uncertain_analysis: currentDecision?.action === 'uncertain',
    owner_correction: currentDecision?.action === 'no_action',
  });
  if (generation !== noteGeneration) return;
  $('status').textContent = 'One bounded Meta request running; Stop cancels it.';
  polling = setInterval(() => action(() => pollNote(generation)), 750);
  await pollNote(generation);
});
for (const [id, useful] of [['useful', true], ['needs-work', false]]) {
  $(id).onclick = () => action(async () => {
    const generation = noteGeneration;
    const feedback = await command('feedback', { useful });
    if (generation !== noteGeneration) return;
    const data = feedback.data || {};
    if (feedback.idempotent) {
      $('preference').textContent = 'This rating is already saved. No duplicate policy update was made.';
      $('status').textContent = 'Feedback unchanged';
      return;
    }
    if (data.duplicate_evidence) {
      $('preference').textContent = `This excerpt is already counted as one evidence unit (${data.distinct_support} distinct). No policy update was made.`;
      $('status').textContent = 'Duplicate excerpt evidence ignored';
      return;
    }
    $('preference').textContent = `${useful ? 'This note helped.' : 'This note did not help.'} Distinct evidence: ${data.distinct_support}. Policy v${data.policy_version_before ?? '?'} -> v${data.policy_version_after ?? '?'}${data.revision ? ' (revised)' : ''}.`;
    $('status').textContent = useful
      ? 'Feedback saved. This evidence supports future analysis.'
      : 'Feedback saved. Repeated unhelpful notes may pause automatic analysis; Analyse anyway remains available.';
  });
}
$('save-research').onclick = () => action(async () => {
  const saved = await command('save-research');
  currentSavedResearchId = saved.id;
  $('research-status').textContent = `Saved reviewed source for this goal: ${saved.data.title || saved.data.url} · ${saved.data.reviewed_at || ''} · SHA-256 ${saved.data.sha256.slice(0, 12)}.`;
  $('withdraw-research').disabled = false;
  $('status').textContent = 'Research memory saved locally; retrieval does not authorise sending it externally.';
});
async function previewRelationship(item) {
  const preview = await command('preview-relationship', { memoryId: item.memory_id });
  const box = $('outbound');
  box.replaceChildren();
  $('relationship-feedback').replaceChildren();
  outboundConsent = preview;
  const external = preview.external ? 'external provider' : 'local deterministic stub';
  box.append(
    outboundText('p', `Outbound payload preview — ${external}.`),
    outboundText('p', `Current source: ${preview.current_source.url} (SHA-256 ${preview.current_source.sha256.slice(0, 12)})`),
    outboundText('blockquote', preview.current_source.excerpt),
    outboundText('p', `Historical source: ${preview.historical_source.url} (SHA-256 ${preview.historical_source.sha256.slice(0, 12)})`),
    outboundText('blockquote', preview.historical_source.excerpt),
    outboundText('p', `Goal: ${preview.goal.instruction}`),
    outboundText('p', `Provider/model: ${preview.provider.id} · ${preview.provider.model}`),
    outboundText('p', `Estimated maximum: ${preview.estimated_max_tokens} tokens · ${preview.estimated_max_micro_usd} micro-USD`),
    outboundText('p', `Remaining allowance: ${preview.remaining_allowance.session_calls_remaining} session calls · ${preview.remaining_allowance.session_tokens_remaining} session tokens · ${preview.remaining_allowance.micro_usd_remaining} micro-USD`),
    outboundText('p', `Exact request SHA-256: ${preview.request_sha256}`),
    outboundText('p', preview.external
      ? 'Authorising this exact payload permits transmission to the external provider.'
      : 'No external transmission occurs for this local stub.'),
  );
  const requestDetails = document.createElement('details');
  const requestSummary = document.createElement('summary');
  requestSummary.textContent = 'Exact outgoing instructions, payload and schema';
  const requestPre = document.createElement('pre');
  requestPre.textContent = JSON.stringify(preview.request, null, 2);
  requestDetails.append(requestSummary, requestPre);
  box.append(requestDetails);
  const authorize = document.createElement('button');
  authorize.textContent = 'Authorize this exact payload';
  authorize.onclick = () => action(async () => {
    const authorized = await command('authorize-relationship', {
      consentId: preview.id,
      payloadSha256: preview.payload_sha256,
    });
    authorize.disabled = true;
    box.append(outboundText('p', `Authorised exact payload at ${authorized.data?.authorized_at || 'recorded time'}.`));
    const run = document.createElement('button');
    run.textContent = 'Run authorised analysis';
    run.onclick = () => action(async () => {
      run.disabled = true;
      const result = await command('analyse-relationship', { consentId: preview.id });
      renderRelationship(result);
    });
    box.append(run);
  });
  box.append(authorize);
}
function outboundText(tag, text) {
  const node = document.createElement(tag);
  node.textContent = text;
  return node;
}
function renderRelationship(result) {
  const connection = result.connection || (result.id ? result : null);
  const analysis = result.analysis;
  const box = $('outbound');
  if (!connection) {
    outboundConsent = null;
    box.append(outboundText('p', `Analysis ${analysis?.status || 'failed'}; no validated connection was stored.`));
    return;
  }
  currentConnectionId = connection.id;
  const data = connection.data || {};
  box.append(
    outboundText('p', `${data.relation_type} · ${data.status}. ${data.explanation}`),
    outboundText('blockquote', `Current source quote: ${data.current_quote || 'unavailable'}`),
    outboundText('blockquote', `Historical source quote: ${data.historical_quote || 'unavailable'}`),
    outboundText('p', `Limitations: ${data.limitations || 'none recorded'}`),
    outboundText('p', `Provider ${data.provider?.id || 'unknown'} · model ${data.provider?.model || 'unknown'} · ${analysis?.data?.usage?.total_tokens ?? 'unknown'} tokens`),
    outboundText('p', 'Hypothesis, not independently verified truth.'),
  );
  renderRelationshipRubric(connection.id);
}
function renderRelationshipRubric(connectionId) {
  const target = $('relationship-feedback');
  target.replaceChildren();
  const rubric = {};
  const rows = [
    ['Factually supported', 'factually_supported'],
    ['Relevant to goal', 'relevant_to_goal'],
    ['Revealed something new', 'revealed_new'],
    ['Would investigate or act', 'would_act'],
    ['Misleading or wrong', 'misleading'],
  ];
  for (const [label, field] of rows) {
    const row = document.createElement('p');
    row.textContent = label + ': ';
    for (const value of ['yes', 'no', 'uncertain']) {
      const button = document.createElement('button');
      button.textContent = value;
      button.onclick = () => action(async () => {
        rubric[field] = value;
        await command('relationship-feedback', { connectionId, rubric: { ...rubric } });
        $('research-status').textContent = `Relationship assessment saved (${label}: ${value}).`;
      });
      row.append(button);
    }
    target.append(row);
  }
}
$('find-research').onclick = () => action(async () => {
  const result = await command('find-research');
  $('research-results').replaceChildren();
  clearOutbound();
  currentResearchId = null;
  $('connect-research').disabled = true;
  $('connection').textContent = '';
  $('connection-useful').disabled = true;
  $('connection-not-useful').disabled = true;
  if (!result.results?.length) {
    $('research-status').textContent = `No related authorised research memory found (${result.mode || 'text'}). Abstained; no connection invented.`;
    return;
  }
  $('research-status').textContent = `${result.results.length} related historical source(s) via ${result.mode}. Historical evidence is distinct from the current page.`;
  for (const item of result.results) {
    const block = document.createElement('div');
    const heading = document.createElement('p');
    heading.textContent = `Previously researched: ${item.source_title || item.source_url}`;
    const source = document.createElement('p');
    source.textContent = `${item.source_url} · reviewed ${item.reviewed_at || 'unknown'} · usefulness ${item.owner_useful === true ? 'useful' : item.owner_useful === false ? 'not useful' : 'unrated'}`;
    const quote = document.createElement('blockquote');
    quote.textContent = item.excerpt;
    const button = document.createElement('button');
    button.textContent = 'Explain connection to this page';
    button.onclick = () => action(async () => {
      currentResearchId = item.memory_id;
      const connection = await command('connection', { memoryId: item.memory_id });
      currentConnectionId = connection.id;
      const data = connection.data || {};
      const modelQuote = data.model_evidence_quote
        ? `\nHistorical model quotation (not a source span): ${data.model_evidence_quote}`
        : '';
      $('connection').textContent = `${data.status} · ${data.relation_type}. ${data.explanation}\nHistorical source quote: ${data.historical_quote || 'unavailable'}\nCurrent source quote: ${data.current_quote || 'unavailable'}${modelQuote}`;
      $('connection-useful').disabled = data.status !== 'candidate';
      $('connection-not-useful').disabled = data.status !== 'candidate';
      $('status').textContent = connection.abstained
        ? 'Connection abstained: no inspectable shared source evidence.'
        : 'Connection candidate created; both sources remain distinct.';
    });
    block.append(heading, source, quote, button);
    const outbound = document.createElement('button');
    outbound.textContent = 'Preview outbound analysis';
    outbound.onclick = () => action(async () => {
      currentResearchId = item.memory_id;
      await previewRelationship(item);
    });
    block.append(outbound);
    const withdraw = document.createElement('button');
    withdraw.textContent = 'Withdraw this memory';
    withdraw.onclick = () => action(async () => {
      await command('withdraw-research', { researchId: item.memory_id });
      if (currentSavedResearchId === item.memory_id) {
        currentSavedResearchId = null;
        $('withdraw-research').disabled = true;
      }
      currentConnectionId = null;
      $('connection-useful').disabled = true;
      $('connection-not-useful').disabled = true;
      clearOutbound();
      $('research-status').textContent = `Withdrew displayed memory ${item.memory_id}; it will not be retrieved.`;
      $('research-results').replaceChildren();
      $('connection').textContent = '';
    });
    block.append(withdraw);
    $('research-results').append(block);
  }
});
$('withdraw-research').onclick = () => action(async () => {
  if (!currentSavedResearchId) throw new Error('Save a research memory first');
  await command('withdraw-research', { researchId: currentSavedResearchId });
  currentSavedResearchId = null;
  $('withdraw-research').disabled = true;
  $('research-results').replaceChildren();
  $('connection').textContent = '';
  $('research-status').textContent = 'Research memory withdrawn; it will not be retrieved or reindexed.';
});
for (const [id, useful] of [['connection-useful', true], ['connection-not-useful', false]]) {
  $(id).onclick = () => action(async () => {
    await command('connection-feedback', { useful });
    $('connection').textContent = `Connection feedback saved: ${useful ? 'useful' : 'not useful'}.`;
    $('connection-useful').disabled = $('connection-not-useful').disabled = true;
  });
}
async function preview() {
  const { latest, selected } = await chrome.storage.session.get(['latest', 'selected']);
  reviewed = latest?.payload || null;
  $('source').textContent = reviewed ? 'Reviewed page: ' + reviewed.url : 'No page authorised.';
  const signature = reviewed ? JSON.stringify(reviewed) : null;
  if (signature !== reviewedSignature) {
    reviewedSignature = signature;
    currentDecision = null;
    invalidateNote();
  }
  $('preview').textContent = reviewed ? JSON.stringify(reviewed, null, 2) : 'No observation permission. Authorise this page to preview.';
  $('send').disabled = !reviewed;
  if (!reviewed) { $('analyse').disabled = true; clearCurrentNote('No observation permission. Authorise this page to preview.'); return; }
  if (selected && selected.snapshot.data.text !== reviewed.text) $('analyse').disabled = true;
}
chrome.storage.onChanged.addListener(preview);
await preview();
$('connect').disabled = $('token').disabled = $('backend').disabled = false;

