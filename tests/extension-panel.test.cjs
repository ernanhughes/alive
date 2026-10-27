// Execute the shipped panel script with controlled DOM/Chrome boundaries and delayed replies.
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { test } = require('node:test');
const { join } = require('node:path');
const source = readFileSync(join(__dirname, '../extension/panel.js'), 'utf8')
  .replace(/^import .*?;\r?\n/, 'const DEFAULT_BACKEND = "http://127.0.0.1:8000";\n');
const AsyncFunction = Object.getPrototypeOf(async () => {}).constructor;
const note = { status: 'validated', data: { model: 'synthetic', usage: { total_tokens: 0 },
  output: { summary: 'A reviewed note.', evidence_quote: 'A reviewed excerpt.', limitations: 'Fixture.' } } };

async function panel() {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, { disabled: true, value: '', checked: false,
      textContent: '', replaceChildren() {}, append() {} });
    return elements.get(id);
  };
  let resolveNote;
  let changed;
  let stored = {};
  const document = { getElementById: element, createElement: () => ({}) };
  const chrome = { storage: {
    local: { get: async () => ({}), set: async () => {} },
    session: { get: async () => stored },
    onChanged: { addListener: listener => { changed = listener; } },
  }, runtime: { sendMessage: async message => message.type === 'note'
    ? new Promise(resolve => { resolveNote = resolve; }) : { data: { ok: true } } } };
  const load = new AsyncFunction('chrome', 'document', 'clearInterval',
    source + '\nreturn { pollNote, action };');
  const api = await load(chrome, document, () => {});
  return { element, api,
    reply: response => resolveNote(response),
    change: async text => {
      stored = { latest: { payload: { text, url: 'https://docs.python.org/3/tutorial/' } } };
      await changed();
    } };
}

test('a late validated reply cannot restore a feedback target after Stop', async () => {
  const p = await panel();
  const pending = p.api.pollNote();
  await p.element('stop').onclick();
  const status = p.element('status').textContent;
  p.reply({ data: note });
  await pending;
  assert.equal(p.element('useful').disabled, true);
  assert.equal(p.element('needs-work').disabled, true);
  assert.equal(p.element('status').textContent, status);
  assert.equal(p.element('note').textContent, 'Observation stopped and permission revoked.');
});

test('a late reply cannot rate the previous excerpt after the preview changes', async () => {
  const p = await panel();
  const pending = p.api.pollNote();
  await p.change('A different reviewed observation.');
  p.reply({ data: note });
  await pending;
  assert.equal(p.element('useful').disabled, true);
});

test('an obsolete polling error cannot overwrite the stopped status', async () => {
  const p = await panel();
  const pending = p.api.action(() => p.api.pollNote());
  await p.element('stop').onclick();
  const status = p.element('status').textContent;
  p.reply({ error: 'The old request failed.' });
  await pending;
  assert.equal(p.element('status').textContent, status);
});

test('changing language requires a new reviewed snapshot and invalidates old feedback', async () => {
  const p = await panel();
  const pending = p.api.pollNote();
  p.element('analyse').disabled = false;
  p.element('language').onchange();
  p.reply({ data: note });
  await pending;
  assert.equal(p.element('analyse').disabled, true);
  assert.equal(p.element('useful').disabled, true);
  assert.match(p.element('status').textContent, /save the reviewed observation again/);
});

test('a current validated note still enables feedback', async () => {
  const p = await panel();
  const pending = p.api.pollNote();
  p.reply({ data: note });
  await pending;
  assert.equal(p.element('useful').disabled, false);
  assert.equal(p.element('needs-work').disabled, false);
  assert.match(p.element('status').textContent, /Meta note ready/);
});
