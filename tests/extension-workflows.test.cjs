const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const {test} = require('node:test');
const source = readFileSync(join(__dirname, '../extension/workflow-link.js'), 'utf8');
const load = () => import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
test('bounded workflow navigation contains only identifiers and no authority', async () => {
  const {workflowURL} = await load();
  const url = new URL(workflowURL('http://127.0.0.1:8000', {
    workflow:'research-review',version:2,run:'11111111-1111-1111-1111-111111111111',stage:'analyze',
    token:'must-not-appear',context:'private',action:'run',
  }));
  assert.equal(url.pathname, '/');
  assert.equal(url.hash, '#workflows?workflow=research-review&version=2&run=11111111-1111-1111-1111-111111111111&stage=analyze');
  assert.equal(url.href.includes('private'), false);
});
test('rejects foreign origins, script URLs and invalid identities', async () => {
  const {workflowURL} = await load();
  for (const origin of ['https://attacker.test','javascript:alert(1)','http://localhost:8000@evil.test'])
    assert.throws(()=>workflowURL(origin,{workflow:'ok',version:1}));
  for (const change of [{workflow:'<script>'},{version:0},{version:1000001},{run:'../start'},{stage:'javascript:run()'}])
    assert.throws(()=>workflowURL('http://localhost:8000',{workflow:'ok',version:1,...change}));
});
