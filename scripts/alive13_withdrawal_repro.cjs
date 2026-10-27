/* Reproduce the ALIVE-12 withdrawal-target defect and record the corrected behaviour. */
const { execFileSync } = require('node:child_process');
const { readFileSync, writeFileSync, mkdirSync } = require('node:fs');
const { join } = require('node:path');

const root = join(__dirname, '..');
const archive = join(root, 'archives', 'ALIVE-13', 'evidence');
const base = 'af12bc88c91a85558873d01579dba93fdd6b1bbf';

function harness(source) {
  let listener;
  const session = {};
  const calls = [];
  const chrome = {
    sidePanel: { setPanelBehavior() {} },
    runtime: { id: 'test', getURL: p => 'chrome-extension://test/' + p,
      onMessage: { addListener: callback => { listener = callback; } } },
    storage: { local: { get: async () => ({ backend: 'http://127.0.0.1:61001', token: 't' }) },
      session: { get: async keys => typeof keys === 'string'
        ? { [keys]: session[keys] }
        : Object.fromEntries((keys || []).map(key => [key, session[key]])),
        set: async data => Object.assign(session, data),
        remove: async keys => { for (const key of keys || []) delete session[key]; } } },
    tabs: { onRemoved: { addListener() {} }, onUpdated: { addListener() {} } },
  };
  const prepared = source.replace(/^import .*?;\r?\n/, `const DEFAULT_BACKEND='http://127.0.0.1:61001';
const DEFAULT_BACKENDS=[DEFAULT_BACKEND]; const AUTHORISED_PAGES=[]; const isLocalDemo=()=>false;\n`);
  new Function('chrome', 'fetch', prepared)(chrome, async url => {
    calls.push(url);
    return { ok: true, json: async () => ({ id: 'result', data: {} }) };
  });
  return {
    session,
    calls,
    invoke: message => new Promise(resolve => listener(message,
      { id: 'test', url: 'chrome-extension://test/panel.html' }, resolve)),
  };
}

async function main() {
  const oldSource = execFileSync('git', ['show', `${base}:extension/background.js`], {
    cwd: root,
    encoding: 'utf8',
  });
  const newSource = readFileSync(join(root, 'extension', 'background.js'), 'utf8');
  const oldWorker = harness(oldSource);
  oldWorker.session.researchId = 'research-B-last-saved';
  const oldResult = await oldWorker.invoke({ type: 'withdraw-research' });
  const newWorker = harness(newSource);
  newWorker.session.researchId = 'research-B-last-saved';
  const newResult = await newWorker.invoke({
    type: 'withdraw-research',
    researchId: 'research-A-displayed',
  });
  const missingWorker = harness(newSource);
  missingWorker.session.researchId = 'research-B-last-saved';
  const missingResult = await missingWorker.invoke({ type: 'withdraw-research' });
  const evidence = {
    defect: 'The pre-ALIVE-13 background worker withdrew the last saved research ID, not the displayed result.',
    old_worker: {
      saved_id: 'research-B-last-saved',
      requested_displayed_id: null,
      withdrawn_target: oldResult.data ? oldWorker.calls[0] : null,
      target_was_last_saved: oldWorker.calls[0]?.includes('research-B-last-saved') || false,
    },
    corrected_worker: {
      saved_id: 'research-B-last-saved',
      requested_displayed_id: 'research-A-displayed',
      withdrawn_target: newResult.data ? newWorker.calls[0] : null,
      target_was_displayed: newWorker.calls[0]?.includes('research-A-displayed') || false,
    },
    missing_explicit_id: {
      error: missingResult.error || null,
      fetches: missingWorker.calls.length,
    },
    extension_tests: 'node --test tests/extension-background.test.cjs tests/extension-panel.test.cjs',
  };
  mkdirSync(archive, { recursive: true });
  writeFileSync(join(archive, 'withdrawal-target.json'), JSON.stringify(evidence, null, 2) + '\n');
  console.log(JSON.stringify(evidence, null, 2));
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
