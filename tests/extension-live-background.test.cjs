const assert = require('node:assert/strict');
const { test } = require('node:test');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { createHash, webcrypto } = require('node:crypto');
const source = readFileSync(join(__dirname, '../extension/background.js'), 'utf8')
 .replace(/^import .*?;\r?\n/, 'const DEFAULT_BACKEND="http://127.0.0.1:8000"; const DEFAULT_BACKENDS=[DEFAULT_BACKEND]; const AUTHORISED_PAGES=[]; const isLocalDemo=()=>false;\n');
const sha = text => createHash('sha256').update(text).digest('hex');
function worker() {
  let listener;
  const calls = [], text = 'One sentence here. Remember this exact sentence.';
  const session = { observedTab: 1, observedUrl: 'http://127.0.0.1:8000/demo-live-01/python-3.11.html', grantId: 'grant',
    latest: { payload: { url: 'http://127.0.0.1:8000/demo-live-01/python-3.11.html', title: 'Mirror', text, capture_format_version: 2, capture_entries: [] } },
    selected: { snapshot: { id: 'snapshot', data: { goal_id: 'g', sha256: sha(text) } } } };
  const memory = { id: 'memory', data: { goal_id: 'g', url: session.observedUrl, sha256: sha(text), reliance_anchor: { revision: 7, quote: 'Old anchor.' } } };
  const chrome = { sidePanel: { setPanelBehavior() {} }, runtime: { id: 'test', getURL: p=>'chrome-extension://test/'+p,
    onMessage: { addListener(fn) { listener=fn; } } },
    storage: { local: { get: async () => ({backend: 'http://127.0.0.1:8000', goalId:'g'}) },
      session: { get: async () => session, set: async value=>Object.assign(session,value) } },
    tabs: { get: async () => ({url:session.observedUrl}), onRemoved:{addListener(){}}, onUpdated:{addListener(){}} },
    scripting:{ executeScript: async () => [{ result: {text,selection:{quote:'Remember this exact sentence.',occurrence_start:19}} }] } };
  new Function('chrome','fetch','crypto',source)(chrome,async (url, options) => {
    const body=options.body ? JSON.parse(options.body):undefined; calls.push({url,body});
    let data={};
    if(url.endsWith('/browser-experience')) data={goals:[{id:'g',data:{instruction:'Investigate'}}]};
    else if(url.includes('/research/memories?')) data={memories:[memory]};
    else if(url.includes('/research/relationships?')) data={connections:[],analyses:[]};
    else if(url.endsWith('/research/retrieve')) data={results:[]};
    else if(url.endsWith('/research/memories')) data=memory;
    else if(url.endsWith('/snapshots')) data=session.selected;
    else if(url.endsWith('/anchor')) data={...memory,data:{...memory.data,reliance_anchor:{...body,revision:8}}};
    return {ok:true,json:async()=>data};
  },webcrypto);
  return {calls,session,memory,command:message=>new Promise(resolve=>listener(message,{id:'test',url:'chrome-extension://test/panel.html'},resolve))};
}
test('live preview always specifies claim mode and the local fixture provider',async()=>{
  const w=worker(); const r=await w.command({type:'live-preview',memoryId:'memory',provider:'meta'});
  assert.ok(!r.error); assert.equal(w.calls[0].body.analysis_mode,'claim_comparison');
  assert.equal(w.calls[0].body.provider,'local_fixture_claim');
});
test('live preview refuses a snapshot from another active goal before transmission',async()=>{
  const w=worker();w.session.selected.snapshot.data.goal_id='other';
  const r=await w.command({type:'live-preview',memoryId:'memory'});
  assert.match(r.error,/active investigation/);assert.equal(w.calls.length,0);
});
test('live selection preserves the chosen occurrence and expected anchor revision',async()=>{
  const w=worker();const r=await w.command({type:'live-selection'});
  assert.equal(r.data.occurrence_start,19);assert.equal(r.data.expected_revision,7);
  assert.equal(r.data.expected_sha256,sha(w.session.latest.payload.text));
});
test('remembering a passage binds source SHA, chosen offset and revision without a model note',async()=>{
  const w=worker();const proposal=(await w.command({type:'live-selection'})).data;
  const r=await w.command({type:'live-remember',proposal});assert.ok(!r.error);
  const anchor=w.calls.find(x=>x.url.endsWith('/anchor')).body;
  assert.equal(anchor.occurrence_start,19);assert.equal(anchor.expected_revision,7);
  assert.equal(anchor.expected_sha256,proposal.expected_sha256);
  assert.equal(w.calls.some(x=>x.url.endsWith('/analyse')),false);
});
test('a changed selection source is refused before creating any snapshot or memory',async()=>{
  const w=worker();const proposal=(await w.command({type:'live-selection'})).data;w.calls.length=0;
  const r=await w.command({type:'live-remember',proposal:{...proposal,expected_sha256:'changed'}});
  assert.match(r.error,/Source or investigation changed/);assert.equal(w.calls.length,0);
});
