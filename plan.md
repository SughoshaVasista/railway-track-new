# AMRIN Railway Simulation and Frontend Integration Plan

## Goal

Extend the cloned `ShreeVidya-HS/frontend` React/Vite application with a reproducible railway-switching simulation package. The simulation will support SUMO when available, fall back to a pure-Python position loop when SUMO cannot be installed or verified within the stated time box, emit the agreed `SWITCH_DECISION` schema, POST decisions to a local Flask stub, and expose the decision data to the existing frontend UI. The implementation will preserve the frontend’s current prototype behavior while replacing hardcoded decision-rule presentation with data-driven rules where practical.

## Key decisions and assumptions

1. **Schema:** Use the brief’s recommended Option A. Every decision includes `rules_checked`, allowing the frontend to render rule names and pass/fail states dynamically.
2. **Location:** Add a self-contained `train-sim/` directory at the repository root. SUMO-generated files will live there, and the existing React app remains at the root `src/` location.
3. **Fallback:** Attempt to verify `sumo` and `netconvert` first. If unavailable, do not block delivery; implement and validate the pure-Python fallback with the same `decide()` function and JSON contract.
4. **Backend:** Use `tiny_stub.py` as the local receiver at `http://localhost:8000/api/switch/decision`. Keep the endpoint in one controller constant so it can later be replaced by the real backend URL.
5. **Frontend integration:** Add a small API/data adapter or state flow that can consume a decision payload without requiring a backend for the current demo. The existing command-center recommendation and rule rows will use the extended payload shape, with a safe fallback to existing demo data when no decision has been received.
6. **Safety behavior:** If both tracks are blocked and score infinity, return `EMERGENCY_STOP` with no target track and the specified reason. Avoid attempting a route switch in this case.

## Implementation steps

### 1. Inspect and establish the simulation workspace

- Confirm the current repository is clean before changes.
- Create `train-sim/` and a short README documenting prerequisites, commands, fallback behavior, and scenario expectations.
- Check whether `sumo` and `netconvert` are installed. If they are available, use them; otherwise continue with Plan B rather than making SUMO installation a delivery blocker.
- Keep Python code standard-library compatible except for the explicitly required runtime packages (`traci`, `requests`, and Flask for the stub).

### 2. Build the SUMO network artifacts

Create the following files in dependency order:

- `train-sim/nodes.nod.xml`: `start`, `junctionA`, `junctionB`, and `end` nodes from the brief.
- `train-sim/edges.edg.xml`: entry, Track A, Track B, and fork-B edges.
- `train-sim/network.net.xml`: generate with `netconvert` when available; verify that it exists and is non-empty. If SUMO is unavailable, document that this artifact is optional for fallback execution rather than fabricating a generated network.
- `train-sim/routes.rou.xml`: train vehicle type plus `route_A` and `route_B`.
- `train-sim/sim.sumocfg`: network, route, and simulation time configuration.

When SUMO is available, run a headless sanity check first and, where a GUI is available, document the `sumo-gui -c sim.sumocfg` command for visual verification.

### 3. Implement and test the pure decision function

Create `train-sim/decision.py` with:

- Severity scoring for S1, S2, and S3.
- Hard safety checks for target occupancy, S3 defects, and switch availability.
- Weighted scoring where a valid track is preferred by lower score.
- `rules_checked` entries containing `rule` and `passed`.
- `MAINTAIN` for Track A when it is the best safe target.
- `SWITCH` for Track B when Track B is the best safe target.
- `EMERGENCY_STOP` when neither track is safe, with reason `No safe track available — both blocked.`.
- Stable JSON-compatible output fields: `timestamp`, `train_id`, `position`, `action`, `target_track`, `confidence`, `rules_checked`, `reason`, and `raw_scores`.
- Correct handling of `None` and omitted state fields.

Add `train-sim/test_decision.py` using Python’s built-in `unittest` so the four scenarios and important edge cases can be run without SUMO or Flask.

### 4. Implement the local receiver and simulation controller

Create:

- `train-sim/tiny_stub.py`: Flask POST endpoint that validates/prints received JSON and returns a success response.
- `train-sim/controller.py`: TraCI controller that advances SUMO, reads train edge and lane position, calls `decide()`, reroutes once to `route_B` while on the entry edge when the action is `SWITCH`, and POSTs every decision with a short timeout.
- `train-sim/plan_b_stub.py`: pure-Python fallback loop that advances normalized position from 0.0 to 1.0, invokes `decide()` on every tick, and POSTs the same payload.
- `train-sim/scenario.py`: the four named scenario states and a CLI runner. It will select SUMO mode only when usable and otherwise invoke the fallback, while still allowing direct decision-only execution for fast tests.

The controller will make POST failures visible as warnings but will not crash the simulation solely because the local receiver is unavailable. It will close TraCI cleanly when SUMO is used.

### 5. Connect the decision schema to the React frontend

Update the frontend in a minimal, backward-compatible way:

- Add a decision payload model/default object in `src/` or the existing app module.
- Make the command-center recommendation panel render `target_track`, `confidence`, and `reason` from the latest decision payload.
- Map `rules_checked` dynamically into rule rows, showing pass/fail styling and labels.
- Show `EMERGENCY_STOP` distinctly and avoid presenting a recommended track in that state.
- Preserve the current prototype/demo values when no simulation payload has been loaded, so the app remains usable without a running Python process.
- Keep the current login, routing, alerts, worker, map, AI, and hardware views intact unless a small shared component change is needed.
- Add a clearly documented local development integration path, such as an optional JSON fetch or a mock adapter, without introducing a mandatory backend dependency.

### 6. Documentation and demo artifacts

Add `train-sim/README.md` covering:

- SUMO installation and verification commands.
- Python dependency installation.
- Network generation and optional GUI sanity check.
- Starting the stub and running each scenario.
- Plan B fallback usage.
- The one-line endpoint replacement for the real backend.
- Expected action and target for all four scenarios.
- Note that this is simulation/decision-support software and not live railway signalling control.

Save representative JSON outputs from the four decision-only or fallback runs under `train-sim/demo/` if practical. Do not commit large recordings or generated runtime logs. GUI screen recording remains a manual step and will be documented rather than automated.

## Verification plan

1. Run the decision unit tests and assert:
   - `clear_clear` → `MAINTAIN`, Track A.
   - `s3_on_A` → `SWITCH`, Track B.
   - `s2_on_A_B_occupied` → `MAINTAIN`, Track A.
   - `both_s3` → `EMERGENCY_STOP`, no safe target.
2. Validate every decision contains all required schema fields and three rule results.
3. Run the pure-Python fallback against the Flask stub and confirm POSTs are received for successive positions.
4. If SUMO is available, generate `network.net.xml`, run a headless simulation, confirm the train completes, and run the TraCI controller against the stub. Use `sumo-gui` for the documented visual sanity check when available.
5. Run frontend lint and production build (`npm run lint`, `npm run build`).
6. Start the Vite app and manually verify login, admin command center, dynamic rule rendering, emergency-stop presentation, worker role, and responsive navigation.
7. Check `git diff` for accidental generated files, secrets, or unrelated changes, and report any environment limitations such as unavailable SUMO GUI or missing Python packages.

## Open risks

- SUMO may not be installed in the sandbox, and GUI execution may not be possible. The fallback path is therefore a first-class, tested deliverable.
- The current frontend has no backend transport contract beyond the brief. The initial integration will use an optional/mock adapter and preserve offline behavior rather than inventing authentication or persistence.
- The requested plan mentions six build files but the detailed tree includes additional generated and stub files; the implementation will follow the detailed dependency tree and keep generated network output clearly separated from hand-authored sources.
- The real backend URL is not yet available. The controller will retain the local endpoint constant and document the single-line replacement.

## Completion criteria

The work is complete when the simulation package is present, the four scenarios produce the expected decisions, the local stub receives decision POSTs, the frontend can render the extended decision schema without a backend, and the React lint/build checks pass. SUMO-specific verification will be marked complete only if the tools are available; otherwise the fallback verification and limitation will be recorded explicitly.

## Files expected to change or be added

- `train-sim/README.md`
- `train-sim/nodes.nod.xml`
- `train-sim/edges.edg.xml`
- `train-sim/network.net.xml` (only when generated by SUMO)
- `train-sim/routes.rou.xml`
- `train-sim/sim.sumocfg`
- `train-sim/decision.py`
- `train-sim/test_decision.py`
- `train-sim/controller.py`
- `train-sim/plan_b_stub.py`
- `train-sim/scenario.py`
- `train-sim/tiny_stub.py`
- `train-sim/demo/` sample outputs as applicable
- Relevant frontend files under `src/`

Approval of this plan will begin implementation; no code or repository files other than this plan are changed during planning.
