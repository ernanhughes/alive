const assert = require('node:assert/strict');
const { test } = require('node:test');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { JSDOM } = require('../dashboard/node_modules/jsdom');
const source = readFileSync(join(__dirname, '../extension/live-companion.js'), 'utf8')
  .replace(/^import .*?;\r?\n/, 'const DEFAULT_BACKEND="http://127.0.0.1:8000"; const DEFAULT_BACKENDS=[DEFAULT_BACKEND];\n');
const html = readFileSync(join(__dirname, '../extension/panel.html'), 'utf8');
const AsyncFunction = Object.getPrototypeOf(async () => {}).constructor;
const finding = { id: 'finding', status: 'candidate', data: {
  provider: {id:'local_fixture_claim'}, historical_memory_id: 'memory', historical_quote: '<img src=x onerror=alert(1)>',
  current_quote: 'Deprecated since 3.12.', supersession_basis_quote: 'Deprecated since 3.12.',
  historical_quote_retained_in_current: true, relation_type: 'explicit_supersession',
  explanation: 'Standing changes; behavior is retained.', limitations: 'Fixture interpretation.',
} };
async function panel(initial = {}, session = {}) {
  const d = new JSDOM(html).window.document;
  let current = { goal: { id: 'g', data: { instruction: 'Research UTC' } }, related: [], findings: [], analyses: [], ...initial };
  let goalId = 'g', onChanged, override;
  const calls = [];
  const chrome = { storage: {
    local: { get: async () => ({ backend: 'http://127.0.0.1:8000', goalId }) },
    session: { get: async () => session }, onChanged: { addListener(fn) { onChanged = fn; } },
  }, runtime: { sendMessage: async message => {
    calls.push(message);
    if (override) { const response = override(message); if (response !== undefined) return response; }
    if (message.type === 'live-context') return { data: current };
    if (message.type === 'live-preview') return { data: {
      id: 'consent', data: { expires_at: 'later' }, preview: {
        goal_id: 'g', current_url: 'http://source/X', current_sha256: 'sha-X',
        historical_memory_id: 'memory', reliance: { quote: 'Anchored source.' },
      },
      request: { instructions: 'Exact claim instructions', input: { anchor: 'Anchored source.' }, schema: { title: 'ClaimComparisonOutput' } },
      provider: { id: 'local_fixture_claim' }, payload_sha256: 'payload-hash', request_sha256: 'request-hash', estimated_max_micro_usd: 0,
    } };
    if (message.type === 'withdraw-research') { current = { ...current, related: [], findings: [] }; return { data: { status: 'withdrawn' } }; }
    if (message.type === 'analyse-relationship') return { data: { analysis: { status: 'validated', data: {
      goal_id: 'g', current_url: 'http://source/X', current_sha256: 'sha-X', historical_memory_id: 'memory',
      validation: { relationship: 'insufficient_evidence' },
    } }, connection: null } };
    return { data: {} };
  } } };
  const api = await new AsyncFunction('chrome', 'document', source + '\nreturn {refresh,showPreview};')(chrome, d);
  const click = async label => {
    const b = Array.from(d.querySelectorAll('#live-content button')).find(n => n.textContent === label);
    assert.ok(b, 'missing button: ' + label); await b.onclick();
  };
  return { d, api, calls, click, change: () => onChanged(), setGoal: id => { goalId = id; },
    setContext: value => { current = value; }, intercept: fn => { override = fn; } };
}
test('live card separates unchanged text and changed standing, renders untrusted quotes as text', async () => {
  const p = await panel({ findings: [finding] });
  const body = p.d.querySelector('#live-content');
  assert.match(body.textContent, /What remained unchanged/);
  assert.match(body.textContent, /What changed/);
  assert.match(body.textContent, /Why ALIVE flagged this/);
  assert.equal(body.querySelectorAll('img,script').length, 0);
  assert.match(body.textContent, /<img src=x/);
});
test('live preview discloses exact request, hashes, local provider and zero maximum spend', async () => {
  const p = await panel(); await p.api.showPreview('memory');
  const body = p.d.querySelector('#live-content').textContent;
  for (const value of ['Exact claim instructions','ClaimComparisonOutput','payload-hash','request-hash','maximum inference spend $0']) assert.ok(body.includes(value));
  assert.equal(p.calls.some(x => x.type === 'analyse-relationship'), false);
  await p.click('Cancel check');
  assert.equal(p.calls.some(x => x.type === 'live-cancel'), true);
  assert.equal(p.calls.some(x => x.type === 'authorize-relationship'), false);
});
test('live authorised abstention shows recorded outcome rather than an alert', async () => {
  const p = await panel(); await p.api.showPreview('memory'); await p.click('Authorise exact comparison');
  assert.equal(p.d.querySelector('#live-state').textContent, 'Evidence checked · No validated change detected');
  assert.equal(p.d.querySelectorAll('[data-finding-id]').length, 0);
  assert.deepEqual(p.calls.filter(x => ['authorize-relationship','analyse-relationship'].includes(x.type)).map(x => x.type), ['authorize-relationship','analyse-relationship']);
});
test('immediate abstention requires the exact recorded source pair', async () => {
  const exact = { goal_id: 'g', current_url: 'http://source/X', current_sha256: 'sha-X',
    historical_memory_id: 'memory', validation: { relationship: 'insufficient_evidence' } };
  for (const changed of [
    {goal_id: 'other'}, {current_url: 'other'}, {current_sha256: 'other'}, {historical_memory_id: 'other'},
    {goal_id: undefined}, {current_url: undefined}, {current_sha256: undefined}, {historical_memory_id: undefined},
  ]) {
    const p = await panel();
    p.intercept(message => message.type === 'analyse-relationship'
      ? { data: { analysis: { status: 'validated', data: {...exact, ...changed} }, connection: null } }
      : undefined);
    await p.api.showPreview('memory'); await p.click('Authorise exact comparison');
    assert.equal(p.d.querySelector('#live-state').textContent, 'Check did not complete. No finding was stored.');
    assert.equal(p.d.querySelectorAll('[data-finding-id]').length, 0);
  }
});
test('validated non-abstention without a stored connection is not displayed as an abstention', async () => {
  const p = await panel();
  p.intercept(message => message.type === 'analyse-relationship'
    ? { data: { analysis: { status: 'validated', data: {
      goal_id: 'g', current_url: 'http://source/X', current_sha256: 'sha-X', historical_memory_id: 'memory',
      validation: { relationship: 'explicit_supersession' },
    } }, connection: null } }
    : undefined);
  await p.api.showPreview('memory'); await p.click('Authorise exact comparison');
  assert.equal(p.d.querySelector('#live-state').textContent, 'Check did not complete. No finding was stored.');
});
test('live review enables related-research lookup for the notebook journey', async () => {
  const p = await panel({}, { latest: { payload: {
    url: 'http://127.0.0.1:1313/chapters/alive-12-status/', text: 'Reviewed chapter text.',
  } } });
  p.d.querySelector('#find-research').disabled = true;
  p.d.querySelector('#live-review').click();
  for (let i = 0; i < 50 && p.d.querySelector('#find-research').disabled; i++)
    await new Promise(resolve => setTimeout(resolve, 10));
  assert.equal(p.d.querySelector('#find-research').disabled, false);
});
test('dismissal keeps source evidence and records interpretation feedback only', async () => {
  const p = await panel({ findings: [finding] }); await p.click('Dismiss interpretation');
  assert.ok(p.calls.some(x => x.type === 'live-feedback' && x.connectionId === 'finding' && x.useful === false));
  assert.equal(p.calls.some(x => x.type === 'withdraw-research'), false);
});
test('withdrawal clears live and legacy cards, and a stale refresh cannot restore them', async () => {
  const p = await panel({ findings: [finding] });
  p.d.querySelector('#evidence-cards').textContent = 'OLD EVIDENCE';
  let resolve;
  p.intercept(message => message.type === 'live-context' ? new Promise(r => { resolve = r; }) : undefined);
  const pending = p.api.refresh();
  await p.click('Withdraw saved source');
  p.intercept(null);
  await p.click('Confirm withdrawal');
  resolve({ data: { findings: [finding], related: [] } }); await pending;
  assert.equal(p.d.querySelectorAll('[data-finding-id]').length, 0);
  assert.equal(p.d.querySelector('#evidence-cards').textContent, '');
  assert.match(p.d.querySelector('#live-state').textContent, /Evidence retired/);
});
test('investigation switch refuses an old preview before any authorization or dispatch', async () => {
  const p = await panel(); await p.api.showPreview('memory'); p.setGoal('other');
  await p.click('Authorise exact comparison');
  assert.match(p.d.querySelector('#live-error').textContent, /Investigation changed/);
  assert.equal(p.calls.some(x => x.type === 'authorize-relationship'), false);
  assert.equal(p.calls.some(x => x.type === 'analyse-relationship'), false);
});

const relatedMemory = { memory_id: 'memory', reliance_anchor: {quote: 'Saved passage.'}, matched_terms: ['UTC'] };
function recordedPair(overrides = {}) {
  return { status: 'validated', data: { goal_id: 'g', current_sha256: 'sha-X', current_url: 'http://source/X',
    historical_memory_id: 'memory', validation: {relationship: 'insufficient_evidence'}, ...overrides } };
}
function pairContext(analyses, overrides = {}) {
  return {goal: {id:'g'}, current: {id:'recapture-X', data:{title:'X',url:'http://source/X',sha256:'sha-X'}},
    related:[relatedMemory], findings:[], analyses, ...overrides};
}
test('recorded abstention must match source hash, URL, saved memory and investigation', async () => {
  for (const changed of [{current_sha256:'other'}, {current_url:'other'}, {historical_memory_id:'other'}, {goal_id:'other'}]) {
    const p = await panel(pairContext([recordedPair(changed)]));
    assert.equal(p.d.querySelector('#live-state').textContent, 'Relevant saved evidence found. No comparison has been authorised.');
  }
});
test('matching recorded abstention survives re-review with a different snapshot id', async () => {
  const p = await panel(pairContext([recordedPair({current_snapshot_id:'original-X'})]));
  assert.equal(p.d.querySelector('#live-state').textContent, 'Evidence checked · No validated change detected');
});
test('dismissed validated candidate never inherits an older abstention', async () => {
  const analyses = [recordedPair(), recordedPair({current_sha256:'other'}),
    recordedPair({validation:{relationship:'explicit_supersession'}})];
  const p = await panel(pairContext(analyses, {findings:[finding]}));
  await p.click('Dismiss interpretation');
  p.setContext(pairContext(analyses)); await p.api.refresh();
  assert.equal(p.d.querySelector('#live-state').textContent, 'Interpretation dismissed. The saved source remains available.');
});
test('unrelated abstention without a displayed memory leaves the quiet state', async () => {
  const p = await panel(pairContext([recordedPair()], {related:[]}));
  assert.equal(p.d.querySelector('#live-state').textContent, 'Nothing significant to report.');
});
