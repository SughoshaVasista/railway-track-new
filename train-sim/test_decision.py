import unittest
from datetime import datetime

from decision import MIN_SAFE_DISTANCE, decide
from scenario import SCENARIOS


class DecisionTests(unittest.TestCase):
    def test_clear_clear_maintains_a(self):
        result = decide(0.0, SCENARIOS["clear_clear"], "express-7", "switch-1")
        self.assertEqual((result["action"], result["target_track"]), ("MAINTAIN", "Track A"))
        self.assertEqual((result["train_id"], result["switch_id"]), ("express-7", "switch-1"))
        datetime.fromisoformat(result["timestamp"].replace("Z", "+00:00"))
        self.assertEqual(len(result["rules_checked"]), 4)

    def test_s3_on_a_switches_b(self):
        result = decide(10.0, SCENARIOS["s3_on_A"])
        self.assertEqual((result["action"], result["target_track"]), ("SWITCH", "Track B"))
        self.assertEqual(len(result["rules_checked"]), 4)
        self.assertIn("A", result["raw_scores"])

    def test_occupied_b_keeps_s2_on_a_with_warning(self):
        result = decide(20.0, SCENARIOS["s2_on_A_B_occupied"])
        self.assertEqual((result["action"], result["target_track"]), ("MAINTAIN", "Track A"))
        self.assertEqual(result["action_level"], "WARNING")
        self.assertIn("S2", result["reason"])
        self.assertLess(result["confidence"], 0.99)

    def test_both_s3_emergency_stops(self):
        result = decide(30.0, SCENARIOS["both_s3"])
        self.assertEqual(result["action"], "EMERGENCY_STOP")
        self.assertEqual(result["action_level"], "EMERGENCY")
        self.assertIsNone(result["target_track"])

    def test_too_close_blocks_both_tracks(self):
        result = decide(40.0, SCENARIOS["too_close"])
        self.assertEqual(result["action"], "EMERGENCY_STOP")
        self.assertFalse(result["rules_checked"][3]["passed"])
        self.assertEqual(MIN_SAFE_DISTANCE, 25.0)


if __name__ == "__main__":
    unittest.main()
