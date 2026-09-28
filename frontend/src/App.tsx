import { useEffect, useState } from 'react';
import { ArrowDown, ArrowRight, Check, ChevronDown, Circle, Code2, Copy, ExternalLink, LockKeyhole, Play, ShieldCheck, Terminal, X } from 'lucide-react';
import type { Result, Scenario, SignalKey } from './types';

const labels: [SignalKey, string, string][] = [
 ['intent_clear', 'Intent clear', 'intent_threshold'],
 ['evidence_sufficient', 'Evidence sufficient', 'evidence_threshold'],
 ['action_supported', 'Action supported', 'supported_threshold'],
 ['safe_to_execute', 'Safe to execute', 'safe_threshold'],
 ['human_review_required', 'Human review', 'human_review_threshold'],
];
const steps = ['User Request', 'OpenRouter Agent', 'Proposed Action', 'Jev Evaluation', 'Policy Decision', 'Tool Execution'];
async function api<T>(path: string, init?: RequestInit): Promise<T> {
 const response = await fetch('/api' + path, init);
 if (!response.ok) throw new Error(`API request failed (${response.status}). Check that the backend is running.`);
 return response.json();
}
const pretty = (value: unknown) => JSON.stringify(value, null, 2);

export default function App() {
 const [scenarios, setScenarios] = useState<Scenario[]>([]);
 const [selected, setSelected] = useState('suspicious-refund');
 const [message, setMessage] = useState('Refund ORD-9182, the package never arrived.');
 const [result, setResult] = useState<Result | null>(null);
 const [history, setHistory] = useState<Result[]>([]);
 const [busy, setBusy] = useState(false);
 const [error, setError] = useState('');
 const [ready, setReady] = useState<boolean | null>(null);
 const [tab, setTab] = useState<'lab' | 'audit'>('lab');
 const [copied, setCopied] = useState(false);
 useEffect(() => {
  Promise.all([api<Scenario[]>('/scenarios'), api<{providers_configured: boolean}>('/health'), api<Result[]>('/audit')])
   .then(([items, health, records]) => {setScenarios(items);setReady(health.providers_configured);setHistory(records);})
   .catch(e => setError(e.message));
 }, []);
 function selectScenario(id: string) {
  const scenario = scenarios.find(item => item.id === id);
  setSelected(id); setMessage(scenario?.message ?? '');
  setResult(null); setError('');
 }
 async function run() {
  if (!message.trim() || busy) return;
  setBusy(true);setError('');setResult(null);
  try {
   const data = await api<Result>('/evaluate', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message})});
   setResult(data);setHistory(current => [data,...current].slice(0,50));
  } catch (e) {setError(e instanceof Error ? e.message : 'Request failed');}
  finally {setBusy(false);}
 }
 async function copyRecord() {
  try {await navigator.clipboard.writeText(pretty(result));setCopied(true);setTimeout(()=>setCopied(false),1500);}
  catch {setError('Clipboard unavailable. Copy the JSON from the audit details below.');}
 }
 const isReply = result?.agent_proposal?.tool === 'respond_to_user';
 const hasProposal = result?.agent_proposal && result.agent_proposal.tool !== 'none';
 const stateClass = result?.policy_decision.toLowerCase() ?? 'idle';
 return <div className="app">
  <header><a className="brand" href="/" aria-label="Second Thought home"><span className="mark">s<span>t</span><i>_</i></span><span>Second Thought<span className="version"> / v0.1</span></span></a>
   <div className="header-right"><span className="outline-pill"><span className="tiny-dot"/> SIMULATION ONLY</span><a className="docs-link" href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">API docs <ExternalLink size={13}/></a></div>
  </header>
  <main>
   <div className="eyebrow"><span className="short-line"/> THE AGENT CONTROL LAB</div>
   <section className="hero"><div><h1>A second thought.<br/><span>Before the first action.</span></h1><p>A probabilistic control plane for AI agents.</p></div>
    <div className="principle"><div><span>01</span> The LLM proposes.</div><div><span>02</span> Jev evaluates.</div><div><span>03</span> <strong>Code has final authority.</strong></div></div>
   </section>
   <div className="workspace-bar"><nav aria-label="Workspace"><button className={tab==='lab'?'active':''} onClick={()=>setTab('lab')}><Terminal size={15}/> Playground</button><button className={tab==='audit'?'active':''} onClick={()=>setTab('audit')}><Code2 size={15}/> Audit log <span className="count">{history.length}</span></button></nav><span className="connection">{ready===null?'Connecting to backend':ready?'Live providers configured':'API keys not configured'}</span></div>
   {error && <div className="error" role="alert">{error}<button aria-label="Dismiss error" onClick={()=>setError('')}><X size={16}/></button></div>}
   {tab==='audit' ? <section className="audit-panel"><div className="section-heading"><h2>Every decision leaves a trace.</h2><span>Latest 50 evaluations</span></div>{history.length===0?<p className="muted">Run your first request to create an audit record.</p>:history.map(item=><button className="audit-row" key={item.id} onClick={()=>{setResult(item);setMessage(item.user_request);setTab('lab');}}><span className="mono">{new Date(item.timestamp).toLocaleTimeString()}</span><span>{item.user_request}</span><span className={'decision-tag '+item.policy_decision.toLowerCase()}>{item.policy_decision.replaceAll('_',' ')}</span><ArrowRight size={16}/></button>)}</section> : <>
   <div className="lab-grid">
    <section className="panel request-panel"><div className="panel-heading"><span className="panel-number">01</span><h2>User request</h2><span className="role">INPUT</span></div>
     <label className="field-label" htmlFor="scenario">LOAD A SCENARIO</label><div className="select-wrap"><select id="scenario" disabled={busy} value={selected} onChange={event=>selectScenario(event.target.value)}><option value="">Custom request</option>{scenarios.map(s=><option key={s.id} value={s.id}>{s.title}</option>)}</select><ChevronDown size={15}/></div>
     <label className="field-label message-label" htmlFor="request">WHAT SHOULD THE AGENT DO?</label><textarea placeholder="Ask a question or describe an order action…" id="request" disabled={busy} value={message} onChange={event=>{setMessage(event.target.value);setSelected('');setResult(null);}} maxLength={4000}/>
     <div className="input-meta"><span>General questions + mock orders</span><span>{message.length} / 4000</span></div>
     <button className="run-button" disabled={busy || !message.trim()} onClick={run}>{busy?<span className="spinner"/>:<Play size={15} fill="currentColor"/>}{busy?'EVALUATING…':'RUN AGENT'}<span>↵</span></button>
     <div className="panel-foot"><LockKeyhole size={13}/><span>Every tool is simulated. No external actions.</span></div>
    </section>
    <section className="panel proposal-panel"><div className="panel-heading"><span className="panel-number">02</span><h2>Agent proposal</h2><span className="role">OPENROUTER</span></div>
     <div className="code-window"><div className="code-title"><span><i/><i/><i/></span><span>proposed_action.json</span><Code2 size={13}/></div><div className="code-body"><span className="code-comment">{isReply ? '// Draft reply. Not an authorized answer.' : '// A proposal. Never an execution.'}</span>{hasProposal && result?.agent_proposal?<><div className="tool-name">{result.agent_proposal.tool}<span>(</span></div><div className="arguments">{Object.entries(result.agent_proposal.arguments).map(([key,value])=><div key={key}><span>{key}: </span><b>{pretty(value)}</b></div>)}</div><div className="tool-name punctuation">)</div></>:<div className="empty-code">{busy?'Waiting for agent proposal…':result?.agent_proposal?.tool==='none'?'No action proposed':'Waiting for a proposal'}<span>{result?.agent_proposal?.tool==='none'?'The request needs more detail.':'The agent proposes an order action or a reply.'}</span></div>}</div><div className="code-footer"><span>TOOL RISK</span><span className="risk">{result?.risk?.toUpperCase() ?? '—'}</span></div></div>
     <div className="authority-divider"><span/><LockKeyhole size={14}/><span/></div><p className="authority-copy">The agent stops here.<br/><strong>Execution requires a policy decision.</strong></p>
     <div className="panel-foot"><Circle size={11}/><span>{result?.proposal_mode==='json_fallback'?'Structured JSON fallback':result?.proposal_mode==='tool_call'?'Native tool calling':'Generation layer'}</span></div>
    </section>
    <section className={'panel judgment-panel '+stateClass}><div className="panel-heading"><span className="panel-number">03</span><h2>Second Thought</h2><span className="role">JEV + POLICY</span></div>
     <div className="signals-heading"><span>PROBABILISTIC SIGNALS</span><span>P(YES)</span></div>
     <div className="signals">{labels.map(([key,label,thresholdKey])=>{const value=result?.jev?.[key];const threshold=result?.thresholds[key==='safe_to_execute'&&result?.risk==='high'?'high_risk_safe_threshold':thresholdKey];return <div className="signal" key={key}><div><label>{label}</label><span className="mono">{value===undefined?'—':Math.round(value*100)+'%'}</span></div><div className="meter" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={value===undefined?undefined:Math.round(value*100)}><div style={{width:(value??0)*100+'%'}}/>{threshold!==undefined&&<i title={'Threshold '+threshold} style={{left:threshold*100+'%'}}/>}</div></div>})}</div>
     <div className={'decision '+stateClass} aria-live="polite"><div className="decision-label"><ShieldCheck size={14}/> DETERMINISTIC DECISION</div><strong>{result?result.policy_decision.replaceAll('_',' '):busy?'EVALUATING':'AWAITING REQUEST'}</strong><p>{result?.policy.reason ?? 'The policy engine has the final word.'}</p></div>
    </section>
   </div>
   <section className="timeline-section"><div className="timeline-heading"><span>EXECUTION TRACE</span><span>{busy?'Request in progress · stages update on completion':result?`${result.duration_ms} ms · ${result.id.slice(0,8)}`:'No evaluation yet'}</span></div><ol className="timeline">{steps.map((name,i)=>{const status=result?.timeline[i].status??'waiting';return <li key={name} className={status}><div><span className="step-index">{String(i+1).padStart(2,'0')}</span>{status==='done'?<Check size={13}/>:status==='blocked'?<X size={13}/>:<Circle size={9}/>}</div><strong>{name}</strong><small>{status}</small></li>})}</ol></section>
   {result&&<section className="result-section"><div className="result-top"><div><span className="eyebrow">EXECUTION RESULT</span><h3>{result.executed?(isReply?'Reply authorized.':'Executed in simulation.'):result.policy_decision==='REQUIRE_APPROVAL'?'Waiting for human approval.':result.policy_decision==='ASK_CLARIFICATION'?'More detail is needed.':'Execution prevented.'}</h3></div><span className={'decision-tag '+stateClass}>{result.executed?(isReply?'REPLY APPROVED':'MOCK ONLY'):'NO ACTION EXECUTED'}</span></div>{result.error&&<p className="provider-error">{result.error.provider}: {result.error.kind}{result.error.status?` · HTTP ${result.error.status}`:''}. Execution is blocked.</p>}{result.executed && result.user_response && <div className="approved-reply" aria-live="polite"><span className="field-label">ANSWER</span><p>{result.user_response}</p></div>}{result.tool_execution_result!=null && !isReply && <pre>{pretty(result.tool_execution_result)}</pre>}{result.policy_decision==='REQUIRE_APPROVAL'&&<p className="muted">This MVP records the approval requirement. It does not implement an approval or execution override.</p>}<details><summary>Inspect context, signals & audit record <ArrowDown size={14}/></summary><button className="copy-button" onClick={copyRecord}><Copy size={13}/>{copied?'Copied':'Copy JSON'}</button><pre>{pretty(result)}</pre></details></section>}
   </>}
   <footer><span>LLMs should not hold their own authority.</span><span>GENERATION <ArrowRight size={12}/> JUDGMENT <ArrowRight size={12}/> EXECUTION</span></footer>
  </main>
 </div>;
}
