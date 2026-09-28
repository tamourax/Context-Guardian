"""JSON-first command-line interface for Context Guardian."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION, __version__
from .claude_adapter import capability_report as claude_capability_report, hook_settings_fragment as claude_hook_settings_fragment
from .codex_adapter import capability_report as codex_capability_report, hook_settings_fragment as codex_hook_settings_fragment
from .core import (
    add_item, apply_transaction, create_checkpoint, create_task, current_task,
    compare_checkpoints, discover_project, handle_claude_hook, handle_codex_hook, initialize_project, integrity_check,
    plan_transaction, protect_item, retrieve, rollback_transaction, status_report,
    switch_task,
)
from .protocol import GuardianError, PRESSURE_WEIGHTS, canonical_json, pressure_report
from .storage import Store

MAX_STDIN_BYTES = 2 * 1024 * 1024


def _project_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="Project directory (default: current directory)")


def _request_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--request-id", help="Stable request ID for retry-safe mutations")


def _format_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=["json"], default="json", help="Output format (V1: json)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cg", description="Local-first coding-agent context runtime")
    parser.add_argument("--version", action="version", version=f"Context Guardian {__version__} (protocol {PROTOCOL_VERSION})")
    commands = parser.add_subparsers(dest="command", required=True)

    init_p = commands.add_parser("init", help="Initialize local project storage")
    _project_arg(init_p); _request_arg(init_p); _format_arg(init_p)

    doctor_p = commands.add_parser("doctor", help="Check runtime and adapter capabilities")
    _project_arg(doctor_p); _format_arg(doctor_p)

    status_p = commands.add_parser("status", help="Show project and context status")
    _project_arg(status_p); _format_arg(status_p)

    pressure_p = commands.add_parser("pressure", help="Calculate deterministic context pressure")
    _project_arg(pressure_p); _format_arg(pressure_p)
    pressure_p.add_argument("--used-tokens", type=int)
    pressure_p.add_argument("--total-tokens", type=int)
    pressure_p.add_argument("--upcoming-tokens", type=int)

    task_p = commands.add_parser("task", help="Create, inspect, and switch task state")
    task_commands = task_p.add_subparsers(dest="task_command", required=True)
    task_create = task_commands.add_parser("create", help="Create and activate a task")
    _project_arg(task_create); _request_arg(task_create); _format_arg(task_create)
    task_create.add_argument("--objective", required=True)
    task_current = task_commands.add_parser("current", help="Show the current task")
    _project_arg(task_current); _format_arg(task_current)
    task_list = task_commands.add_parser("list", help="List tasks")
    _project_arg(task_list); _format_arg(task_list)
    task_switch = task_commands.add_parser("switch", help="Switch current task")
    _project_arg(task_switch); _request_arg(task_switch); _format_arg(task_switch)
    task_switch.add_argument("task_id")

    item_p = commands.add_parser("item", help="Manage structured context items")
    item_commands = item_p.add_subparsers(dest="item_command", required=True)
    item_add = item_commands.add_parser("add", help="Add a context item from JSON stdin")
    _project_arg(item_add); _request_arg(item_add); _format_arg(item_add)
    item_add.add_argument("--input", choices=["-"], required=True)
    item_list = item_commands.add_parser("list", help="List context items")
    _project_arg(item_list); _format_arg(item_list)
    item_list.add_argument("--task")
    item_list.add_argument("--include-archived", action="store_true")
    item_show = item_commands.add_parser("show", help="Show a context item")
    _project_arg(item_show); _format_arg(item_show); item_show.add_argument("item_id")

    checkpoint_p = commands.add_parser("checkpoint", help="Create and inspect checkpoints")
    checkpoint_commands = checkpoint_p.add_subparsers(dest="checkpoint_command", required=True)
    checkpoint_create = checkpoint_commands.add_parser("create", help="Create a structured checkpoint from JSON stdin")
    _project_arg(checkpoint_create); _request_arg(checkpoint_create); _format_arg(checkpoint_create)
    checkpoint_create.add_argument("--input", choices=["-"], required=True)
    checkpoint_list = checkpoint_commands.add_parser("list", help="List checkpoints")
    _project_arg(checkpoint_list); _format_arg(checkpoint_list); checkpoint_list.add_argument("--task")
    checkpoint_show = checkpoint_commands.add_parser("show", help="Show a checkpoint")
    _project_arg(checkpoint_show); _format_arg(checkpoint_show); checkpoint_show.add_argument("checkpoint_id")
    checkpoint_compare = checkpoint_commands.add_parser("compare", help="Compare two immutable checkpoints")
    _project_arg(checkpoint_compare); _format_arg(checkpoint_compare)
    checkpoint_compare.add_argument("left_checkpoint_id"); checkpoint_compare.add_argument("right_checkpoint_id")

    retrieve_p = commands.add_parser("retrieve", help="Search relevant stored context")
    _project_arg(retrieve_p); _format_arg(retrieve_p)
    retrieve_p.add_argument("--query", required=True); retrieve_p.add_argument("--task"); retrieve_p.add_argument("--limit", type=int, default=10)

    integrity_p = commands.add_parser("integrity", help="Verify a current-state package against a checkpoint")
    integrity_commands = integrity_p.add_subparsers(dest="integrity_command", required=True)
    integrity_verify = integrity_commands.add_parser("verify", help="Compare current state with a checkpoint")
    _project_arg(integrity_verify); _request_arg(integrity_verify); _format_arg(integrity_verify)
    integrity_verify.add_argument("--checkpoint", required=True); integrity_verify.add_argument("--input", choices=["-"], required=True)

    protect_p = commands.add_parser("protect", help="Change protection for a context item")
    protect_commands = protect_p.add_subparsers(dest="protect_command", required=True)
    protect_add = protect_commands.add_parser("add", help="Set a protection level")
    _project_arg(protect_add); _request_arg(protect_add); _format_arg(protect_add)
    protect_add.add_argument("--item", required=True); protect_add.add_argument("--level", required=True,
        choices=["LOCKED", "CRITICAL", "IMPORTANT", "NORMAL", "DISCARDABLE"])
    protect_remove = protect_commands.add_parser("remove", help="Return an item to NORMAL protection")
    _project_arg(protect_remove); _request_arg(protect_remove); _format_arg(protect_remove)
    protect_remove.add_argument("--item", required=True); protect_remove.add_argument("--confirm", action="store_true")

    transaction_p = commands.add_parser("transaction", help="Plan, apply, inspect, or roll back a context transaction")
    transaction_commands = transaction_p.add_subparsers(dest="transaction_command", required=True)
    tx_plan = transaction_commands.add_parser("plan", help="Plan a reversible archive or summarize transaction")
    _project_arg(tx_plan); _request_arg(tx_plan); _format_arg(tx_plan); tx_plan.add_argument("--input", choices=["-"], required=True)
    tx_apply = transaction_commands.add_parser("apply", help="Apply a previously previewed plan")
    _project_arg(tx_apply); _format_arg(tx_apply); tx_apply.add_argument("--plan", required=True); tx_apply.add_argument("--confirm", action="store_true")
    tx_rollback = transaction_commands.add_parser("rollback", help="Restore Guardian-managed state from a verified snapshot")
    _project_arg(tx_rollback); _format_arg(tx_rollback); tx_rollback.add_argument("transaction_id"); tx_rollback.add_argument("--confirm", action="store_true")
    tx_show = transaction_commands.add_parser("show", help="Show transaction state")
    _project_arg(tx_show); _format_arg(tx_show); tx_show.add_argument("transaction_id")

    journal_p = commands.add_parser("journal", help="Inspect and verify the operation journal")
    journal_commands = journal_p.add_subparsers(dest="journal_command", required=True)
    journal_verify = journal_commands.add_parser("verify", help="Verify the append-only journal hash chain")
    _project_arg(journal_verify); _format_arg(journal_verify)
    journal_list = journal_commands.add_parser("list", help="List recent journal entries")
    _project_arg(journal_list); _format_arg(journal_list); journal_list.add_argument("--limit", type=int, default=50)

    adapter_p = commands.add_parser("adapter", help="Inspect or receive agent adapter events")
    adapter_commands = adapter_p.add_subparsers(dest="adapter_command", required=True)
    adapter_doctor = adapter_commands.add_parser("doctor", help="Run an agent adapter capability probe")
    _project_arg(adapter_doctor); _format_arg(adapter_doctor); adapter_doctor.add_argument("agent", choices=["claude-code", "codex"])
    adapter_config = adapter_commands.add_parser("config", help="Print a non-installing project-local hook settings fragment")
    _project_arg(adapter_config); _format_arg(adapter_config); adapter_config.add_argument("agent", choices=["claude-code", "codex"])
    adapter_hook = adapter_commands.add_parser("hook", help="Receive an actual hook payload on stdin")
    _project_arg(adapter_hook); adapter_hook.add_argument("agent", choices=["claude-code", "codex"])

    return parser


def _read_stdin_json(args: argparse.Namespace, expected_command: str) -> dict[str, Any]:
    raw = sys.stdin.read(MAX_STDIN_BYTES + 1)
    if len(raw.encode("utf-8")) > MAX_STDIN_BYTES:
        raise GuardianError("INVALID_INPUT", "JSON input exceeds the 2 MiB limit.")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GuardianError("INVALID_INPUT", f"Invalid JSON on stdin at line {exc.lineno}, column {exc.colno}.") from exc
    if not isinstance(value, dict) or value.get("protocol_version") != PROTOCOL_VERSION:
        raise GuardianError("SCHEMA_VERSION_UNSUPPORTED", "JSON input must use the protocol envelope with protocol_version 1.0.")
    request_id = value.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip():
        raise GuardianError("INVALID_INPUT", "Protocol request_id must be a non-empty string.")
    if value.get("command") != expected_command:
        raise GuardianError("INVALID_INPUT", f"Protocol command must be {expected_command}.")
    if getattr(args, "request_id", None) and args.request_id != request_id:
        raise GuardianError("INVALID_INPUT", "CLI --request-id does not match the input envelope request_id.")
    if hasattr(args, "request_id"):
        args.request_id = request_id
    payload = value.get("payload")
    if not isinstance(payload, dict):
        raise GuardianError("INVALID_INPUT", "Protocol payload must be a JSON object.")
    return payload


def _envelope(data: Any, *, request_id: str | None = None, status: str = "ok", warnings: list[str] | None = None) -> dict[str, Any]:
    return {"protocol_version": PROTOCOL_VERSION, "request_id": request_id or f"req_{uuid.uuid4().hex}",
            "status": status, "data": data, "warnings": warnings or [], "error": None}


def _store(project: Path) -> Store:
    return Store(discover_project(project))


def _doctor(project: Path) -> dict[str, Any]:
    root = discover_project(project)
    data: dict[str, Any] = {"runtime_version": __version__, "protocol_version": PROTOCOL_VERSION,
                            "python_version": sys.version.split()[0], "sqlite_version": sqlite3.sqlite_version,
                            "project_root": str(root), "initialized": False,
                            "guardian_cloud_upload": False}
    store = None
    try:
        store = Store(root)
    except GuardianError as exc:
        if exc.code != "NOT_INITIALIZED":
            raise
    if store:
        try:
            data["initialized"] = True
            data["project_id"] = store.get_meta("project_id")
            data["database_quick_check"] = store.conn.execute("PRAGMA quick_check").fetchone()[0]
            data["journal"] = store.verify_journal()
            data["mode"] = store.get_meta("mode", "observe")
            data["adapter"] = codex_capability_report(root, store)
        finally:
            store.close()
    else:
        data["adapter"] = codex_capability_report(root)
    return data


def _dispatch(args: argparse.Namespace) -> tuple[dict[str, Any] | None, int]:
    command = args.command
    if command == "init":
        data = initialize_project(args.project)
        return _envelope(data, request_id=args.request_id), 0
    if command == "doctor":
        return _envelope(_doctor(args.project)), 0
    if command == "adapter" and args.adapter_command == "doctor":
        root = discover_project(args.project)
        store = None
        try:
            store = Store(root)
        except GuardianError as exc:
            if exc.code != "NOT_INITIALIZED":
                raise
        try:
            reporter = codex_capability_report if args.agent == "codex" else claude_capability_report
            data = reporter(root, store)
        finally:
            if store:
                store.close()
        return _envelope(data), 0
    if command == "adapter" and args.adapter_command == "config":
        fragment = codex_hook_settings_fragment() if args.agent == "codex" else claude_hook_settings_fragment()
        return _envelope({"settings_fragment": fragment, "installed": False,
                          "instruction": "Review and merge manually. This command does not modify agent settings."}), 0
    if command == "adapter" and args.adapter_command == "hook":
        try:
            payload = _read_stdin_json()
            root = discover_project(args.project)
            with Store(root) as store:
                handler = handle_codex_hook if args.agent == "codex" else handle_claude_hook
                handler(store, payload)
        except GuardianError as exc:
            if exc.code == "NOT_INITIALIZED":
                print("Context Guardian is not initialized; hook event was not persisted.", file=sys.stderr)
            else:
                print(f"Context Guardian hook skipped ({exc.code}): {exc.message}", file=sys.stderr)
        except (OSError, sqlite3.Error) as exc:
            print(f"Context Guardian hook skipped ({type(exc).__name__}).", file=sys.stderr)
        return None, 0

    with _store(args.project) as store:
        if command == "status":
            return _envelope(status_report(store)), 0
        if command == "pressure":
            if (args.used_tokens is None) != (args.total_tokens is None):
                raise GuardianError("INVALID_INPUT", "Provide both --used-tokens and --total-tokens, or neither.")
            items = store.list_items()
            data = pressure_report(items, active_task_count=max(1, len(store.list_tasks(status="active"))),
                                   used_tokens=args.used_tokens, total_tokens=args.total_tokens,
                                   upcoming_tokens=args.upcoming_tokens)
            return _envelope(data), 0
        if command == "task":
            if args.task_command == "create":
                return _envelope(create_task(store, args.objective, request_id=args.request_id), request_id=args.request_id), 0
            if args.task_command == "current":
                task = current_task(store)
                return _envelope(task, status="ok" if task else "partial",
                                 warnings=[] if task else ["No current task is selected."]), 0
            if args.task_command == "list":
                return _envelope(store.list_tasks()), 0
            return _envelope(switch_task(store, args.task_id, request_id=args.request_id), request_id=args.request_id), 0
        if command == "item":
            if args.item_command == "add":
                item = add_item(store, _read_stdin_json(args, "item.add"), request_id=args.request_id)
                return _envelope(item, request_id=args.request_id), 0
            if args.item_command == "list":
                return _envelope(store.list_items(task_id=args.task, include_archived=args.include_archived)), 0
            item = store.get_item(args.item_id)
            if item is None:
                raise GuardianError("INVALID_INPUT", f"Unknown context item: {args.item_id}.")
            return _envelope(item), 0
        if command == "checkpoint":
            if args.checkpoint_command == "create":
                checkpoint = create_checkpoint(store, _read_stdin_json(args, "checkpoint.create"), request_id=args.request_id)
                return _envelope(checkpoint, request_id=args.request_id), 0
            if args.checkpoint_command == "list":
                return _envelope(store.list_checkpoints(task_id=args.task)), 0
            if args.checkpoint_command == "compare":
                return _envelope(compare_checkpoints(store, args.left_checkpoint_id, args.right_checkpoint_id)), 0
            checkpoint = store.get_checkpoint(args.checkpoint_id)
            if checkpoint is None:
                raise GuardianError("INVALID_INPUT", f"Unknown checkpoint: {args.checkpoint_id}.")
            return _envelope(checkpoint), 0
        if command == "retrieve":
            return _envelope(retrieve(store, args.query, task_id=args.task, limit=args.limit)), 0
        if command == "integrity":
            report = integrity_check(store, args.checkpoint, _read_stdin_json(args, "integrity.verify"))
            return _envelope(report, request_id=args.request_id), 0
        if command == "protect":
            if args.protect_command == "remove" and not args.confirm:
                raise GuardianError("PERMISSION_DENIED", "Removing protection requires the explicit --confirm flag.")
            level = args.level if args.protect_command == "add" else None
            return _envelope(protect_item(store, args.item, level, request_id=args.request_id), request_id=args.request_id), 0
        if command == "transaction":
            if args.transaction_command == "plan":
                return _envelope(plan_transaction(store, _read_stdin_json(args, "transaction.plan"), request_id=args.request_id), request_id=args.request_id), 0
            if args.transaction_command == "apply":
                result = apply_transaction(store, args.plan, confirmed=args.confirm)
                return _envelope(result), 0
            if args.transaction_command == "rollback":
                result = rollback_transaction(store, args.transaction_id, confirmed=args.confirm)
                return _envelope(result), 0
            transaction = store.get_transaction(args.transaction_id)
            if transaction is None:
                raise GuardianError("INVALID_INPUT", f"Unknown transaction: {args.transaction_id}.")
            return _envelope(transaction), 0
        if command == "journal":
            if args.journal_command == "verify":
                report = store.verify_journal()
                return _envelope(report), (0 if report["status"] == "pass" else 2)
            return _envelope(store.journal_entries(limit=max(1, min(args.limit, 1000)))), 0
    raise GuardianError("INVALID_INPUT", "Unsupported command.")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    envelope_input = (
        args.command == "item" and getattr(args, "item_command", None) == "add"
        or args.command == "checkpoint" and getattr(args, "checkpoint_command", None) == "create"
        or args.command == "integrity" and getattr(args, "integrity_command", None) == "verify"
        or args.command == "transaction" and getattr(args, "transaction_command", None) == "plan"
    )
    if hasattr(args, "request_id") and args.request_id is None and not envelope_input:
        args.request_id = f"req_{uuid.uuid4().hex}"
    try:
        result, exit_code = _dispatch(args)
    except GuardianError as exc:
        if args.command == "adapter" and getattr(args, "adapter_command", None) == "hook":
            print(f"Context Guardian hook skipped ({exc.code}): {exc.message}", file=sys.stderr)
            return 0
        envelope = {"protocol_version": PROTOCOL_VERSION, "request_id": getattr(args, "request_id", None) or f"req_{uuid.uuid4().hex}",
                    "status": "error", "data": None,
                    "warnings": [], "error": {"code": exc.code, "message": exc.message, "details": exc.details}}
        print(canonical_json(envelope))
        return 2
    except (sqlite3.Error, OSError) as exc:
        if args.command == "adapter" and getattr(args, "adapter_command", None) == "hook":
            print(f"Context Guardian hook skipped ({type(exc).__name__}).", file=sys.stderr)
            return 0
        envelope = {"protocol_version": PROTOCOL_VERSION, "request_id": f"req_{uuid.uuid4().hex}",
                    "status": "error", "data": None, "warnings": [],
                    "error": {"code": "STORAGE_CORRUPT", "message": str(exc), "details": None}}
        print(canonical_json(envelope))
        return 2
    if result is not None:
        print(canonical_json(result))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
