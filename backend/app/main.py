from contextlib import asynccontextmanager
import json
import logging
import httpx
from fastapi import FastAPI, HTTPException, Query
from app.config import ROOT, Settings
from app.agent.openrouter import OpenRouterAgent
from app.decision.jev import JevEvaluator
from app.decision.models import EvaluationRequest
from app.services.audit import AuditStore
from app.services.pipeline import Pipeline
from app.tools.orders import all_orders
from app.tools.registry import REGISTRY, definitions

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
SCENARIOS = json.loads((ROOT / "benchmark/scenarios.json").read_text())

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    async with httpx.AsyncClient() as client:
        app.state.settings = settings
        app.state.audit = AuditStore(settings.database_path)
        app.state.pipeline = Pipeline(settings, OpenRouterAgent(settings, client),
                                      JevEvaluator(settings, client), app.state.audit)
        yield

app = FastAPI(title="Second Thought", version="0.1.0", lifespan=lifespan)

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "providers_configured": app.state.settings.ready, "simulation_only": True}

@app.get("/tools")
def tools() -> list[dict]:
    return [dict(**item["function"], risk=REGISTRY[item["function"]["name"]][0]) for item in definitions()]

@app.get("/orders")
def orders() -> dict:
    return all_orders()

@app.get("/scenarios")
def scenarios() -> list[dict]:
    return [{k: v for k, v in scenario.items() if k != "expected_decisions"} for scenario in SCENARIOS]

@app.post("/evaluate")
async def evaluate(body: EvaluationRequest) -> dict:
    return await app.state.pipeline.run(body.message)

@app.post("/scenarios/{scenario_id}/run")
async def run_scenario(scenario_id: str) -> dict:
    scenario = next((s for s in SCENARIOS if s["id"] == scenario_id), None)
    if scenario is None:
        raise HTTPException(404, "Scenario not found")
    return await app.state.pipeline.run(scenario["message"])

@app.get("/audit")
def audit(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)) -> list[dict]:
    return app.state.audit.list(limit, offset)

@app.get("/audit/{audit_id}")
def audit_record(audit_id: str) -> dict:
    record = app.state.audit.get(audit_id)
    if record is None:
        raise HTTPException(404, "Audit record not found")
    return record
