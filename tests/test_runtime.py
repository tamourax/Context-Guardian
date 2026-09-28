from __future__ import annotations

import json
import ast
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from context_guardian.claude_adapter import capability_report, normalize_hook
from context_guardian.core import (
    add_item, apply_transaction, compare_checkpoints, create_checkpoint, create_task, plan_transaction,
    protect_item, rollback_transaction,
)
from context_guardian.protocol import GuardianError
from context_guardian.storage import Store


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root, create=True)
        self.task = create_task(self.store, "Preserve API behavior", request_id="req_task")

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def add_item(self, **changes):
        value = {"item_id": "ctx_constraint", "type": "HARD_CONSTRAINT", "content": "Keep the public API backward compatible.",
                 "protection": "NORMAL", "source": {"kind": "user_message"}}
        value.update(changes)
        return add_item(self.store, value, request_id=changes.get("request_id", "req_item"))

    def test_sqlite_storage_and_journal_initialize(self):
        self.assertTrue(self.store.db_path.is_file())
        self.assertEqual(self.store.get_meta("schema_version"), None)
        self.assertEqual(self.store.verify_journal()["status"], "pass")
        self.assertGreaterEqual(self.store.verify_journal()["checked_entries"], 1)

    def test_request_id_retry_returns_same_task(self):
        first = create_task(self.store, "One task", request_id="same-request")
        second = create_task(self.store, "One task", request_id="same-request")
        self.assertEqual(first["task_id"], second["task_id"])
        self.assertTrue(second["idempotent_replay"])
        self.assertEqual(len([t for t in self.store.list_tasks() if t["objective"] == "One task"]), 1)

    def test_request_id_cannot_be_reused_for_different_payload(self):
        create_task(self.store, "Original objective", request_id="reused-request")
        with self.assertRaises(GuardianError) as error:
            create_task(self.store, "Different objective", request_id="reused-request")
        self.assertEqual(error.exception.code, "INVALID_INPUT")

    def test_checkpoint_and_integrity(self):
        item = self.add_item()
        checkpoint = create_checkpoint(self.store, {"objective": self.task["objective"]}, request_id="req_checkpoint")
        self.assertIn(item["item_id"], checkpoint["item_refs"])
        from context_guardian.core import integrity_check
        report = integrity_check(self.store, checkpoint["checkpoint_id"], {
            "items": [item], "objective": self.task["objective"], "coverage": {"complete": True},
        })
        self.assertEqual(report["status"], "pass")

    def test_checkpoint_compare_reports_changed_fields(self):
        left = create_checkpoint(self.store, {"objective": "Preserve API", "requirements": ["Keep v1 stable"]}, request_id="req_cp_left")
        right = create_checkpoint(self.store, {"objective": "Preserve API", "requirements": ["Keep v2 stable"]}, request_id="req_cp_right")
        diff = compare_checkpoints(self.store, left["checkpoint_id"], right["checkpoint_id"])
        self.assertFalse(diff["identical"])
        self.assertEqual(diff["changed_fields"][0]["field"], "requirements")

    def test_protected_item_cannot_be_planned_for_archive(self):
        item = self.add_item(protection="CRITICAL")
        with self.assertRaises(GuardianError) as error:
            plan_transaction(self.store, {"operation": "archive", "item_ids": [item["item_id"]]}, request_id="req_plan")
        self.assertEqual(error.exception.code, "PROTECTED_ITEM")

    def test_transaction_requires_confirmation_and_rolls_back(self):
        item = self.add_item(type="TOOL_OUTPUT", content="Repeated compiler output", protection="NORMAL")
        planned = plan_transaction(self.store, {"operation": "archive", "item_ids": [item["item_id"]]}, request_id="req_archive")
        with self.assertRaises(GuardianError) as error:
            apply_transaction(self.store, planned["transaction_id"], confirmed=False)
        self.assertEqual(error.exception.code, "PERMISSION_DENIED")
        applied = apply_transaction(self.store, planned["transaction_id"], confirmed=True)
        self.assertEqual(applied["state"], "committed")
        self.assertEqual(self.store.get_item(item["item_id"])["lifecycle"], "ARCHIVED")
        snapshot = self.root / ".context-guardian" / applied["result"]["snapshot"]["path"]
        self.assertTrue(snapshot.is_file())
        rolled_back = rollback_transaction(self.store, planned["transaction_id"], confirmed=True)
        self.assertEqual(rolled_back["state"], "rolled_back")
        self.assertEqual(self.store.get_item(item["item_id"])["lifecycle"], "HOT")
        self.assertEqual(self.store.verify_journal()["status"], "pass")

    def test_rollback_refuses_to_overwrite_later_changes(self):
        item = self.add_item(type="TOOL_OUTPUT", content="Output to archive", protection="NORMAL")
        planned = plan_transaction(self.store, {"operation": "archive", "item_ids": [item["item_id"]]}, request_id="req_later_change")
        apply_transaction(self.store, planned["transaction_id"], confirmed=True)
        changed = self.store.get_item(item["item_id"])
        changed["content"] = "Edited after transaction"
        with self.store.atomic():
            self.store.save_item(changed)
        with self.assertRaises(GuardianError) as error:
            rollback_transaction(self.store, planned["transaction_id"], confirmed=True)
        self.assertEqual(error.exception.code, "STATE_CHANGED")

    def test_apply_rejects_expired_or_changed_plan(self):
        item = self.add_item(type="TOOL_OUTPUT", content="Old output", protection="NORMAL")
        expired = plan_transaction(self.store, {"operation": "archive", "item_ids": [item["item_id"]]}, request_id="req_expired")
        self.store.conn.execute("UPDATE transactions SET expires_at='2000-01-01T00:00:00Z' WHERE transaction_id=?", (expired["transaction_id"],))
        with self.assertRaises(GuardianError) as error:
            apply_transaction(self.store, expired["transaction_id"], confirmed=True)
        self.assertEqual(error.exception.code, "PLAN_EXPIRED")

        fresh = plan_transaction(self.store, {"operation": "archive", "item_ids": [item["item_id"]]}, request_id="req_changed_plan")
        changed = self.store.get_item(item["item_id"])
        changed["content"] = "New output after preview"
        with self.store.atomic():
            self.store.save_item(changed)
        with self.assertRaises(GuardianError) as error:
            apply_transaction(self.store, fresh["transaction_id"], confirmed=True)
        self.assertEqual(error.exception.code, "STATE_CHANGED")

    def test_summarize_requires_caller_text_and_archives_sources_reversibly(self):
        item = self.add_item(type="DEBUGGING_ATTEMPT", content="Old hypothesis failed", protection="NORMAL")
        with self.assertRaises(GuardianError):
            plan_transaction(self.store, {"operation": "summarize", "item_ids": [item["item_id"]]}, request_id="req_empty_summary")
        planned = plan_transaction(self.store, {"operation": "summarize", "item_ids": [item["item_id"]],
                                                "summary": "Hypothesis was ruled out."}, request_id="req_summary")
        result = apply_transaction(self.store, planned["transaction_id"], confirmed=True)
        summary = self.store.get_item(result["result"]["created_item_ids"][0])
        self.assertEqual(summary["content"], "Hypothesis was ruled out.")
        self.assertEqual(self.store.get_item(item["item_id"])["lifecycle"], "ARCHIVED")
        rollback_transaction(self.store, planned["transaction_id"], confirmed=True)
        self.assertEqual(self.store.get_item(item["item_id"])["lifecycle"], "HOT")

    def test_claude_spike_never_claims_unobserved_or_automatic_compaction(self):
        report = capability_report(self.root)
        self.assertFalse(report["observed_events"]["PreCompact"])
        self.assertFalse(report["observed_events"]["SessionStart(compact)"])
        self.assertFalse(report["release_gates"]["automatic_compaction_enabled"])
        self.assertEqual(report["capabilities"]["post_transition_state_package"], "not_provided_by_hook")

    def test_existing_agent_hook_is_not_mistaken_for_guardian_hook(self):
        settings_dir = self.root / ".claude"
        settings_dir.mkdir()
        (settings_dir / "settings.json").write_text(json.dumps({
            "hooks": {"PreCompact": [{"hooks": [{"type": "command", "command": "some-other-tool"}]}]}
        }), encoding="utf-8")
        report = capability_report(self.root)
        self.assertIn("PreCompact", report["agent_event_groups_present_in_settings"])
        self.assertNotIn("PreCompact", report["guardian_hook_events_configured"])
        self.assertEqual(report["capabilities"]["pre_compaction_signal"], "other_agent_hook_group_present")

    def test_unrecognized_claude_hook_event_is_not_normalized(self):
        self.assertIsNone(normalize_hook({"hook_event_name": "UnknownFutureEvent", "session_id": "session-1"}))

    def test_runtime_has_no_network_client_dependencies(self):
        forbidden = {"socket", "http", "urllib", "requests", "aiohttp", "httpx"}
        source_root = Path(__file__).resolve().parents[1] / "src" / "context_guardian"
        imported = set()
        for source in source_root.glob("*.py"):
            tree = ast.parse(source.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
        self.assertFalse(forbidden & imported, f"Unexpected network client imports: {forbidden & imported}")


if __name__ == "__main__":
    unittest.main()
