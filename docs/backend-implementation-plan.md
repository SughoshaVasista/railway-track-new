# AMRIN backend implementation plan

## Phase 0 audit

### Stack and local commands

- Frontend: React 18, Vite 5, React Router 6, Axios, React Leaflet 4, Recharts, lucide-react, Vitest.
- Frontend development: `npm install`, then `npm run dev` (Vite on port 5173).
- Existing API demo: `python mock-server/server.py` (port 8000). It is in-memory and resets on restart; it is not a production backend.
- Frontend checks run in this audit: `npm test` passed (1 file, 5 tests); `npm run build` passed.

### Current API contract

Most list endpoints are unwrapped by `src/hooks/useData.js` from `{items: [...]}`. The frontend polls most resources every three seconds. The authenticated client sends the stored Bearer token. Routes are role-guarded in React, but that is only a UX check; the backend must enforce every permission.

| Method and path | Request | Response consumed by UI | Consumer / intended access |
|---|---|---|---|
| `POST /api/auth/login` | `{username, password}`; username field is used for email in Login | `{token, role, name, worker_id?, city?}` | Login; public |
| `POST /api/auth/register` | `{name,email,password,city,role}` | Registration result / pending state | Signup; public, always pending and never self-admin |
| `GET /api/alerts` | `severity,status,track,from,to`; UI also filters `type`, `time`, `q`, `tab` client-side; city is client-filtered | `{items:[{id,defect/type,severity,confidence,status,track,chainage,latitude,longitude,gps,sensors,image_url,city,created_at,updated_at}]}` | Dashboard, Alerts, Tasks, Map; admin, with worker access only if specifically needed by their role |
| `GET /api/alerts/<id>` | Public alert ID | Alert object | Alert detail; admin |
| `POST /api/alerts/<id>/acknowledge` | Optional JSON body (UI sends none) | Changed alert object | Alert drawer; admin |
| `POST /api/alerts/<id>/resolve` | Optional JSON body | Changed alert object | Alert drawer; admin |
| `POST /api/alerts/<id>/false-positive` | Optional JSON body | Changed alert object | Alert drawer; admin |
| `POST /api/alerts/<id>/assign` | `{worker_id}` | Changed alert object | Alert drawer; admin |
| `POST /api/alerts/<id>/priority` | `{severity:"S1"|"S2"|"S3"}` | Changed alert object with consistent severity/priority | Alert drawer; admin |
| `GET /api/alerts/<id>/history` | Public alert ID | UI expects an array; `{items:[...]}` is the preferred envelope, with timestamp/action/actor/notes/changes | Alert drawer; admin |
| `GET /api/devices` | None | `{items:[{id,name,platform,status,uptime,updated_at,city}]}` | Hardware; admin |
| `GET /api/devices/<id>/sensors` | Optional `history=true&window=24h` | Latest `{items:[{name,status,value,reading,raw,interpreted,updated_at,...}]}`; history should be bounded and preserve timestamp/value | Hardware; admin |
| `GET /api/devices/<id>/diagnostics` | None | `{device_id,status,pi_status,network_status,uptime,updated_at,checks:[{name,status}]}` | Hardware; admin |
| `GET /api/tasks` | Optional `worker_id` | `{items:[{id,alert_id,worker_id,status,priority,severity,defect,track,chainage,gps,image_url,thumbnail,sensors,notes,created_at,updated_at}]}` | Tasks / Worker; admin sees all; worker sees only assigned tasks regardless of query |
| `POST /api/tasks` | `{alert_id,worker_id,status:"ASSIGNED"}` | Created task with display fields populated from alert | Tasks; admin |
| `PUT /api/tasks/<id>/status` | `{status:"ACCEPTED"|"IN_PROGRESS"|"COMPLETED"}` | Changed task | Worker detail; assigned worker or admin; completion requires evidence |
| `POST /api/tasks/<id>/evidence` | Multipart `file` and optional `notes` | Evidence metadata and safe image URL | Worker detail; assigned worker or admin |
| `GET /api/workers` | None | `{items:[{id,worker_id,name,email,city,status}]}` | Task assignment; admin only; approved active workers |
| `GET /api/tracks` | None | `{items:[{id,name,status,occupancy,max_speed,severity,city,geometry:{type:"LineString",coordinates:[[lng,lat],...]}}]}` | Map; admin and worker |
| `GET /api/trains` | None | `{items:[{id,latitude,longitude,speed,destination,next_switch,distance,gps,city,updated_at}]}` | Map; admin and worker |
| `GET /api/switch/status` | None | `{status,action,action_level,train_id,switch_id,target_track,confidence,reason,latitude,longitude,rules_checked,raw_scores}` | Map decision panel; admin and worker; decision support only |
| `POST /api/switch/decision` | Decision JSON from `train-sim/controller.py` | Persisted/accepted decision | Controller integration; authenticated service/admin; never controls hardware |
| `GET /api/simulation/state`, `POST /api/simulation/mode` | None / `{mode}` | Compatibility state / mode | Not called by current standalone `/simulation`; optional legacy mock compatibility |
| `GET /api/dashboard/summary` | Optional city/filter params | Counts: `active_alerts,s3_alerts,s2_alerts,s1_alerts,pending_tasks,online_devices,total_devices` | Exported but current `useDashboardSummary` computes from alerts/tasks/devices; admin |
| `GET /api/dashboard/event-log` | Optional `since` | `{items:[{timestamp,action,...}],generated_at?}` | EventLog; admin |
| `GET /api/model/status` | None | Model state fields used by Hardware; truthful `loaded:false,inference_active:false` until independently reported | Hardware; admin |
| `GET /api/ai/detection` | None | Detection fields `image_url,class/defect,confidence,severity,boxes,fusion/final_confidence,timestamp`; empty response is valid | AI page; admin |

The current UI’s admin pages are `/admin`, `/alerts`, `/tasks`, `/hardware`, and `/ai-detection`. `/map` is available to admin and worker. Worker task routes are `/worker` and `/worker/:taskId`. Public routes are `/login`, `/signup`, and the local standalone `/simulation`.

### Proposed data model

- **User**: public ID, name, normalized unique email, password hash, role, approval/active status, city, optional worker ID, UTC created/updated times. Never serialize a password hash.
- **Alert**: public ID, defect/type, validated severity and lifecycle state (including legacy `ACTIVE`), confidence, track, chainage, coordinates/GPS metadata, sensor evidence JSON, safe evidence reference, city, source and optional idempotency event key, assigned worker, detected/created/updated UTC times.
- **AlertHistory**: alert FK, actor FK or service identity, action, prior/new state, details/notes JSON, UTC timestamp.
- **Device** and **SensorReading**: stable device ID and city/status/platform/diagnostics; normalized sensor name/status and timestamp plus numeric or structured reading, interpretation, and optional accelerometer/GPS fields. Index device + sensor + timestamp.
- **MaintenanceTask**: stable task ID, unique open-task constraint per alert, alert/worker FKs, lifecycle status, priority, admin notes, timestamps.
- **TaskEvidence**: task FK, randomized stored filename, MIME type, bytes, notes, uploader FK, timestamp; separate records allow before/after evidence.
- **Track**: public ID, name/status/occupancy/max speed, GeoJSON geometry, city and optional severity.
- **Train**: public ID, position, speed/destination/next switch/distance, GPS metadata, city and measurement time.
- **DecisionState**: latest advisory decision and rules/scores payload with source/time; explicitly decision-support only.
- **EventLog**: timestamped persisted operational/auth/task events for dashboard queries.
- **ML-origin event**: unique source namespace + event ID, linked alert and validated source/model metadata. No inference/model runtime in this implementation.

### Contract mismatches and risks found

1. `mock-server/server.py` is a single in-memory Flask file with public routes, plaintext `admin/admin` and `worker/worker`, no persistence, and no authorization. Its comments explicitly call it temporary/demo-only.
2. Signup calls `POST /auth/register`, absent from the mock server. The frontend can fall back to browser-local demo auth only when `VITE_DEMO_AUTH=true`; `registerDemo` permits a client-visible invite value and stores pending users in localStorage.
3. `/api/users/pending` and approve/reject are absent. `src/pages/Tasks.jsx` has no pending-user approval view in this checkout; prior localStorage approval behavior described by earlier notes is not present in current source. Backend approval must not trust browser state.
4. Mock alert actions accept any action string route, mutate only three statuses, return `{}` for unknown IDs rather than 404, and do not implement assign/priority despite frontend calls. They have no transition validation, transaction, or audit records.
5. Mock alert list only filters severity/status/track. Frontend also has type/time/search/tab and city behavior. Current `Alerts.jsx` filters most of these client-side; task/map call `useAlerts` with only their relevant filters.
6. AlertDrawer accepts `history` only when it is a raw array, while both the mock and desired bounded API contract naturally return `{items:[...]}`. It also treats action response objects as the updated alert without normalizing a nested `items`/`alert` response consistently.
7. Task creation/status/evidence in the mock are permissive and in-memory. Task action can report success for unknown IDs; no worker ownership, legal status flow, duplicate protection, file validation, persistence, or completion-evidence requirement exists. The current worker UI uploads evidence in an `IN_PROGRESS` step and then offers completion.
8. Mock sensors ignores requested device history and has no time windows; diagnostics invents ONLINE for an unknown device. Mock tracks/trains are static and have no city filtering in the server. Frontend expects GeoJSON `[longitude,latitude]` track coordinates and derives city locally from city or coordinates.
9. Mock switch decision POST merely echoes input. Simulation endpoints are not used by the active standalone simulator or current `src/services/api.js` (no helper exports for simulation mode/state); only `getSwitchStatus` is used.
10. `getDashboardSummary` is exported but unused by active hooks; the current dashboard summary is derived from alerts/tasks/devices. `getDashboardEventLog` is used by EventLog.
11. Mock model status claims a loaded model and measured inference timing; the real backend must report no model/inference until an actual integration proves otherwise. Mock AI detection returns a static demo SVG and fake-looking confidence values without a source marker.
12. API client JSON-parses persisted auth without a malformed-value guard. Evidence upload must preserve Axios multipart boundary handling. No page may treat demo-local auth or a returned mock token as backend authorization.

### Phased backend checklist and acceptance

1. **Audit (this phase)** — document exact API and model plan; run existing frontend tests/build.
2. **Backend skeleton** — Flask factory, config, extensions, CORS, errors, health route, test SQLite configuration, Windows instructions. Acceptance: isolated health test and frontend build pass.
3. **Schema/migrations/demo seed** — SQLAlchemy entities, Alembic migrations, serializers, idempotent explicitly-demo seed. Acceptance: new SQLite migration works, seed twice does not change row counts, model tests pass.
4. **Auth/accounts** — hashed passwords, JWT, pending registration, protected/admin/worker authorization, approval endpoints, safe first-admin CLI. Acceptance: test authentication and role lifecycle; no default production credentials.
5. **Alerts/tasks** — persistent filtered alerts, lifecycle + history transactions, assignment, task creation/status/ownership, safe evidence storage. Acceptance: action, transition, audit, ownership, upload, and completion guard tests.
6. **Read APIs** — devices/sensors/diagnostics/tracks/trains/switch/dashboard/model/AI. Acceptance: tested response shapes, empty states, map coordinate order, aggregate correctness, switch persistence.
7. **Frontend integration** — API helpers, auth/error handling, admin approval UI server-backed; preserve layout and standalone simulator. Acceptance: documented end-to-end workflows with demo auth off.
8. **ML ingestion boundary** — authenticated, idempotent validated event ingestion; no inference. Acceptance: duplicate, validation, authorization, upload and persistence tests.
9. **Final audit/handoff** — fresh SQLite migration/seed, backend/frontend test+build, security and Windows walkthrough, docs. Acceptance: commands and remaining manual steps documented accurately.

Recommended checks: backend `pytest`; frontend `npm test`; frontend `npm run build`. During final audit also run migrations against a new SQLite path and run the seed command twice. Exact backend command names will be documented when implemented.

### Security note and test accounts

React role guards, browser localStorage approvals, `VITE_ADMIN_INVITE`, and mock credentials are not production authentication. Users must be authenticated and authorized on every backend request. Public signup will create a pending, non-admin account; a database-backed admin approval is required. The first administrator should be created with a CLI command that prompts for a password (or accepts a protected environment input) without logging it. The current `admin/admin` and `worker/worker` values belong only to the temporary mock server and must not be reused or shipped as real-backend accounts. This audit does not create credentials. Once the authentication phase is implemented, use the interactive `create-admin` command to create your own test username/password; worker test accounts should be registered then approved through that backend.
