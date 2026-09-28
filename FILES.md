# Project files

Source, configuration and documentation (generated caches excluded):

- `.dockerignore`
- `.env`
- `.env.example`
- `.gitignore`
- `Dockerfile.backend`
- `Dockerfile.frontend`
- `FILES.md`
- `LICENSE`
- `README.md`
- `TEST_REPORT.md`
- `backend/app/__init__.py`
- `backend/app/agent/__init__.py`
- `backend/app/agent/openrouter.py`
- `backend/app/agent/prompts.py`
- `backend/app/config.py`
- `backend/app/data/orders.json`
- `backend/app/decision/__init__.py`
- `backend/app/decision/jev.py`
- `backend/app/decision/models.py`
- `backend/app/decision/policy.py`
- `backend/app/main.py`
- `backend/app/services/__init__.py`
- `backend/app/services/audit.py`
- `backend/app/services/http.py`
- `backend/app/services/pipeline.py`
- `backend/app/tools/__init__.py`
- `backend/app/tools/executor.py`
- `backend/app/tools/orders.py`
- `backend/app/tools/registry.py`
- `backend/docker-entrypoint.sh`
- `backend/requirements.lock.txt`
- `backend/requirements.txt`
- `backend/tests/test_api_benchmark.py`
- `backend/tests/test_core.py`
- `benchmark/run_benchmark.py`
- `benchmark/scenarios.json`
- `docker-compose.yml`
- `frontend/index.html`
- `frontend/package-lock.json`
- `frontend/package.json`
- `frontend/server.mjs`
- `frontend/src/App.tsx`
- `frontend/src/main.tsx`
- `frontend/src/style.css`
- `frontend/src/types.ts`
- `frontend/tsconfig.json`
- `frontend/vite.config.ts`
- `pyproject.toml`

Generated locally: `.venv/`, `frontend/node_modules/`, `frontend/dist/`, `backend/audit.sqlite3`, Compose named volume `second-thought_audit-data`, and Python/TypeScript caches. `.env` is excluded from git and Docker build context.
