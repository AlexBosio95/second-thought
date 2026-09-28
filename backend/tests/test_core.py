from copy import deepcopy
from unittest.mock import AsyncMock
import httpx
import pytest
from pydantic import ValidationError
from app.config import Settings
from app.decision.models import Choice, Decision, PolicyResult, Proposal, Signals
from app.decision.policy import decide
from app.decision.jev import build_state, parse_signals
from app.tools.registry import validate, ToolValidationError
from app.tools.executor import execute
from app.tools.orders import all_orders
from app.services.audit import AuditStore
from app.services.pipeline import Pipeline
from app.services.http import ProviderError, post_json
from app.agent.openrouter import OpenRouterAgent

@pytest.fixture
def signals():
    return Signals(intent_clear=.97, evidence_sufficient=.96, action_supported=.95,
                   safe_to_execute=.96, human_review_required=.05,
                   next_action=Choice(choice="execute", probabilities={"execute":.96,"clarify":.01,
                   "retrieve_more":.01,"human":.01,"block":.01}))

@pytest.fixture
def settings():
    return Settings(_env_file=None, openrouter_api_key="test", openrouter_model="test/model", typesafe_api_key="test")

def raw_signals(signals):
    data = signals.model_dump()
    return {"answers": {**{k: {"type":"noul", "noul":v} for k,v in data.items() if k != "next_action"},
                        "next_action": {"type":"choice", **data["next_action"]}}}

@pytest.mark.parametrize("field,value,expected", [
    ("intent_clear",.74,Decision.ASK_CLARIFICATION),
    ("human_review_required",.80,Decision.REQUIRE_APPROVAL),
    ("evidence_sufficient",.79,Decision.BLOCK),
    ("action_supported",.79,Decision.BLOCK),
    ("safe_to_execute",.89,Decision.REQUIRE_APPROVAL),
    ("safe_to_execute",.90,Decision.EXECUTE)])
def test_policy(signals, settings, field, value, expected):
    assert decide(signals.model_copy(update={field:value}), "high", settings).decision == expected

def test_unavailable(settings):
    assert decide(None,"high",settings).decision == Decision.BLOCK

@pytest.mark.parametrize("decision", [Decision.BLOCK, Decision.ASK_CLARIFICATION, Decision.REQUIRE_APPROVAL])
def test_guard(decision):
    proposal = Proposal(tool="refund_order", arguments={"order_id":"ORD-4412","amount":79})
    with pytest.raises(PermissionError):
        execute(proposal, PolicyResult(decision=decision, rule="test", reason="test"))

def test_execution_is_mock(signals,settings):
    before = all_orders()
    proposal = Proposal(tool="refund_order", arguments={"order_id":"ORD-4412","amount":79})
    assert execute(proposal, decide(signals,"high",settings))["status"] == "simulated"
    assert all_orders() == before

@pytest.mark.parametrize("tool,args", [
    ("unknown",{}),("get_order",{"order_id":"ORD-0000"}),
    ("get_order",{"order_id":"ORD-9182","extra":True}),
    ("refund_order",{"order_id":"ORD-4412","amount":999}),
    ("refund_order",{"order_id":"ORD-4412","amount":-1}),
    ("refund_order",{"order_id":"ORD-4412","amount":True}),
    ("refund_order",{"order_id":"ORD-4412","amount":float("nan")})])
def test_validation(tool,args):
    with pytest.raises(ToolValidationError): validate(Proposal(tool=tool,arguments=args))

def test_missing_address():
    with pytest.raises(ToolValidationError) as exc:
        validate(Proposal(tool="update_address",arguments={"order_id":"ORD-9182"}))
    assert exc.value.missing

def test_state():
    proposal=Proposal(tool="refund_order",arguments={"order_id":"ORD-9182","amount":249})
    state=build_state("Refund ORD-9182",{"status":"in_transit"},proposal,"high")
    for label in ["USER REQUEST","AVAILABLE CONTEXT","PROPOSED ACTION","ARGUMENTS","ACTION RISK"]:
        assert f"[{label}]" in state
    assert "in_transit" in state and "249" in state
    assert "reasoning" not in state

@pytest.mark.parametrize("value", [-.1,1.1,float("nan"),float("inf"),"0.9",True])
def test_bad_probability(signals,value):
    raw=raw_signals(signals); raw["answers"]["intent_clear"]["noul"]=value
    with pytest.raises((ValueError,ValidationError)): parse_signals(raw)

@pytest.mark.parametrize("choice,expected", [("block",Decision.BLOCK),("human",Decision.REQUIRE_APPROVAL),
    ("clarify",Decision.ASK_CLARIFICATION),("retrieve_more",Decision.BLOCK)])
def test_next_action_veto(signals,settings,choice,expected):
    probabilities={k:0.0 for k in signals.next_action.probabilities}; probabilities[choice]=1.0
    signals.next_action=Choice(choice=choice,probabilities=probabilities)
    assert decide(signals,"low",settings).decision==expected

async def test_pipeline_jev_unavailable(tmp_path,settings):
    agent=AsyncMock(); evaluator=AsyncMock()
    agent.propose.return_value=(Proposal(tool="refund_order",arguments={"order_id":"ORD-4412","amount":79}),"tool_call")
    evaluator.evaluate.side_effect=ProviderError("TypeSafe","timeout")
    audit=AuditStore(tmp_path/'audit.sqlite3')
    record=await Pipeline(settings,agent,evaluator,audit).run("Refund ORD-4412")
    assert record['policy_decision']=='BLOCK' and not record['executed']
    assert audit.get(record['id'])==record

@pytest.mark.parametrize("tool,args,expected",[("unknown",{},"BLOCK"),
    ("update_address",{"order_id":"ORD-9182"},"ASK_CLARIFICATION"),("none",{},"ASK_CLARIFICATION")])
async def test_pipeline_validation(tmp_path,settings,tool,args,expected):
    agent=AsyncMock(); evaluator=AsyncMock()
    agent.propose.return_value=(Proposal(tool=tool,arguments=args),"tool_call")
    result=await Pipeline(settings,agent,evaluator,AuditStore(tmp_path/'audit.sqlite3')).run("Fix my order")
    assert result['policy_decision']==expected and not result['executed']
    evaluator.evaluate.assert_not_called()

async def test_pipeline_success(tmp_path,settings,signals):
    agent=AsyncMock(); evaluator=AsyncMock()
    agent.propose.return_value=(Proposal(tool="send_tracking_link",arguments={"order_id":"ORD-9182"}),"tool_call")
    evaluator.evaluate.return_value=raw_signals(signals)
    result=await Pipeline(settings,agent,evaluator,AuditStore(tmp_path/'audit.sqlite3')).run("Tracking ORD-9182")
    assert result['executed'] and result['tool_execution_result']['status']=='simulated'
    assert all(s['status']=='done' for s in result['timeline'])

async def test_malformed_jev_retained(tmp_path,settings):
    agent=AsyncMock(); evaluator=AsyncMock()
    agent.propose.return_value=(Proposal(tool="get_order",arguments={"order_id":"ORD-9182"}),"tool_call")
    evaluator.evaluate.return_value={"answers":{}}
    result=await Pipeline(settings,agent,evaluator,AuditStore(tmp_path/'audit.sqlite3')).run("Lookup ORD-9182")
    assert result['policy_decision']=='BLOCK' and result['jev_raw']=={"answers":{}}

@pytest.mark.parametrize("status",[429,502,503,504])
async def test_retries(status,monkeypatch):
    sleep=AsyncMock(); monkeypatch.setattr('app.services.http.asyncio.sleep',sleep)
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(status)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError): await post_json(client,'test','https://example.com','test',{},1)
    assert len(calls)==4
    assert [c.args[0] for c in sleep.call_args_list]==[1,2,4]

async def test_http_timeout():
    def handler(request): raise httpx.ReadTimeout('timeout')
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError,match='timeout'): await post_json(client,'test','https://example.com','test',{},1)

async def test_openrouter_fallback(settings):
    bodies=[]
    def handler(request):
        import json
        bodies.append(json.loads(request.content))
        content='no tool' if len(bodies)==1 else '{"tool":"get_order","arguments":{"order_id":"ORD-9182"}}'
        return httpx.Response(200,json={"choices":[{"message":{"content":content}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        proposal,mode=await OpenRouterAgent(settings,client).propose('Lookup ORD-9182',{})
    assert mode=='json_fallback' and proposal.tool=='get_order'
    assert 'tools' in bodies[0] and 'tools' not in bodies[1]

async def test_openrouter_native(settings):
    def handler(request):
        return httpx.Response(200,json={"choices":[{"message":{"tool_calls":[{"function":{
            "name":"get_order","arguments":'{"order_id":"ORD-9182"}'}}]}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        proposal,mode=await OpenRouterAgent(settings,client).propose('Lookup ORD-9182',{})
    assert mode=='tool_call' and proposal.arguments['order_id']=='ORD-9182'

@pytest.mark.parametrize("body",['not json','{"x":NaN}','{"x":1e999}','[]'])
async def test_malformed_http(body):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,text=body))) as client:
        with pytest.raises(ProviderError,match='malformed'):
            await post_json(client,'test','https://example.com','test',{},1)

async def test_openrouter_multiple_calls(settings):
    call={"function":{"name":"get_order","arguments":'{"order_id":"ORD-9182"}'}}
    raw={"choices":[{"message":{"tool_calls":[call,call]}}]}
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=raw))) as client:
        with pytest.raises(ProviderError,match='multiple'):
            await OpenRouterAgent(settings,client).propose('Lookup',{})

async def test_audit_failure_prevents_execution(tmp_path,settings,signals,monkeypatch):
    from unittest.mock import Mock
    agent=AsyncMock(); evaluator=AsyncMock(); audit=Mock()
    agent.propose.return_value=(Proposal(tool="refund_order",arguments={"order_id":"ORD-4412","amount":79}),"tool_call")
    evaluator.evaluate.return_value=raw_signals(signals)
    audit.save.side_effect=OSError('disk full')
    executor=Mock(); monkeypatch.setattr('app.services.pipeline.execute',executor)
    with pytest.raises(OSError): await Pipeline(settings,agent,evaluator,audit).run('Refund ORD-4412')
    executor.assert_not_called()

@pytest.mark.parametrize("field", ["action_supported", "evidence_sufficient"])
def test_block_precedes_unclear_intent(signals,settings,field):
    signals.intent_clear=.63
    setattr(signals,field,.12)
    assert decide(signals,"high",settings).decision==Decision.BLOCK

async def test_total_http_deadline():
    import asyncio
    async def handler(request):
        await asyncio.sleep(.1)
        return httpx.Response(200,json={})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError,match="timeout"):
            await post_json(client,"test","https://example.com","test",{},.01)

@pytest.mark.parametrize('message', ['', '   ', 5, 'x'*4001])
def test_reply_validation(message):
    with pytest.raises(ToolValidationError):
        validate(Proposal(tool='respond_to_user',arguments={'message':message}))

@pytest.mark.parametrize('decision',[Decision.BLOCK,Decision.ASK_CLARIFICATION,Decision.REQUIRE_APPROVAL])
def test_reply_execution_guard(decision):
    with pytest.raises(PermissionError):
        execute(Proposal(tool='respond_to_user',arguments={'message':'Dopo il 4 viene il 5.'}),
                PolicyResult(decision=decision,rule='test',reason='test'))

async def test_general_reply_approved(tmp_path,settings,signals):
    agent=AsyncMock(); evaluator=AsyncMock()
    agent.propose.return_value=(Proposal(tool='respond_to_user',arguments={'message':'Dopo il 4 viene il 5.'}),'tool_call')
    evaluator.evaluate.return_value=raw_signals(signals)
    audit=AuditStore(tmp_path/'audit.sqlite3')
    result=await Pipeline(settings,agent,evaluator,audit).run('Cosa viene dopo il 4?')
    assert result['policy_decision']=='EXECUTE'
    assert result['user_response']=='Dopo il 4 viene il 5.'
    assert result['context']=={} and result['risk']=='low'
    assert result['executed'] and audit.get(result['id'])==result
    state=evaluator.evaluate.call_args.args[0]
    assert '[ACTION SEMANTICS]' in state and 'Dopo il 4 viene il 5.' in state

@pytest.mark.parametrize('unavailable',[False,True])
async def test_general_reply_withheld(tmp_path,settings,signals,unavailable):
    agent=AsyncMock(); evaluator=AsyncMock()
    agent.propose.return_value=(Proposal(tool='respond_to_user',arguments={'message':'Dopo il 4 viene il 9.'}),'tool_call')
    if unavailable:
        evaluator.evaluate.side_effect=ProviderError('TypeSafe','timeout')
    else:
        signals.action_supported=.1
        evaluator.evaluate.return_value=raw_signals(signals)
    result=await Pipeline(settings,agent,evaluator,AuditStore(tmp_path/'audit.sqlite3')).run('Cosa viene dopo il 4?')
    assert result['policy_decision']=='BLOCK' and not result['executed']
    assert result['user_response'] is None and result['tool_execution_result'] is None

async def test_native_reply_tool_call(settings):
    def handler(request):
        import json
        body=json.loads(request.content)
        assert any(t['function']['name']=='respond_to_user' for t in body['tools'])
        return httpx.Response(200,json={'choices':[{'message':{'tool_calls':[{'function':{
            'name':'respond_to_user','arguments':'{"message":"Dopo il 4 viene il 5."}'}}]}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        proposal,mode=await OpenRouterAgent(settings,client).propose('Cosa viene dopo il 4?',{})
    assert mode=='tool_call'
    assert validate(proposal)=={'message':'Dopo il 4 viene il 5.'}
