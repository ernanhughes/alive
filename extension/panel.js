const $ = id => document.getElementById(id);
const saved = await chrome.storage.local.get(['backend', 'token', 'autoSend', 'goalId']);
$('backend').value = saved.backend || 'http://127.0.0.1:8000';
$('token').value = saved.token || '';
$('auto').checked = !!saved.autoSend;
let reviewed = null;
let polling = null;
async function command(type, args = {}) {
  const response = await chrome.runtime.sendMessage({ type, ...args });
  if (response.error) throw new Error(response.error);
  return response.data;
}
async function action(fn) {
  try { await fn(); } catch (e) { $('status').textContent = e.message; }
}
function showNote(note) {
  $('note').replaceChildren();
  const output = note?.data?.output;
  if (output) {
    for (const [tag, text] of [['p', output.summary], ['blockquote', output.evidence_quote], ['p', 'Limits: ' + output.limitations]]) {
      const element = document.createElement(tag); element.textContent = text; $('note').append(element);
    }
  } else $('note').textContent = note ? 'Note ' + note.status : 'No note yet.';
  $('useful').disabled = $('needs-work').disabled = note?.status !== 'validated';
  $('cost').textContent = note ? `${note.status} · ${note.data.model} · ${note.data.usage?.total_tokens ?? 'pending'} tokens · estimated $${note.data.estimated_usd ?? '?'} · ${Math.round(note.data.latency_ms || 0)} ms` : '';
}
async function pollNote() {
  const note = await command('note');
  showNote(note);
  if (note && note.status !== 'reserved') { clearInterval(polling); polling = null;
    $('status').textContent = note.status === 'validated' ? 'Meta note ready · review its evidence and limitations' : 'Meta note failed · failure retained in ledger'; }
}
$('connect').onclick = () => action(async () => {
  await chrome.storage.local.set({ backend: $('backend').value.replace(/\/$/, ''), token: $('token').value });
  const state = await command('connect');
  $('state').textContent = JSON.stringify({ identity: state.identity, lifecycle: state.lifecycle }, null, 2);
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
  await command('stop');
  await chrome.storage.local.set({ goalId: $('resume').value });
  $('goal').value = $('resume').selectedOptions[0].textContent;
  $('instruction').textContent = $('goal').value;
  $('status').textContent = 'Goal resumed; authorise this tab again.';
});
$('save-goal').onclick = () => action(async () => {
  await command('stop');
  const goal = await command('goal', { instruction: $('goal').value });
  $('instruction').textContent = goal.data.instruction;
  $('status').textContent = 'Goal saved locally. It survives browser and backend restarts.';
});
$('auto').onchange = () => chrome.storage.local.set({ autoSend: $('auto').checked });
$('start').onclick = () => action(async () => {
  await command('start');
  $('status').textContent = 'Observing this page · explicit permission active for up to 30 minutes';
});
$('stop').onclick = () => action(async () => {
  clearInterval(polling);
  await command('stop');
  $('status').textContent = 'Stopped · page observation revoked';
});
$('send').onclick = () => action(async () => {
  const result = await command('send', { reviewed });
  $('status').textContent = 'Observation persisted by ALIVE';
  if (result.decision) {
    $('decision-label').textContent = result.decision.action === 'recall'
      ? 'Recall a note you found useful · no new inference'
      : 'Fresh analysis recommended · no useful matching experience yet';
    $('decision').textContent = JSON.stringify({ ...result.decision,
      note: result.decision.note?.id || null, candidate_note: result.decision.candidate_note?.id || null }, null, 2);
    $('fact').textContent = `${result.snapshot.data.text_status} · SHA-256 ${result.snapshot.data.sha256}. Observed text; not verified factual truth.`;
    $('preference').textContent = result.decision.feedback_id
      ? 'Recall follows your earlier useful rating. Feedback ' + result.decision.feedback_id + '.'
      : 'No positive matching rating. A saved note alone does not enable reuse.';
    $('analyse').disabled = result.decision.action === 'recall';
    if (result.decision.note) { showNote(result.decision.note); $('status').textContent = 'Recalled useful experience · 0 new Meta calls'; }
    else showNote(result.decision.candidate_note);
  }
});
$('analyse').onclick = () => action(async () => {
  $('analyse').disabled = true;
  await command('analyse');
  $('status').textContent = 'One bounded Meta request running; Stop cancels it.';
  polling = setInterval(() => action(pollNote), 750);
  await pollNote();
});
for (const [id, useful] of [['useful', true], ['needs-work', false]]) {
  $(id).onclick = () => action(async () => {
    const feedback = await command('feedback', { useful });
    $('preference').textContent = `${useful ? 'Reuse recommended' : 'Fresh analysis recommended'} for this exact goal, URL and excerpt. Feedback ${feedback.id}.`;
    $('status').textContent = 'Feedback saved. Future choices use this experience.';
  });
}
async function preview() {
  const { latest, selected } = await chrome.storage.session.get(['latest', 'selected']);
  reviewed = latest?.payload || null;
  $('preview').textContent = reviewed ? JSON.stringify(reviewed, null, 2) : 'No observation permission. Authorise this page to preview.';
  $('send').disabled = !reviewed;
  if (!reviewed) { $('analyse').disabled = true; return; }
  if (selected && selected.snapshot.data.text !== reviewed.text) $('analyse').disabled = true;
}
chrome.storage.onChanged.addListener(preview);
await preview();
$('connect').disabled = $('token').disabled = $('backend').disabled = false;
