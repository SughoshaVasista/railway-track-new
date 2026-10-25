from __future__ import annotations

import json
import sys
from decision import decide

SCENARIOS = {
    "clear_clear": {"track_A_defect": None, "track_A_occupied": False, "track_B_defect": None, "track_B_occupied": False, "switch_A_available": True, "switch_B_available": True, "distance_to_switch": 100},
    "s3_on_A": {"track_A_defect": "S3", "track_A_occupied": False, "track_B_defect": None, "track_B_occupied": False, "switch_A_available": True, "switch_B_available": True, "distance_to_switch": 100},
    "s2_on_A_B_occupied": {"track_A_defect": "S2", "track_A_occupied": False, "track_B_defect": None, "track_B_occupied": True, "switch_A_available": True, "switch_B_available": True, "distance_to_switch": 100},
    "both_s3": {"track_A_defect": "S3", "track_A_occupied": False, "track_B_defect": "S3", "track_B_occupied": False, "switch_A_available": True, "switch_B_available": True, "distance_to_switch": 100},
    "too_close": {"track_A_defect": None, "track_A_occupied": False, "track_B_defect": None, "track_B_occupied": False, "switch_A_available": True, "switch_B_available": True, "distance_to_switch": 10},
}

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "clear_clear"
    if name not in SCENARIOS:
        raise SystemExit(f"Unknown scenario: {name}. Choose from {', '.join(SCENARIOS)}")
    print(json.dumps(decide(0.0, SCENARIOS[name]), indent=2, allow_nan=False))
