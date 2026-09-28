from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from context_guardian.codex_adapter import capability_report, hook_settings_fragment, normalize_hook
from context_guardian.core import create_task, handle_codex_hook
from context_guardian.protocol import GuardianError
from context_guardian.storage import Store


class CodexAdapterTests(unittest.TestCase):
    def test_normalizes_documented_compaction_events_without_state_package(self):
        before = normalize_hook({
            "hook_event_name": "PreCompact", "session_id": "session-1",
            "turn_id": "turn-1", "trigger": "auto", "transcript_path": "private.jsonl",
        })
        after = normalize_hook({
            "hook_event_name": "PostCompact", "session_id": "session-1",
            "turn_id": "turn-1", "trigger": "auto",
        })

        self.assertEqual(before["name"], "compaction.pre")
        self.assertEqual(after["name"], "compaction.post")
        self.assertFalse(after["payload"]["state_package_available"])
        self.assertEqual(after["payload"]["integrity_status"], "unverified")
        self.assertNotIn("transcript_path", before["payload"])

    def test_session_start_is_observed_but_unknown_lifecycle_is_ignored(self):
        start = normalize_hook({
            "hook_event_name": "SessionStart", "session_id": "session-2", "source": "resume",
        })
        unsupported = normalize_hook({
            "hook_event_name": "UserPromptSubmit", "session_id": "session-2", "prompt": "secret",
        })

        self.assertEqual(start["name"], "session.started")
        self.assertEqual(start["payload"]["session_start_source"], "resume")
        self.assertIsNone(unsupported)

    def test_rejects_malformed_hook_input(self):
        with self.assertRaises(GuardianError):
            normalize_hook({"hook_event_name": "PreCompact"})

    def test_pre_compact_hook_persists_event_and_guardian_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with Store(root, create=True) as store:
                task = create_task(store, "Keep the compatibility contract", request_id="task-1")
                result = handle_codex_hook(store, {
                    "hook_event_name": "PreCompact", "session_id": "test-session",
                    "turn_id": "test-turn", "trigger": "manual",
                })
                events = store.list_events(name="compaction.pre")

            self.assertEqual(result["status"], "recorded")
            self.assertIsNotNone(result["checkpoint_id"])
            self.assertEqual(events[0]["source"], "codex-cli")
            self.assertEqual(task["objective"], "Keep the compatibility contract")

    def test_project_capabilities_separate_configuration_from_observation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            hooks_path = root / ".codex" / "hooks.json"
            hooks_path.parent.mkdir()
            hooks_path.write_text(json.dumps(hook_settings_fragment()), encoding="utf-8")
            with patch("context_guardian.codex_adapter.shutil.which", return_value="codex"), \
                 patch("context_guardian.codex_adapter._version", return_value=("codex-cli 0.151.0", None)), \
                 patch("context_guardian.codex_adapter._hooks_feature", return_value="enabled"):
                report = capability_report(root)

        self.assertEqual(report["release_gates"]["project_hooks_configured"], "pass")
        self.assertEqual(report["release_gates"]["pre_compaction_observed"], "blocked_not_observed")
        self.assertEqual(report["release_gates"]["post_compaction_state_package_available"], "blocked")
        self.assertFalse(report["release_gates"]["guardian_automatic_compaction_enabled"])


if __name__ == "__main__":
    unittest.main()
