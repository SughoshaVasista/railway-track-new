from __future__ import annotations

import json
import sys

import requests

from decision import decide

ENDPOINT = "http://localhost:8000/api/switch/decision"
TRAIN_ID = "train_0"
SWITCH_EDGE = "entry"
SWITCH_ID = "switch_0"


def run(scenario_state: dict) -> dict | None:
    import traci

    traci.start(["sumo", "-c", "sim.sumocfg", "--no-step-log"])
    already_switched = False
    last_decision = None
    try:
        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            if TRAIN_ID not in traci.vehicle.getIDList():
                continue
            edge = traci.vehicle.getRoadID(TRAIN_ID)
            position = traci.vehicle.getLanePosition(TRAIN_ID)
            decision = decide(position, scenario_state, TRAIN_ID, SWITCH_ID)
            last_decision = decision
            if decision["action"] == "SWITCH" and edge == SWITCH_EDGE and not already_switched:
                traci.vehicle.setRouteID(TRAIN_ID, "route_B")
                already_switched = True
                print("[SWITCH] Rerouted to Track B")
            try:
                requests.post(ENDPOINT, json=decision, timeout=1).raise_for_status()
            except requests.RequestException as exc:
                print(f"[WARN] POST failed: {exc}", file=sys.stderr)
    finally:
        traci.close()
    if last_decision:
        print("[DONE]", json.dumps(last_decision, indent=2, allow_nan=False))
    return last_decision


if __name__ == "__main__":
    from scenario import SCENARIOS

    run(SCENARIOS[sys.argv[1] if len(sys.argv) > 1 else "s3_on_A"])
