from __future__ import annotations

from datetime import datetime, timezone
from math import inf

MIN_SAFE_DISTANCE = 25.0
DEFECT_SAFETY = {None: 1.0, "NONE": 1.0, "S1": 0.8, "S2": 0.4, "S3": 0.0}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _distance(state: dict, track: str) -> float:
    value = state.get(f"distance_to_switch_{track}", state.get("distance_to_switch", inf))
    try:
        return float(value)
    except (TypeError, ValueError):
        return inf


def _check_rules(track: str, state: dict) -> list[dict]:
    defect = state.get(f"track_{track}_defect") or "NONE"
    distance = _distance(state, track)
    return [
        {"rule": "Target track is not occupied", "passed": not state.get(f"track_{track}_occupied", False)},
        {"rule": "No S3 defect on target track", "passed": defect != "S3"},
        {"rule": "Switch mechanism is available", "passed": state.get(f"switch_{track}_available", True)},
        {"rule": "Train is not too close to switch", "passed": distance >= MIN_SAFE_DISTANCE},
    ]


def _score_track(track: str, state: dict) -> float:
    if not all(item["passed"] for item in _check_rules(track, state)):
        return -inf
    defect = state.get(f"track_{track}_defect") or "NONE"
    defect_safety = DEFECT_SAFETY.get(defect, 0.0)
    track_availability = 1.0 if not state.get(f"track_{track}_occupied", False) else 0.0
    distance = _distance(state, track)
    distance_safety = min(distance / MIN_SAFE_DISTANCE, 1.0) if distance != inf else 1.0
    delay_score = float(state.get("delay_score", 1.0))
    return round(0.50 * defect_safety + 0.25 * track_availability + 0.15 * distance_safety + 0.10 * delay_score, 4)


def _confidence(winner: float, loser: float) -> float:
    if loser == -inf:
        return 0.5
    return round(min(0.99, max(0.0, 0.5 + (winner - loser) / 2)), 2)


def _reason(target: str, state: dict) -> str:
    defect = state.get(f"track_{target}_defect") or "NONE"
    other = "B" if target == "A" else "A"
    parts = [f"Track {target} selected"]
    if defect != "NONE":
        parts.append(f"Track {target} has {defect} defect")
    if state.get(f"track_{other}_occupied", False):
        parts.append(f"Track {other} is occupied")
    elif state.get(f"track_{other}_defect"):
        parts.append(f"Track {other} has {state[f'track_{other}_defect']} defect")
    return ". ".join(parts) + "."


def _json_score(score: float) -> float | None:
    return None if score == -inf else score


def decide(train_position: float, state: dict, train_id: str = "train_0", switch_id: str = "switch_0") -> dict:
    score_a, score_b = _score_track("A", state), _score_track("B", state)
    rules_a = _check_rules("A", state)
    rules_b = _check_rules("B", state)
    base = {"timestamp": _timestamp(), "train_id": train_id, "switch_id": switch_id, "position": train_position, "raw_scores": {"A": _json_score(score_a), "B": _json_score(score_b)}}
    if score_a == -inf and score_b == -inf:
        return {**base, "action": "EMERGENCY_STOP", "action_level": "EMERGENCY", "target_track": None, "confidence": 0.0, "rules_checked": rules_a, "reason": "No safe track available - both blocked."}
    target, winner, loser, rules = ("A", score_a, score_b, rules_a) if score_a >= score_b else ("B", score_b, score_a, rules_b)
    defect = state.get(f"track_{target}_defect")
    return {**base, "action": "MAINTAIN" if target == "A" else "SWITCH", "action_level": "WARNING" if defect == "S2" else "NORMAL", "target_track": f"Track {target}", "confidence": _confidence(winner, loser), "rules_checked": rules, "reason": _reason(target, state)}
