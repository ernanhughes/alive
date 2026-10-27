const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { test } = require('node:test');
const { join } = require('node:path');
const source = readFileSync(join(__dirname, '../extension/background.js'), 'utf8')
  .replace(/^import .*?;\r?\n/, `const DEFAULT_BACKEND='http://127.0.0.1:61001';
const DEFAULT_BACKENDS=[DEFAULT_BACKEND]; const AUTHORISED_PAGES=[]; const isLocalDemo=()=>false;\n`);

function worker(backend, identity = { protocol_version: 1, runtime_sha256: 'fingerprint' }) {
  let listener;
  const session = {};
  const calls = [];
  const chrome = {
    sidePanel: { setPanelBehavior() {} },
    runtime: { id: 'test', getURL: p => 'chrome-extension://test/' + p,
      onMessage: { addListener: callback => { listener = callback; } } },
    storage: { local: { get: async () => ({ backend, token: 'local-test-token' }) },
      session: { set: async data => Object.assign(session, data) } },
    tabs: { onRemoved: { addListener() {} }, onUpdated: { addListener() {} } },
  };
  new Function('chrome', 'fetch', source)(chrome, async url => {
    calls.push(url);
    return { ok: true, json: async () => url.endsWith('/provenance') ? identity : { identity: { name: 'Fixture' } } };
  });
  return { calls, session,
    connect: () => new Promise(resolve => listener({ type: 'connect' },
      { id: 'test', url: 'chrome-extension://test/panel.html' }, resolve)),
    command: message => new Promise(resolve => listener(message,
      { id: 'test', url: 'chrome-extension://test/panel.html' }, resolve)) };
}

test('isolated extension rejects stale port 8000 before any fetch', async () => {
  const w = worker('http://127.0.0.1:8000');
  const result = await w.connect();
  assert.match(result.error, /not allowed/);
  assert.deepEqual(w.calls, []);
});

test('connect records the authenticated backend identity before declaring connection', async () => {
  const w = worker('http://127.0.0.1:61001');
  const result = await w.connect();
  assert.equal(result.data.identity.name, 'Fixture');
  assert.equal(w.session.backendProvenance.runtime_sha256, 'fingerprint');
  assert.deepEqual(w.calls, ['http://127.0.0.1:61001/api/v1/provenance', 'http://127.0.0.1:61001/api/v1/alive']);
});

test('connect fails closed on an incompatible backend identity', async () => {
  const w = worker('http://127.0.0.1:61001', { protocol_version: 2 });
  const result = await w.connect();
  assert.match(result.error, /identity is unavailable/);
  assert.equal(w.calls.length, 1);
  assert.equal(w.session.backendProvenance, undefined);
});

test('withdraw sends the displayed research id, not the most recently saved id', async () => {
  const w = worker('http://127.0.0.1:61001');
  w.session.researchId = 'research-B-last-saved';
  const result = await w.command({ type: 'withdraw-research', researchId: 'research-A-displayed' });
  assert.equal(result.data.identity.name, 'Fixture');
  assert.deepEqual(w.calls, [
    'http://127.0.0.1:61001/api/v1/browser-experience/research/memories/' +
      'research-A-displayed/withdraw',
  ]);
  assert.ok(!w.calls.some(url => url.includes('research-B-last-saved')));
});

test('withdraw without an explicit research id fails before any fetch', async () => {
  const w = worker('http://127.0.0.1:61001');
  w.session.researchId = 'research-B-last-saved';
  const result = await w.command({ type: 'withdraw-research' });
  assert.match(result.error, /Select the research memory to withdraw/);
  assert.deepEqual(w.calls, []);
});
