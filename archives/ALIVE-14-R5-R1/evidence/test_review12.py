"""Independent R5 observation probes; synthetic only, no Meta transport."""
import asyncio
import copy
import json
import pytest
import scripts.alive14r5_experiment as r
from alive.providers import MetaProvider, ProviderError
from alive.research_relationships import ResearchRelationships
from alive.web_models import WebExperience

@pytest.fixture(autouse=True)
def isolation(tmp_path,monkeypatch):
    monkeypatch.setattr(r,'RUNS',tmp_path/'runs')
    monkeypatch.setattr(r,'ARCHIVE',tmp_path/'archive')
    monkeypatch.delenv('ALIVE_META_API_KEY',raising=False)
    async def forbidden(*a,**kw):
        raise AssertionError('REVIEW-12 forbids Meta transport')
    monkeypatch.setattr(MetaProvider,'_request',forbidden)

def setup():
    p=r.verify_protocol_identity()
    s=r.prepare('synthetic')
    d=r.run_dir('synthetic',p)
    t=r.token_for(d)
    r.approve('synthetic',synthetic=True,stage=1)
    s=r.read_json(d/'state.json')
    a=r.read_json(d/'approval.json')
    return p,s,d,t,a

def approve(c,s,number):
    name='stage_1' if number==1 else 'full'
    return r.call(c,'POST',f"/research/experiment/campaigns/{s['campaign_digest']}/approve",{
        'stage':number,'call_cap':2 if number==1 else 18,
        'max_input_tokens':s['campaign_stages'][name]['reserved_tokens'],
        'max_output_tokens':1536,'max_usd':0,'no_retries':True,'human_attestation':False})

def consent(c,s,a,index):
    task=next(x for x in s['tasks'] if x['task_id']==s['task_order'][index//2])
    condition='A' if index%2==0 else 'B'
    exp={'campaign_digest':s['campaign_digest'],'approval_id':a['approval_id'],
         'run_id':s['run_id'],'stage':a['stage'],'task_id':task['task_id'],
         'condition':condition,'call_index':index}
    fresh=r.preview(c,task,s['provider'],task['memory_id'] if condition=='B' else None,exp)
    r.call(c,'POST','/research/outbound/authorize',{'consent_id':fresh['id'],'payload_sha256':fresh['payload_sha256'],'approved':True})
    return fresh

def dispatch(c,s,a,index):
    fresh=consent(c,s,a,index)
    return r.call(c,'POST','/research/relationships',{'consent_id':fresh['id']})

def test_server_dispatches_second_cell_first(monkeypatch):
    p,s,d,t,a=setup()
    seen=[]
    original=ResearchRelationships._local_stub_paired
    def capture(self,payload):
        seen.append(copy.deepcopy(payload))
        return original(self,payload)
    monkeypatch.setattr(ResearchRelationships,'_local_stub_paired',capture)
    with r.Client(r.build_settings('synthetic',p,d,t),t) as c:
        r.reactivate_approved_grants(c,d,s)
        result=dispatch(c,s,a,1)
    assert len(seen)==1 and 'historical_excerpt' in seen[0]
    assert result['analysis']['data']['call_index']==1
    print('CONFIRMED: server dispatched call_index=1 before any attempt at index=0')

def test_backend_dispatches_after_fatal_error(monkeypatch):
    p,s,d,t,a=setup()
    seen=[]
    def fail(self,payload):
        seen.append(payload)
        raise ProviderError('authentication',401)
    monkeypatch.setattr(ResearchRelationships,'_local_stub_paired',fail)
    with r.Client(r.build_settings('synthetic',p,d,t),t) as c:
        r.reactivate_approved_grants(c,d,s)
        first=dispatch(c,s,a,0)
        assert first['analysis']['data']['campaign_fatal'] is True
        second=dispatch(c,s,a,1)
        assert second['analysis']['data']['call_index']==1
    assert len(seen)==2
    print('CONFIRMED: backend dispatched index=1 after durable fatal 401 at index=0')

def test_runner_crash_recovery_continues_after_fatal(monkeypatch):
    p,s,d,t,a=setup()
    calls=[]
    original=ResearchRelationships._local_stub_paired
    def fail_once(self,payload):
        calls.append(payload)
        if len(calls)==1:
            raise ProviderError('authentication',401)
        return original(self,payload)
    monkeypatch.setattr(ResearchRelationships,'_local_stub_paired',fail_once)
    normal=r.call
    crashed=[]
    def crash(c,method,path,body=None,expected=200):
        result=normal(c,method,path,body,expected)
        if method=='POST' and path=='/research/relationships' and not crashed:
            crashed.append(True)
            raise SystemExit('simulated process exit after durable fatal settlement')
        return result
    monkeypatch.setattr(r,'call',crash)
    with pytest.raises(SystemExit,match='simulated process exit'):
        r.execute('synthetic')
    assert len(calls)==1
    monkeypatch.setattr(r,'call',normal)
    result=r.execute('synthetic')
    assert len(calls)==2
    rows=r.read_jsonl(d/'outputs.jsonl')
    assert rows[0]['campaign_fatal'] is True and len(rows)==2
    print('CONFIRMED: ordinary restart recovered fatal 401 but dispatched the next cell; phase='+result['phase'])

def test_cancellation_rolls_back_settlement_and_allows_stage_two(monkeypatch):
    p,s,d,t,a=setup()
    seen=[]
    original=ResearchRelationships._local_stub_paired
    def cancel_second(self,payload):
        seen.append(payload)
        if len(seen)==2:
            raise asyncio.CancelledError()
        return original(self,payload)
    monkeypatch.setattr(ResearchRelationships,'_local_stub_paired',cancel_second)
    with r.Client(r.build_settings('synthetic',p,d,t),t) as c:
        r.reactivate_approved_grants(c,d,s)
        first=dispatch(c,s,a,0)
        assert first['analysis']['status']=='validated'
        fresh=consent(c,s,a,1)
        async def cancel_and_inspect():
            try:
                await c.app.state.relationships.analyze(fresh['id'])
            except asyncio.CancelledError:
                pass
            async with c.app.state.kernel.db.sessions() as session:
                rows=await c.app.state.approvals.attempts_locked(session,s['campaign_digest'])
                second=next(x for x in rows if x.data.get('call_index')==1)
                return {'id':second.id,'status':second.status,'data':dict(second.data)}
        second=c.portal.call(cancel_and_inspect)
        assert second['status']=='reserved'
        assert not second['data'].get('campaign_fatal')
        assert 'charged_tokens' not in second['data']
        c.portal.call(c.app.state.relationships.initialize)
        async def recovered():
            async with c.app.state.kernel.db.sessions() as session:
                row=await session.get(WebExperience,second['id'])
                return {'status':row.status,'data':dict(row.data)}
        resumed=c.portal.call(recovered)
        assert resumed['status']=='interrupted' and resumed['data']['cost_liability_tokens']>0
        assert not resumed['data'].get('campaign_fatal')
        stage2=approve(c,s,2)['data']
        result=dispatch(c,s,stage2,2)
        assert result['analysis']['data']['call_index']==2
    assert len(seen)==3
    print('CONFIRMED: cancellation settlement rolled back; restart charged ambiguity but omitted fatal flag; stage 2 approved and dispatched')

def test_registration_accepts_display_manifest_divergence(monkeypatch):
    p,s,d,t,a=setup()
    # A fresh DB avoids duplicate-registration protection and preserves content identity.
    r.RUNS=r.RUNS.parent/'other-runs'
    normal=r.call
    def alternate(c,method,path,body=None,expected=200):
        if method=='POST' and path=='/research/experiment/campaigns':
            body=copy.deepcopy(body)
            body['manifest']=json.loads(json.dumps(body['manifest']))
            body['manifest']['tasks'][0]['question']='DISPLAYED QUESTION DIFFERS FROM ENFORCED CONTENT'
        return normal(c,method,path,body,expected)
    r.call=alternate
    try:
        other=r.prepare('synthetic')
    finally:
        r.call=normal
    otherd=r.run_dir('synthetic',p)
    othert=r.token_for(otherd)
    r.approve('synthetic',synthetic=True,stage=1)
    othera=r.read_json(otherd/'approval.json')
    seen=[]
    original=ResearchRelationships._local_stub_paired
    def capture(self,payload):
        seen.append(payload)
        return original(self,payload)
    monkeypatch.setattr(ResearchRelationships,'_local_stub_paired',capture)
    with r.Client(r.build_settings('synthetic',p,otherd,othert),othert) as c:
        record=r.fetch_campaign(c,other['campaign_digest'])['data']
        assert record['manifest']['tasks'][0]['question']!=record['content']['tasks'][0]['question']
        r.reactivate_approved_grants(c,otherd,other)
        dispatch(c,other,othera,0)
    assert seen[0]['research_question']==record['content']['tasks'][0]['question']
    assert seen[0]['research_question']!=record['manifest']['tasks'][0]['question']
    print('CONFIRMED: actual dispatched question differs from registered native-display manifest')

def test_revocation_queued_before_final_marker_blocks_dispatch(monkeypatch):
    p,s,d,t,a=setup()
    seen=[]
    original=ResearchRelationships._local_stub_paired
    def capture(self,payload):
        seen.append(payload)
        return original(self,payload)
    monkeypatch.setattr(ResearchRelationships,'_local_stub_paired',capture)
    with r.Client(r.build_settings('synthetic',p,d,t),t) as c:
        r.reactivate_approved_grants(c,d,s)
        fresh=consent(c,s,a,0)
        async def race():
            gate=asyncio.Event(); release=asyncio.Event()
            validation=c.app.state.relationships._validate_sources
            validations=0
            async def pause(session,row):
                nonlocal validations
                validations+=1
                if validations==2:
                    gate.set()
                    await release.wait()
                return await validation(session,row)
            c.app.state.relationships._validate_sources=pause
            executing=asyncio.create_task(c.app.state.relationships.analyze(fresh['id']))
            await gate.wait()
            revoke=asyncio.create_task(c.app.state.approvals.revoke(a['approval_id']))
            await asyncio.sleep(0)
            release.set()
            revocation=await revoke
            result=await executing
            return revocation,result
        revoked,result=c.portal.call(race)
        assert revoked['data']['status']=='revoked'
        assert result['analysis']['data']['campaign_fatal'] is True
        assert result['analysis']['data']['cost_liability_tokens']==0
    assert seen==[]
    print('PASS: queued revocation committed before final dispatch marker; zero provider calls, zero liability')

@pytest.mark.parametrize('field', ['research_question','current_excerpt','historical_excerpt','current_url','current_sha256','goal_instruction','instructions','schema','provider','model','run_id','approval_id','stage','call_index'])
def test_actual_outbound_mutation_is_refused(monkeypatch,field):
    p,s,d,t,a=setup()
    seen=[]
    stub=ResearchRelationships._local_stub_paired
    def capture(self,payload):
        seen.append(payload)
        return stub(self,payload)
    monkeypatch.setattr(ResearchRelationships,'_local_stub_paired',capture)
    if field=='instructions':
        original=ResearchRelationships._instructions
        monkeypatch.setattr(ResearchRelationships,'_instructions',lambda self,mode:original(self,mode)+' MUTATED')
    elif field=='schema':
        original=ResearchRelationships._schema
        def schema(self,mode):
            result=copy.deepcopy(original(self,mode)); result['title']='MUTATED'; return result
        monkeypatch.setattr(ResearchRelationships,'_schema',schema)
    elif field=='run_id':
        s=copy.deepcopy(s); s['run_id']='different-run'
    elif field=='approval_id':
        a=copy.deepcopy(a); a['approval_id']='different-approval'
    elif field=='stage':
        a=copy.deepcopy(a); a['stage']=2
    elif field=='call_index':
        pass
    else:
        original=ResearchRelationships._payload
        def payload(self,*args,**kwargs):
            result=original(self,*args,**kwargs)
            result[field]='MUTATED'
            return result
        monkeypatch.setattr(ResearchRelationships,'_payload',payload)
    with r.Client(r.build_settings('synthetic',p,d,t),t) as c:
        r.reactivate_approved_grants(c,d,s)
        if field=='call_index':
            task=next(x for x in s['tasks'] if x['task_id']==s['task_order'][0])
            exp={'campaign_digest':s['campaign_digest'],'approval_id':a['approval_id'],'run_id':s['run_id'],'stage':1,'task_id':task['task_id'],'condition':'A','call_index':1}
            with pytest.raises(RuntimeError):
                r.preview(c,task,s['provider'],None,exp)
        else:
            with pytest.raises(RuntimeError):
                consent(c,s,a,0)
    assert seen==[]
    print('PASS: modified outbound',field,'refused before provider dispatch')

def test_fresh_digest_budget_and_minimum_cap(monkeypatch):
    p,s,d,t,a=setup()
    r.RUNS=r.RUNS.parent/'fresh-runs'
    second=r.prepare('synthetic')
    assert s['tasks'][0]['snapshot_id']!=second['tasks'][0]['snapshot_id']
    assert s['campaign_digest']==second['campaign_digest']
    real=r.prepare('real')  # Preview only: creates no owner approval and performs no inference.
    assert real['campaign_stages']['stage_1']=={'call_cap':2,'reserved_tokens':10345,'worst_case_micro_usd':43967}
    assert real['totals']=={'calls':18,'reserved_tokens':92148,'worst_case_micro_usd':391635}
    content=real['campaign_content']
    assert sum((cell['reserved_tokens']*17+3)//4 for cell in content['cells'])==391635
    changed=copy.deepcopy(p)
    changed['tasks'][0]['current_source']['excerpt']+=' Changed.'
    assert r.campaign_digest(changed,'meta','muse-spark-1.3')!=r.campaign_digest(p,'meta','muse-spark-1.3')
    approval={'protocol_sha256':real['protocol_sha256'],'provider':real['provider'],'model':real['model'],
              'payload_sha256s':{x['task_id']:x['payload_sha256s'] for x in real['tasks']},
              'no_retries':True,'provenance':'authenticated_owner_interface','call_cap':2,
              'max_input_tokens':10345,'max_output_tokens':1536,'max_usd':0.44,'stage':1}
    monkeypatch.setenv('ALIVE_R4_RUNTIME_USD_CAP','0.40')
    assert r.validate_execution_approval(real,approval,'real',2)['effective_max_usd']==0.40
    approval['max_usd']=0.39
    assert r.validate_execution_approval(real,approval,'real',2)['effective_max_usd']==0.39
    approval['max_usd']=5.0
    monkeypatch.setenv('ALIVE_R4_RUNTIME_USD_CAP','5.0')
    assert r.validate_execution_approval(real,approval,'real',2)['effective_max_usd']==0.45
    print('PASS: UUID-independent digest, source sensitivity, budgets 10345/92148 tokens, 43967/391635 micro-USD, minimum owner/runtime/protocol cap')

def test_supersession_before_marker_blocks_dispatch(monkeypatch):
    p,s,d,t,a=setup()
    seen=[]
    def forbidden(self,payload):
        seen.append(payload)
        raise AssertionError('Superseded approval must not dispatch')
    monkeypatch.setattr(ResearchRelationships,'_local_stub_paired',forbidden)
    with r.Client(r.build_settings('synthetic',p,d,t),t) as c:
        r.reactivate_approved_grants(c,d,s)
        fresh=consent(c,s,a,0)
        newer=approve(c,s,1)
        assert newer['data']['approval_id']!=a['approval_id']
        result=r.call(c,'POST','/research/relationships',{'consent_id':fresh['id']})
    assert seen==[]
    assert result['analysis']['data']['cost_liability_tokens']==0
    assert result['analysis']['data']['campaign_fatal'] is True
    print('PASS: already-authorized consent refused after campaign approval supersession; zero dispatch')
