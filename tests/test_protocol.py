from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from context_guardian.protocol import GuardianError, integrity_report, normalize_item, pressure_report


class ProtocolTests(unittest.TestCase):
    def item(self, **changes):
        value = {"item_id": "ctx_1", "type": "HARD_CONSTRAINT", "content": "Keep the public API stable.",
                 "protection": "LOCKED", "lifecycle": "HOT", "created_at": "2026-09-28T00:00:00Z"}
        value.update(changes)
        return normalize_item(value, task_id="task_1")

    def test_item_schema_rejects_unknown_type(self):
        with self.assertRaises(GuardianError) as error:
            normalize_item({"type": "MEMORY", "content": "x"})
        self.assertEqual(error.exception.code, "INVALID_INPUT")

    def test_credential_patterns_are_rejected_but_placeholders_are_allowed(self):
        with self.assertRaises(GuardianError) as error:
            normalize_item({"type": "ASSUMPTION", "content": "api_key=not-a-real-token-1234567890abcd"})
        self.assertEqual(error.exception.code, "SENSITIVE_DATA")
        safe = normalize_item({"type": "ASSUMPTION", "content": "Read API_TOKEN from the environment."})
        self.assertEqual(safe["type"], "ASSUMPTION")

    def test_pressure_is_deterministic_and_never_authorizes_mutation(self):
        items = [self.item(), self.item(item_id="ctx_2", type="TOOL_OUTPUT", protection="NORMAL", content="Build log: done")]
        report = pressure_report(items, active_task_count=2, used_tokens=500, total_tokens=1000, upcoming_tokens=100)
        self.assertEqual(report["coverage"], 1.0)
        self.assertEqual(report["components"]["window_usage"], 50.0)
        self.assertFalse(report["automatic_action_allowed"])
        self.assertEqual(report, pressure_report(items, active_task_count=2, used_tokens=500, total_tokens=1000, upcoming_tokens=100))

    def test_pressure_rejects_invalid_window_values(self):
        with self.assertRaises(GuardianError):
            pressure_report([], used_tokens=10, total_tokens=0)

    def test_integrity_pass_and_critical_loss_gate(self):
        expected = self.item()
        checkpoint = {"items": [expected]}
        preserved = integrity_report(checkpoint, {"items": [expected], "coverage": {"complete": True}})
        self.assertEqual(preserved["status"], "pass")
        self.assertEqual(preserved["score"], 100.0)
        missing = integrity_report(checkpoint, {"items": [], "coverage": {"complete": True}})
        self.assertEqual(missing["status"], "fail")
        self.assertEqual(missing["items"][0]["state"], "missing")

    def test_integrity_does_not_assume_absence_from_partial_state(self):
        report = integrity_report({"items": [self.item()]}, {"items": [], "coverage": {"complete": False}})
        self.assertEqual(report["status"], "inconclusive")
        self.assertEqual(report["items"][0]["state"], "unverified")

    def test_empty_integrity_baseline_is_not_perfect(self):
        report = integrity_report({"items": []}, {"items": [], "coverage": {"complete": True}})
        self.assertEqual(report["status"], "not_applicable")
        self.assertIsNone(report["score"])

    def test_integrity_checks_structured_requirements_and_constraints(self):
        checkpoint = {"checkpoint_id": "cp1", "requirements": ["Keep auth behavior unchanged"],
                      "protected_constraints": ["Do not expose secrets"], "objective": "Preserve authentication behavior"}
        complete = {"requirements": ["Keep auth behavior unchanged"],
                    "protected_constraints": ["Do not expose secrets"], "objective": "Preserve authentication behavior",
                    "coverage": {"complete": True}}
        self.assertEqual(integrity_report(checkpoint, complete)["status"], "pass")
        missing = {"requirements": ["Keep auth behavior unchanged"], "protected_constraints": [],
                   "objective": "A different objective",
                   "coverage": {"complete": True}}
        report = integrity_report(checkpoint, missing)
        self.assertEqual(report["status"], "fail")
        self.assertLess(report["score"], 50.0)


if __name__ == "__main__":
    unittest.main()
