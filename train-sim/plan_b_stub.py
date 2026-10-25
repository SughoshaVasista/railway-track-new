from __future__ import annotations

import argparse
import time

import requests

from decision import decide
from scenario import SCENARIOS

ENDPOINT = "http://localhost:8000/api/switch/decision"
TRAIN_ID = "train_0"
SWITCH_ID = "switch_0"


def run_simulation(track_state: dict, endpoint: str = ENDPOINT, tick_delay: float = 0.05) -> list[dict]:
    position = 0.0
    results = []
    while position < 1.0:
        position = min(1.0, round(position + 0.05, 2))
        result = decide(position, track_state, TRAIN_ID, SWITCH_ID)
        results.append(result)
        try:
            requests.post(endpoint, json=result, timeout=1).raise_for_status()
        except requests.RequestException as exc:
            print(f"[WARN] POST failed: {exc}")
        print(f"pos={position:.2f} | decision={result['action']}")
        if tick_delay:
            time.sleep(tick_delay)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", choices=SCENARIOS, default="s3_on_A", nargs="?")
    parser.add_argument("--endpoint", default=ENDPOINT)
    parser.add_argument("--no-delay", action="store_true")
    args = parser.parse_args()
    run_simulation(SCENARIOS[args.scenario], args.endpoint, 0 if args.no_delay else 0.05)
