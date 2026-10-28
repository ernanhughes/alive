"""Independent REVIEW-11 probes. Synthetic campaigns only; network forbidden."""
import json
import socket
import pytest
import scripts.alive14r4_experiment as r
from alive.research_relationships import ResearchRelationships

@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(r, 'RUNS', tmp_path / 'runs')
    monkeypatch.setattr(r, 'ARCHIVE', tmp_path / 'archive')
    monkeypatch.delenv('ALIVE_META_API_KEY', raising=False)
    def denied(*a, **kw):
        raise AssertionError('External network forbidden during REVIEW-11')
    monkeypatch.setattr(socket, 'create_connection', denied)

def setup():
    p = r.verify_protocol_identity()
    s = r.prepare('synthetic')
    d = r.run_dir('synthetic', p)
    t = r.token_for(d)
    return p, s, d, t

def stage(s, d, t, number=1, cap=2):
    with r.Client(r.build_settings('synthetic', r.verify_protocol_identity(), d, t), t) as c:
        return r.call(c, 'POST', f"/research/experiment/campaigns/{s['campaign_digest']}/approve", {
            'stage':number, 'call_cap':cap,
            'max_input_tokens':s['campaign_stages']['full' if cap>2 else 'stage_1']['reserved_tokens'],
            'max_output_tokens':1536, 'max_usd':0.0, 'no_retries':True,
            'human_attestation':False})

def test_revoked_campaign_continues_dispatch(monkeypatch):
    p,s,d,t=setup()
    a=stage(s,d,t)
    r.approve('synthetic', synthetic=True)
    original=r.call
    revoked=[]
    def hooked(c, method, path, body=None, expected=200):
        result=original(c,method,path,body,expected)
        if method=='POST' and path=='/research/relationships' and not revoked:
            revoked.append(original(c,'POST',f"/research/experiment/approvals/{a['data']['approval_id']}/revoke",{}))
        return result
    monkeypatch.setattr(r,'call',hooked)
    result=r.execute('synthetic')
    assert revoked[0]['data']['status']=='revoked'
    assert result['execution']['attempted_dispatches']==2
    print('CONFIRMED: second dispatch occurred AFTER campaign approval revocation')

def test_local_question_and_hash_edits_bypass_digest(monkeypatch):
    p,s,d,t=setup()
    stage(s,d,t)
    r.approve('synthetic', synthetic=True)
    s=r.read_json(d/'state.json')
    approved_digest=s['campaign_digest']
    task=next(x for x in s['tasks'] if x['task_id']==s['task_order'][0])
    original_question=task['question']
    task['question']='Changed question outside the approved campaign'
    with r.Client(r.build_settings('synthetic',p,d,t),t) as c:
        r.reactivate_approved_grants(c,d,s)
        for label,memory in [('A',None),('B',task['memory_id'])]:
            fresh=r.preview(c,task,s['provider'],memory)
            task['payload_sha256s'][label]=fresh['payload_sha256']
            task['request_sha256s'][label]=fresh['request_sha256']
    r.write_state(d,s)
    a=r.read_json(d/'approval.json')
    a['payload_sha256s'][task['task_id']]=task['payload_sha256s']
    r.write_json(d/'approval.json',a)
    seen=[]
    original=ResearchRelationships._local_stub_paired
    def capture(self,payload):
        seen.append(payload['research_question'])
        return original(self,payload)
    monkeypatch.setattr(ResearchRelationships,'_local_stub_paired',capture)
    result=r.execute('synthetic',limit=1)
    assert seen==[task['question']]
    assert result['campaign_digest']==approved_digest
    assert original_question!=seen[0]
    print('CONFIRMED: local JSON edits dispatched changed question under unchanged server approval/digest')

def test_stage_one_accepts_full_campaign_cap():
    p,s,d,t=setup()
    a=stage(s,d,t,number=1,cap=18)
    assert a['data']['stage']==1 and a['data']['call_cap']==18
    print('CONFIRMED: stage=1 accepts call_cap=18 despite registered stage_1 cap=2')

def test_blind_status_route_correlates_content(monkeypatch):
    p,s,d,t=setup()
    r.approve('synthetic',synthetic=True)
    result=r.execute('synthetic')
    with r.Client(r.build_settings('synthetic',p,d,t),t) as c:
        view=r.call(c,'GET',f"/research/blind/runs/{result['blind']['run_id']}")
        assert view['outputs']
        inventory=r.call(c,'GET','/research/relationships')
        events=c.get('/api/v1/events',params={'limit':500}).json()
        assert all('payload_sha256' not in e['payload'] for e in events if e['event_type']=='research.paired_analysis_settled')
        print('BLIND inventory:',json.dumps(inventory)[:700])
        assert all('historical_memory_id' not in x['data'] for x in inventory['analyses'])

def test_staged_order_budget_digest_and_revisions():
    p,s,d,t=setup()
    stage(s,d,t)
    r.approve('synthetic',synthetic=True)
    first=r.execute('synthetic')
    assert first['execution']['attempted_dispatches']==2
    again=r.execute('synthetic',limit=16)
    assert again['execution']['attempted_dispatches']==2
    stage(s,d,t,2,18)
    r.approve('synthetic',synthetic=True)
    end=r.execute('synthetic',limit=16)
    rows=r.read_jsonl(d/'outputs.jsonl')
    assert [(x['task_id'],x['condition']) for x in rows]==[(task,c) for task in s['task_order'] for c in ('A','B')]
    assert len({x['attempt_id'] for x in rows})==18
    r.rate('synthetic',synthetic=True)
    r.reveal('synthetic'); r.analyse('synthetic'); r.archive('synthetic')
    print('STAGED: 2 + 16 distinct attempts, stable order, restart/archive successful')

@pytest.mark.parametrize('category,status', [('authentication',401),('access_denied',403),('unsupported_schema',400),('quota_exhausted',402),('rate_limit',429),('timeout',None),('ambiguous_settlement',None)])
def test_all_fatal_categories_stop_and_no_replay(monkeypatch,category,status):
    from alive.providers import ProviderError
    p,s,d,t=setup()
    r.approve('synthetic',synthetic=True)
    calls=[]
    def fail(self,payload):
        calls.append(payload)
        raise ProviderError(category,status)
    monkeypatch.setattr(ResearchRelationships,'_local_stub_paired',fail)
    result=r.execute('synthetic')
    assert len(calls)==1
    assert result['phase']=='blocked'
    rows=r.read_jsonl(d/'outputs.jsonl')
    assert len(rows)==1 and rows[0]['cost_liability_tokens']>0
    with pytest.raises(SystemExit):
        r.execute('synthetic')
    assert len(calls)==1
    print('FATAL',category,': one dispatch; positive conservative liability; restart replay refused')

def test_unwrapped_timeout_fails_to_stop(monkeypatch):
    p,s,d,t=setup()
    stage(s,d,t)
    r.approve('synthetic',synthetic=True)
    calls=[]
    def fail(self,payload):
        calls.append(payload)
        raise TimeoutError('governor wall timeout')
    monkeypatch.setattr(ResearchRelationships,'_local_stub_paired',fail)
    result=r.execute('synthetic')
    assert len(calls)==2
    rows=r.read_jsonl(d/'outputs.jsonl')
    assert all(x['error_category']=='TimeoutError' and not x['campaign_fatal'] for x in rows)
    print('CONFIRMED: raw wall-clock TimeoutError is nonfatal and dispatch continues')

def test_fresh_database_digest_and_budget():
    p,s,d,t=setup()
    first=s
    r.RUNS=r.RUNS.parent/'fresh-runs'
    second=r.prepare('synthetic')
    assert first['tasks'][0]['snapshot_id']!=second['tasks'][0]['snapshot_id']
    assert first['campaign_digest']==second['campaign_digest']
    real=r.prepare('real')  # Preview registration only. No approval and no inference.
    assert real['campaign_stages']['stage_1']=={'call_cap':2,'reserved_tokens':10345,'worst_case_micro_usd':43967}
    assert real['totals']=={'calls':18,'reserved_tokens':92148,'worst_case_micro_usd':391635}
    from copy import deepcopy
    altered=deepcopy(p)
    altered['tasks'][0]['current_source']['excerpt']+=' Modified.'
    assert r.campaign_digest(altered,'meta','muse-spark-1.3')!=r.campaign_digest(p,'meta','muse-spark-1.3')
    print('DIGEST stable across distinct fresh database IDs; source-sensitive; budget 10345/92148 tokens and 43967/391635 micro-USD')

def test_superseded_approval_and_placeholder_identity():
    p,s,d,t=setup()
    a=stage(s,d,t)
    r.approve('synthetic',synthetic=True)
    stage(s,d,t,2,18)
    with pytest.raises(SystemExit,match='no longer active'):
        r.execute('synthetic')
    with r.Client(r.build_settings('synthetic',p,d,t),t) as c:
        record=r.call(c,'GET',f"/research/experiment/approvals/{a['data']['approval_id']}")
        assert record['data']['status']=='superseded'
        url=r.API+f"/research/experiment/campaigns/{s['campaign_digest']}/approve"
        response=c.post(url,json={'stage':1,'call_cap':2,'max_input_tokens':12000,'max_output_tokens':1536,'max_usd':0,'no_retries':True,'approved_by':'placeholder'})
        assert response.status_code==422
        response=c.get(r.API+'/research/experiment/campaigns',headers={'Authorization':'Bearer invalid-review11-token'})
        assert response.status_code==401
    print('APPROVAL: superseded pointer, placeholder identity field and invalid bearer rejected')

def test_mixed_scoring_abstention_missing_misleading_revision(monkeypatch):
    p,s,d,t=setup()
    r.approve('synthetic',synthetic=True)
    original=ResearchRelationships._local_stub_paired
    counter=[]
    def mixed(self,payload):
        counter.append(1)
        out=original(self,payload)
        if len(counter)==1:
            return out.model_copy(update={'answer':'Insufficient evidence to answer.','sufficient_evidence':False,'evidence':[], 'confidence':0.1,'abstention_reason':'The current excerpt does not establish the requested limitation.'})
        if len(counter)==2:
            return self._local_stub_paired_invalid(payload)
        if len(counter)==3:
            return out.model_copy(update={'answer':'This proves every system is always safe.'})
        return out
    monkeypatch.setattr(ResearchRelationships,'_local_stub_paired',mixed)
    end=r.execute('synthetic')
    rows=r.read_jsonl(d/'outputs.jsonl')
    assert rows[0]['abstained'] is True
    assert rows[1]['missing'] is True
    r.rate('synthetic',synthetic=True)
    with r.Client(r.build_settings('synthetic',p,d,t),t) as c:
        view=r.call(c,'GET',f"/research/blind/runs/{end['blind']['run_id']}")
        for row in rows[:3]:
            output=next(x for x in view['outputs'] if x['output_sha256']==row['output_sha256'])
            rubric={'factually_supported':'yes','relevant_to_goal':'yes','revealed_new':'yes','already_obvious':'no','would_act':'yes','misleading':'yes' if row is rows[2] else 'no','uncertain':'no'}
            r.call(c,'POST',f"/research/blind/runs/{end['blind']['run_id']}/ratings",{'output_id':output['output_id'],'output_sha256':output['output_sha256'],'capability':view['rating_capability'],'rubric':rubric,'synthetic':True})
    r.reveal('synthetic'); r.analyse('synthetic'); r.archive('synthetic')
    analysis=r.read_json(d/'analysis.json')
    missing=next(x for x in analysis['tasks'] if x['task_id']==rows[1]['task_id'])['conditions'][rows[1]['condition']]
    assert missing['missing'] and missing['supported_useful'] is False
    assert set(analysis['secondary']['misleading_by_condition'])=={'A','B','C'}
    assert analysis['secondary']['misleading_by_condition'][rows[2]['condition']]>=1
    results=r.read_json(d/'results.json')
    assert len(results['ratings'])==30
    print('MIXED: abstention, rejection/missing, misleading answer and three rating revisions archived; missing cannot score useful')
