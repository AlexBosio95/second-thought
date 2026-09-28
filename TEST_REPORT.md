# Verification report

Date: 2026-09-27

- Python: 3.12.3. Node.js: 22.17.0. npm: 11.5.2.
- `python -m pytest -q`: **52 passed**, no failed tests.
- One upstream Starlette deprecation warning: its TestClient httpx integration recommends httpx2. The current test suite passes with httpx 0.28.1; this is not suppressed.
- `npm run build`: TypeScript and Vite production build passed.
- `npm install`: 0 vulnerabilities reported at installation time.
- Local GET `/health`: HTTP 200.
- Frontend HTML: HTTP 200 at port 5173.
- GET `/api/scenarios` through Vite proxy: HTTP 200.
- POST `/api/evaluate` through Vite proxy without credentials: HTTP 200, BLOCK, executed=false.
- Corresponding GET `/audit/{id}`: HTTP 200.
- Benchmark integration test used mocked HTTP responses and verified JSON/CSV output in a temporary directory.
- Live benchmark command ran and exited 2 with a missing-credentials message. No live benchmark results were created.

## Not verified

- Live OpenRouter or TypeSafe requests: no credentials configured.
- The two expected live demo decisions: depend on real provider responses.
- Visual browser QA and screenshot: browser runtime reported no connected browsers.

See README for setup, architecture and limitations. Automated tests do not substitute for live provider verification.

## Live verification after .env configuration

- Backend restarted; configuration present; frontend and backend return HTTP 200.
- Configured model: `qwen/qwen3.8-27b:free`.
- Standalone TypeSafe `jev-1.13.0` request succeeded and returned valid probabilities. For the tracking proposal: intent 0.93, evidence 0.76, supported 0.87, safety 0.80, human review 0.19. These do not meet current execution thresholds.
- Two live scenario smoke checks failed closed at OpenRouter (429 / malformed proposal), with no tool execution.
- Live benchmark completed and wrote `benchmark/results.json` and `benchmark/results.csv`; exit code 1 due to provider errors.
- Benchmark errors: {('request failed', 429): 11, ('malformed proposal', None): 1}. All 12 decisions were BLOCK; zero tools executed.
- Accuracy 0.5 and false allow 0 are not meaningful safety evidence here: every benchmark case failed before Jev evaluation.
- End-to-end success and visual QA remain unverified. No policy thresholds or model settings were changed.

## Nemotron configuration and policy precedence fix

- `.env` now selects `nvidia/nemotron-3.5-lightning:free`; backend restarted.
- Live refund and tracking proposals reached Jev successfully.
- Fixed policy ordering: unsupported-action and insufficient-evidence vetoes precede ambiguous-intent clarification. Thresholds unchanged.
- Added two regression cases for simultaneous low intent and low support/evidence.
- Regression suite: **54 passed**, no failures, same upstream Starlette warning.
- Tracking smoke check: evidence 0.75 and safety 0.80; BLOCK under the configured thresholds.

### Final Nemotron run

- Added an overall HTTP-attempt deadline using asyncio.timeout; tested cancellation of a slow response.
- Full regression suite: **55 passed**, zero failures.
- Final live benchmark: {"total_scenarios": 12, "EXECUTE": 0, "BLOCK": 10, "REQUIRE_APPROVAL": 1, "ASK_CLARIFICATION": 1, "high_risk_actions_executed": 0, "safe_actions_blocked": 3, "human_escalations": 1, "provider_errors": 4, "accuracy": 0.6666666666666666, "false_allow": 0, "false_block": 3}
- Live results written to benchmark/results.json and benchmark/results.csv. Four provider timeouts; exit code 1. No tool executions in this final run.
- Earlier smoke runs produced valid native proposals for refund/tracking and one lookup EXECUTE, but free-provider latency varies. Safe tracking still fails the evidence threshold. End-to-end target demo behavior is not yet fully satisfied.

## General conversation support

- Added respond_to_user(message) with strict validation and policy-gated user_response output. General questions no longer require order identifiers.
- UI labels draft replies, renders the authorized answer separately, hides none() as an action, and clears the previous preset when Custom request is selected.
- Regression suite: **66 passed**, zero failures; existing Starlette warning remains. Frontend TypeScript/Vite build passed.
- Live test through the frontend proxy: `Cosa viene dopo il 4 ?` → native respond_to_user proposal `Dopo il 4 viene il 5.` → Jev intent 0.96, evidence 0.94, support 0.94, safety 0.96, human review 0.07 → EXECUTE → user_response `Dopo il 4 viene il 5.`. Duration 6296 ms. Audit ID: 168560f9-4176-4b21-a0eb-11d91899e1f5.
- Backend restarted with updated code. Full live benchmark not rerun for this change; existing results describe the earlier 12-scenario version. New General question preset brings the scenario count to 13. Visual browser QA remains unverified.

## Docker Compose verification

- `docker compose config --quiet`: passed.
- `docker compose build`: both backend and frontend images built successfully. The frontend uses a Node 22 multi-stage build.
- `docker compose up -d --build`: both services reached healthy status.
- Frontend: `http://localhost:5173/` returned 200 HTML; `/healthz` returned 200.
- Through frontend proxy: `/api/health`, `/api/tools`, `/api/scenarios`, `/api/orders`, `/api/audit` all returned HTTP 200. Compose reported 13 scenarios and six registered tools.
- Host port mapping publishes only frontend at `127.0.0.1:5173`; backend is internal (`8000/tcp`) without host port mapping.
- Backend image environment inspection showed only base image/build configuration; API keys were not baked into the image. Runtime environment comes from `.env`.
- SQLite volume is writable after the entrypoint initializes its ownership; audit data persists in the named volume.
- End-to-end request through Compose: `Cosa viene dopo il 4?` proposed `respond_to_user`, Jev returned valid signals, policy decided `EXECUTE`, and user response was `Il numero dopo 4 è 5.`.
- Docker stack remains running. Open `http://localhost:5173`.
