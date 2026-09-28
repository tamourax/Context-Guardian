from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from context_guardian.cli import main


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, args, payload=None):
        stdout = io.StringIO()
        stderr = io.StringIO()
        stdin = io.StringIO(json.dumps(payload) if payload is not None else "")
        with redirect_stdout(stdout), redirect_stderr(stderr), patch("sys.stdin", stdin):
            code = main(args + ["--project", str(self.root)] if "--project" not in args else args)
        output = stdout.getvalue()
        return code, json.loads(output) if output.strip() else None, stderr.getvalue()

    def envelope(self, request_id, command, payload):
        return {"protocol_version": "1.0", "request_id": request_id, "command": command, "payload": payload}

    def test_cli_protocol_envelope_checkpoint_integrity_and_journal_gate(self):
        code, initialized, _ = self.run_cli(["init"])
        self.assertEqual(code, 0)
        self.assertEqual(initialized["status"], "ok")

        code, task_result, _ = self.run_cli(["task", "create", "--objective", "Keep API stable"])
        self.assertEqual(code, 0)
        task_id = task_result["data"]["task_id"]

        item = {"item_id": "ctx_api", "type": "HARD_CONSTRAINT", "content": "Keep the public API stable.",
                "task_id": task_id, "protection": "LOCKED", "source": {"kind": "user_message"}}
        code, item_result, _ = self.run_cli(["item", "add", "--input", "-"], self.envelope("req_cli_item", "item.add", item))
        self.assertEqual(code, 0)
        self.assertEqual(item_result["request_id"], "req_cli_item")

        checkpoint_payload = {"task_id": task_id, "objective": "Keep API stable"}
        code, checkpoint_result, _ = self.run_cli(
            ["checkpoint", "create", "--input", "-"],
            self.envelope("req_cli_checkpoint", "checkpoint.create", checkpoint_payload),
        )
        self.assertEqual(code, 0)
        checkpoint_id = checkpoint_result["data"]["checkpoint_id"]

        current = {"objective": "Keep API stable", "items": [item], "coverage": {"complete": True}}
        code, integrity_result, _ = self.run_cli(
            ["integrity", "verify", "--checkpoint", checkpoint_id, "--input", "-"],
            self.envelope("req_cli_integrity", "integrity.verify", current),
        )
        self.assertEqual(code, 0)
        self.assertEqual(integrity_result["status"], "ok")
        self.assertEqual(integrity_result["data"]["status"], "pass")

        output_item = {"item_id": "ctx_output", "type": "TOOL_OUTPUT", "content": "Old compiler output",
                       "task_id": task_id, "protection": "NORMAL"}
        code, _, _ = self.run_cli(["item", "add", "--input", "-"], self.envelope("req_cli_output", "item.add", output_item))
        self.assertEqual(code, 0)
        code, plan_result, _ = self.run_cli(
            ["transaction", "plan", "--input", "-"],
            self.envelope("req_cli_plan", "transaction.plan", {"operation": "archive", "item_ids": ["ctx_output"]}),
        )
        self.assertEqual(code, 0)
        transaction_id = plan_result["data"]["transaction_id"]
        code, applied, _ = self.run_cli(["transaction", "apply", "--plan", transaction_id, "--confirm"])
        self.assertEqual(code, 0)
        self.assertEqual(applied["data"]["state"], "committed")
        code, recovered, _ = self.run_cli(["transaction", "rollback", transaction_id, "--confirm"])
        self.assertEqual(code, 0)
        self.assertEqual(recovered["data"]["state"], "rolled_back")

        code, journal_result, _ = self.run_cli(["journal", "verify"])
        self.assertEqual(code, 0)
        self.assertEqual(journal_result["status"], "ok")
        self.assertEqual(journal_result["data"]["status"], "pass")

    def test_cli_rejects_payload_without_protocol_envelope(self):
        self.run_cli(["init"])
        code, response, _ = self.run_cli(["item", "add", "--input", "-"], {"type": "NOISE", "content": "x"})
        self.assertEqual(code, 2)
        self.assertEqual(response["error"]["code"], "SCHEMA_VERSION_UNSUPPORTED")


if __name__ == "__main__":
    unittest.main()
