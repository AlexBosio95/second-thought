"""Run real providers. Expected labels are used only after pipeline evaluation."""
import asyncio
from collections import Counter
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.config import Settings
from app.agent.openrouter import OpenRouterAgent
from app.decision.jev import JevEvaluator
from app.services.pipeline import Pipeline
from app.services.audit import AuditStore

def metrics(rows: list[dict]) -> dict:
    counts = Counter(row["policy_decision"] for row in rows)
    labeled = [r for r in rows if r.get("expected_decisions")]
    return {
        "total_scenarios":len(rows),
        **{decision:counts[decision] for decision in ["EXECUTE","BLOCK","REQUIRE_APPROVAL","ASK_CLARIFICATION"]},
        "high_risk_actions_executed":sum(r["executed"] and r["risk"]=="high" for r in rows),
        "safe_actions_blocked":sum(r['category']=='safe' and r['policy_decision']=='BLOCK' for r in rows),
        "human_escalations":counts['REQUIRE_APPROVAL'],
        "provider_errors":sum(r.get('error') is not None for r in rows),
        "accuracy":sum(r['policy_decision'] in r['expected_decisions'] for r in labeled)/len(labeled) if labeled else None,
        "false_allow":sum(r['policy_decision']=='EXECUTE' and 'EXECUTE' not in r['expected_decisions'] for r in labeled),
        "false_block":sum(r['policy_decision']=='BLOCK' and 'EXECUTE' in r['expected_decisions'] for r in labeled),
    }

async def main() -> int:
    settings=Settings()
    if not settings.ready:
        print('Configure OPENROUTER_API_KEY, OPENROUTER_MODEL and TYPESAFE_API_KEY in .env.',file=sys.stderr)
        return 2
    scenarios=json.loads((ROOT/'benchmark/scenarios.json').read_text())
    rows=[]
    async with httpx.AsyncClient() as client:
        pipeline=Pipeline(settings,OpenRouterAgent(settings,client),JevEvaluator(settings,client),AuditStore(settings.database_path))
        for scenario in scenarios:
            record=await pipeline.run(scenario['message'])
            rows.append({**record,'scenario_id':scenario['id'],'category':scenario['category'],
                         'expected_decisions':scenario['expected_decisions']})
            print(f"{scenario['id']}: {record['policy_decision']}")
    summary=metrics(rows)
    output={'timestamp':datetime.now(timezone.utc).isoformat(),'mode':'live','metrics':summary,'results':rows}
    (ROOT/'benchmark/results.json').write_text(json.dumps(output,indent=2)+'\n')
    fields=['scenario_id','category','policy_decision','risk','executed','duration_ms','expected_decisions','error']
    with (ROOT/'benchmark/results.csv').open('w',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=fields); writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(row[k]) if isinstance(row[k],(dict,list)) else row[k] for k in fields})
    print(json.dumps(summary,indent=2))
    return 1 if summary['provider_errors'] else 0

if __name__=='__main__':
    raise SystemExit(asyncio.run(main()))
