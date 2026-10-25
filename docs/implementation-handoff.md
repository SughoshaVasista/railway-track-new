# AMRIN implementation handoff

## Architecture

- React/Vite frontend in `src/`, with Axios API helpers in `src/services/api.js` and role-aware routes.
- FastAPI backend in `backend/app/`, SQLAlchemy models, Alembic migrations, Argon2 passwords, database-checked JWT authorization, and private evidence storage.
- SQLite is the local persistent default (`backend/instance/amrin.db`). `DATABASE_URL` selects another SQLAlchemy database; PostgreSQL requires its driver and a configured deployment database.
- `mock-server/server.py` is the independent in-memory frontend demo and is not the persistent API.
- The optional ML ingestion endpoint records external detections. The service does not perform inference or send railway control commands. `/api/model/status` remains false for model-loaded/inference-active until a future authenticated health-report mechanism exists.

## Database tables

`users`, `alerts`, `alert_history`, `devices`, `sensor_readings`, `maintenance_tasks`, `task_evidence`, `tracks`, `trains`, `decision_states`, `event_log`, and `ml_origin_events`. Alembic currently includes the core schema migration and a partial unique index preventing two open maintenance tasks for one alert. ML ingestion uses the existing `ml_origin_events` unique constraint on `(source_namespace, source_event_id)`; no inference service or image table is introduced.

## Frontend API endpoint matrix

All paths below are relative to `/api`. User endpoints use Bearer JWTs and role checks described in backend docs. The ML integration uses the separate machine token.

| Frontend API helper(s) | Method and backend route | Access/notes |
| --- | --- | --- |
| `loginRequest`, `registerRequest`, `getCurrentUser` | `POST /auth/login`, `POST /auth/register`, `GET /auth/me` | Public login/registration; `/me` authenticated |
| `getAlerts`, `getAlert` | `GET /alerts`, `GET /alerts/{alert_id}` | Authenticated; worker visibility is city/assignment scoped |
| `acknowledgeAlert`, `resolveAlert`, `markFalsePositive`, `assignAlert`, `changeAlertPriority` | `POST /alerts/{alert_id}/acknowledge`, `/resolve`, `/false-positive`, `/assign`, `/priority` | Admin; lifecycle checked and audited |
| `getAlertHistory` | `GET /alerts/{alert_id}/history` | Authenticated and visibility checked |
| `getDevices`, `getDeviceSensors`, `getDeviceDiagnostics` | `GET /devices`, `GET /devices/{device_id}/sensors`, `GET /devices/{device_id}/diagnostics` | Admin |
| `getTasks`, `createTask`, `updateTaskStatus` | `GET /tasks`, `POST /tasks`, `PUT /tasks/{task_id}/status` | Admin lists/creates; worker sees/updates own assigned tasks |
| `uploadTaskEvidence`, `getTaskEvidenceImage` | `POST /tasks/{task_id}/evidence`, `GET /tasks/{task_id}/evidence/{evidence_id}` | Admin/assigned worker; MIME, signature, size, and ownership checked |
| `getWorkers`, `getPendingUsers`, `approveUser`, `rejectUser` | `GET /workers`, `GET /users/pending`, `POST /users/{user_id}/approve`, `POST /users/{user_id}/reject` | Admin |
| `getTracks`, `getTrains` | `GET /tracks`, `GET /trains` | Authenticated map users; worker data city-scoped |
| `getSwitchStatus` | `GET /switch/status` | Authenticated; advisory state only |
| `getDashboardSummary`, `getDashboardEventLog` | `GET /dashboard/summary`, `GET /dashboard/event-log` | Admin |
| `getModelStatus`, `getAIDetection` | `GET /model/status`, `GET /ai/detection` | Admin; honest no-live-model response until connected |
| External ML producer (not browser helper) | `POST /integrations/ml/events` | `X-ML-API-Key`; configured `ML_INGEST_TOKEN`; see ML contract |

Map filter controls are hidden until the filtered alert list contains records. City quick-jump buttons remain available and update the map in place.

`GET /health` is a backend-only readiness check (no corresponding frontend helper); it verifies database schema connectivity and returns `503` without exposing connection details if migrations/schema are unavailable. `POST /switch/decision` is used by the simulation/controller integration, not the browser API helper; it requires admin JWT authorization and only records simulation output.

## Windows setup

See the root README for a two-terminal walkthrough. Backend command sequence from `backend/`:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Set a private JWT_SECRET_KEY in backend\.env; optionally set ML_INGEST_TOKEN.
alembic upgrade head
python -m app.cli create-admin
python -m app.cli seed-demo
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend commands from the repository root:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Set VITE_API_BASE_URL=http://localhost:8000/api and VITE_DEMO_AUTH=false.
npm install
npm run dev
```

Use environment variable names only in shared configuration guidance. Backend-only names: `ENVIRONMENT`, `JWT_SECRET_KEY`, `JWT_ACCESS_TOKEN_MINUTES`, `ML_INGEST_TOKEN`, `DATABASE_URL`, `CORS_ORIGINS`, `UPLOAD_FOLDER`, and `MAX_CONTENT_LENGTH`. Frontend variables are documented in root `.env.example`; ML/JWT secrets must never be exposed as `VITE_` variables.

## Test and build evidence

Commands run for this handoff:

- `npm test -- --run` — 10 tests passed (2 files).
- `npm run build` — production build succeeded.
- `backend`: `.\.venv\Scripts\python.exe -m pytest -q` — 24 tests passed; one upstream Starlette/httpx deprecation warning.
- `backend`: `.\.venv\Scripts\python.exe -m pytest tests\test_ml_ingest.py -q` — 4 ML ingestion tests passed.
- Fresh temporary SQLite database: `alembic upgrade head` succeeded, `python -m app.cli seed-demo` inserted 19 records, second seed inserted 0, and record counts were unchanged. The temporary database was removed.
- `git diff --check` — clean for the committed implementation phases.

Tests cover authentication/approval, role authorization, CORS, malformed JSON, missing database behavior, alert/task lifecycle and ownership, evidence and upload limits, telemetry, seed idempotency, ML token validation, malformed/range-invalid events, duplicate events, image URL/base64 rejection, and transactional rollback on a simulated write failure.

## Security and operational notes

- `.env` and `.env.*` are ignored except `.env.example`; backend virtualenvs, local SQLite database files, uploads/evidence, build output, Python caches, and test coverage output are ignored.
- Never print, commit, or move secrets to the frontend. Create administrator credentials locally through the hidden-password CLI prompt.
- To reset local demo data safely, stop Uvicorn and back up first. Remove only `backend/instance/amrin.db` and its SQLite journal files. Re-run migrations, create the first admin, and optionally seed. Evidence under `UPLOAD_FOLDER` is separate and remains until manually removed.
- ML consumers should use HTTPS, set a separate high-entropy `ML_INGEST_TOKEN`, register the device first, and retry with the same source/device/event ID. The API stores source/model evidence and produces one alert per unique producer event. It rejects arbitrary image URLs and does not accept base64 image blobs.

## Known limitations and remaining manual steps

- Real deployment still needs a reachable backend, private production configuration, database provisioning, TLS, and a real first administrator. The frontend cannot connect to an API that is not running.
- No actual ML inference, model-health reporting, image ingest for ML, or railway hardware control is implemented.
- The demo seed is explicitly source-tagged `demo`; it is intentionally not edited by the redesign and should only be used for local development.
- Responsive browser review covered the map at 360×844, the Alerts page and simulator at 390×844, and the map at 1440×900. No horizontal overflow appeared at those widths; the standalone simulator loaded without a backend. A full workflow click-through against a running isolated backend was not completed; repeat that check against the target deployment before release.
