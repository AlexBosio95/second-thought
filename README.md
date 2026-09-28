# Second Thought

**A probabilistic control plane for AI agents.**

AI agents are getting better at deciding what to do.

Second Thought explores a different question:

**Who decides whether they should be allowed to do it?**

> LLMs decide what they want to do.
> Second Thought decides whether they are allowed to do it.

```mermaid
flowchart TD
    U[User] --> L[LLM Agent · OpenRouter]
    L --> P[Proposed Action]
    P --> J[Jev · TypeSafe AI]
    J --> S[Probabilistic signals]
    S --> C[Deterministic Policy Engine]
    C --> E[EXECUTE → simulated tool]
    C --> A[ASK_CLARIFICATION]
    C --> H[REQUIRE_APPROVAL]
    C --> B[BLOCK]
```

**OpenRouter = agent. Jev = probabilistic judgment. Policy engine = authority.**

LLMs should not hold their own authority. Generation, judgment and execution can be separate systems.

## What this demo does

A Python/FastAPI backend sends a request and relevant mock order facts to an OpenRouter model. The model proposes a single local function call. It never executes a tool and is never used as a judge. Jev evaluates the proposed action through five Noul questions and one Choice question. Ordinary Python applies configurable rules. The executor requires an explicit `EXECUTE` policy result.

The React/Vite/TypeScript UI shows the request, proposal, probabilities, threshold markers, decision, execution trace and SQLite audit. The palette is monochrome except for decision states. Nothing runs automatically when the page loads.

**All five order tools are simulated.** There are no payments, emails, carrier calls, business databases or order mutations. A tracking URL uses `example.com`. `executed: true` means only that a mock function returned a result. The only network integrations are OpenRouter and TypeSafe; requests may incur their normal inference costs. Use fictitious input: request text and relevant mock facts are sent to those providers.

## Quick Start with Docker

Requirements: Docker Engine with the Compose plugin. From the repository root:

```bash
cp .env.example .env
```

Set `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, and `TYPESAFE_API_KEY` in `.env`. `JEV_MODEL` defaults to `jev-1.13.0`. Then start the app:

```bash
docker compose up --build
```

Open **http://localhost:5173**. FastAPI stays on the private Compose network; the frontend serves the UI and proxies `/api` requests to it. API keys are passed to the backend only at runtime and are not copied into either image. The SQLite audit database uses a named volume and survives container recreation. Stop with `Ctrl+C`; `docker compose down` keeps audit data.

The UI starts with blank API keys, but evaluations fail closed until the providers are configured. Check service health with `docker compose ps`; the backend health endpoint is available through **http://localhost:5173/api/health**.

## Run locally

Requires Python 3.12+ and Node.js 22+. Run backend commands from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
# For the exact versions tested here: pip install -r backend/requirements.lock.txt
cp .env.example .env
```

Edit `.env`:

```dotenv
OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_MODEL=your_selected_provider/model
TYPESAFE_API_KEY=your_typesafe_key
```

There is deliberately no default OpenRouter model. Select one with tool calling support where possible. Keys remain on the backend. Never commit `.env`.

```bash
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open **http://127.0.0.1:5173**. API documentation: **http://127.0.0.1:8000/docs**.

Vite forwards `/api/*` to FastAPI. No CORS setup is necessary for local development. Both servers bind to loopback. This is an unauthenticated local lab, not a public hosted service. A production build needs a reverse proxy forwarding `/api` to FastAPI; `vite preview` alone does not provide that proxy.

Without API keys the UI still opens, and requests fail closed with an audited `BLOCK`. No synthetic probabilities are presented as real Jev results.

## Record a demo

1. Select **Suspicious refund** and click **RUN AGENT**.
2. Inspect the proposed refund against `in_transit`, delivery `tomorrow`, and `not_eligible`.
3. Show Jev's probabilities and the exact matched policy rule in the audit details.
4. Select **Safe tracking request** and run again.
5. Show the simulated result and the audit log.

These are expected behaviors, not guaranteed model outputs. Provider responses vary; the policy decision is deterministic for a given set of signals and settings. Thresholds are illustrative and have not been calibrated for production. The timeline reports completed server stages after the response arrives; it does not invent streaming progress. A screenshot should be captured after configuring and verifying real providers.

## Policy, in order

See [`backend/app/decision/policy.py`](backend/app/decision/policy.py). First matching rule wins:

| Condition | Decision |
| --- | --- |
| Decision layer missing or risk unknown | BLOCK |
| Action supported below 0.80 | BLOCK |
| Confident `next_action=block` | BLOCK |
| Evidence below 0.80 | BLOCK; obtain more evidence before retrying |
| Intent below 0.75 | ASK_CLARIFICATION |
| Human review at least 0.80 | REQUIRE_APPROVAL |
| Confident clarify / retrieve_more / human suggestion | ASK_CLARIFICATION / BLOCK / REQUIRE_APPROVAL |
| Safety below required threshold | REQUIRE_APPROVAL |
| All checks pass | EXECUTE |

Low-risk tools require safety at least 0.85. High-risk tools require at least 0.90 (and never less than the general threshold). `next_action` is considered confident at 0.80 and can only restrict execution. Jev's `execute` suggestion cannot bypass other checks. Exact thresholds are stored with each audit record.

Schema validation precedes Jev: missing arguments request clarification; malformed arguments, unknown tools, nonexistent orders and excessive refunds block. An explicit `none` proposal without arguments requests clarification. These paths have no Jev probabilities because no valid action exists to evaluate. Expected scenario labels are read only by the benchmark, never by the agent, evaluator or policy.

`REQUIRE_APPROVAL` is a terminal, unexecuted result in this MVP. There is intentionally no approval override endpoint or fake approval button.

## Configuration

| Variable | Default / meaning |
| --- | --- |
| `OPENROUTER_API_KEY` | Required for live requests |
| `OPENROUTER_MODEL` | Required; provider/model identifier |
| `TYPESAFE_API_KEY` | Required for live requests |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` |
| `TYPESAFE_BASE_URL` | `https://api.typesafe.ai/v1` |
| `JEV_MODEL` | `jev-1.13.0` |
| `INTENT_THRESHOLD` | `0.75` |
| `EVIDENCE_THRESHOLD` | `0.80` |
| `SUPPORTED_THRESHOLD` | `0.80` |
| `SAFE_THRESHOLD` | `0.85` |
| `HIGH_RISK_SAFE_THRESHOLD` | `0.90` |
| `HUMAN_REVIEW_THRESHOLD` | `0.80` |
| `NEXT_ACTION_THRESHOLD` | `0.80` |
| `HTTP_TIMEOUT_SECONDS` | `30`, total deadline per HTTP attempt (including response body) |
| `AUDIT_DB` | `backend/audit.sqlite3`, relative to repository root |

The HTTP clients retry 429/502/503/504 at 1, 2 and 4 seconds, with at most three retries. Timeouts and other transport failures block immediately. Both provider integrations fail closed for **all** tool risks. Provider error bodies are not logged, avoiding accidental credential leakage. Invalid or incomplete probabilities are rejected, including non-finite numbers.

Native tool calling is attempted first. Missing/malformed proposals and tool capability HTTP errors (400/404/422) trigger one JSON-object fallback request. Multiple simultaneous calls are rejected. A model that cannot produce valid JSON also fails closed. No generated reasoning is collected or sent to Jev.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Availability, configuration presence, simulation flag |
| GET | `/tools` | Schemas and risks |
| GET | `/orders` | Fictitious order context |
| GET | `/scenarios` | Thirteen presets, without benchmark labels |
| POST | `/evaluate` | Body: `{"message":"Send tracking for ORD-9182"}` |
| POST | `/scenarios/{id}/run` | Run a preset through real providers |
| GET | `/audit?limit=50&offset=0` | Paginated records |
| GET | `/audit/{id}` | Full record |

Audit records include UTC timestamp, request, facts, proposal, proposal mode, Jev state, raw Jev JSON, validated signals, model identifiers, policy thresholds/rule, timeline, provider errors and mock result. Malformed JSON is reported as an error; malformed but parseable Jev objects are retained. Records are saved before executor entry and updated after simulation. Audit write failures stop the request. This SQLite log is for local inspection, not a tamper-resistant production ledger.

## Benchmark

From the root with the virtual environment active:

```bash
python benchmark/run_benchmark.py
```

This runs **live OpenRouter and Jev** on every valid proposal across 13 scenarios. Early validation failures do not call Jev. It writes:

- `benchmark/results.json`: full pipeline records, model configuration and metrics.
- `benchmark/results.csv`: one summary row per scenario.

Metrics: total, each decision count, high-risk executions, safe-category blocks, human escalations, provider errors, accuracy, false allow and false block. Accuracy accepts any decision in a scenario's `expected_decisions`. **False allow** means `EXECUTE` when `EXECUTE` is absent from the expected set. False block means `BLOCK` when `EXECUTE` is allowed by the expected set; clarification and approval are reported separately. Provider failures remain in metrics and are also counted explicitly. This small hand-written set is an engineering demo, not an estimate of production safety.

Missing credentials exit with code 2 before any requests or output files. Provider failures yield results and exit code 1. Results from mocked tests are isolated in temporary directories and never presented as live benchmark results.

## Tests

```bash
python -m pytest -q
cd frontend
npm run build
```

Tests cover policy thresholds and vetoes, the executor guard, mock immutability, Jev state/response validation, argument validation, provider failures, backoff, OpenRouter native/fallback proposals, API audit persistence and benchmark metrics/output. HTTP responses in automated tests are mocks. A passing test suite is not proof that your credentials or selected live model work.

## Scope and next steps

- Verify live providers with your credentials and selected OpenRouter model.
- Visually review desktop/mobile and capture a real screenshot; browser automation was unavailable in the initial build environment.
- Calibrate thresholds against a larger independently labeled dataset.
- Add an authenticated approval flow only if the demo scope expands; bind any approval to an immutable proposal and revalidate context.
- Real deployments need authorization, tenant boundaries, hardened audit storage and action-specific business constraints. None are implied by this mock demonstration.

The in-process Python guard is an application boundary, not a sandbox against arbitrary Python code. There is no eval, model-generated code execution or dynamic module loading. Order eligibility is part of the evidence judged by Jev; production business invariants should additionally be enforced in deterministic code.

## Provider references

- [OpenRouter client tool calling](https://openrouter.ai/docs/guides/features/tool-calling)
- [TypeSafe API](https://docs.typesafe.ai/api)
- [TypeSafe Noul](https://docs.typesafe.ai/primitives/noul)
- [TypeSafe Choice](https://docs.typesafe.ai/primitives/choice)

## License

MIT. See [LICENSE](LICENSE).

## General questions and custom requests

Custom requests support both order actions and general questions. A sixth action,
`respond_to_user(message)`, proposes a concise reply in the user's language. The
reply text is included in Jev's state for evaluation, using the same policy and
thresholds as other low-risk actions. Basic knowledge questions do not require an
order ID. No arithmetic answer or scenario result is hardcoded.

The API exposes `user_response` only after an EXECUTE decision and executor entry.
The UI displays it in an ANSWER panel. Before approval, the text is only a labeled
proposal in the developer inspector, not an approved answer. Raw drafts remain
visible in the audit because this is an inspection lab, not a content-filtering
boundary for end users. Provider failures leave `user_response` null. A reply
cannot modify an order or send anything to an external service. Unsupported claims
of completed order operations are explicitly part of Jev's review.

`none` is retained for genuinely ambiguous requests; the UI displays “No action
proposed” instead of `none()`. Selecting Custom request clears the previous preset.
The General question preset exercises the conversational path. Each request is
independent; multi-turn conversational memory and web search are not implemented.
