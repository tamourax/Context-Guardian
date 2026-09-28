"""V1 runtime operations built on the protocol and SQLite store."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from . import PROTOCOL_VERSION, __version__
from .protocol import (
    GuardianError, assert_no_secrets, canonical_json, integrity_report, new_id, normalize_item,
    pressure_report, sha256_text, utc_now,
)
from .storage import Store


def discover_project(path: Path) -> Path:
    resolved = Path(path).expanduser().resolve()
    for candidate in (resolved, *resolved.parents):
        if (candidate / ".context-guardian" / "guardian.sqlite3").is_file():
            return candidate
    return resolved


def initialize_project(path: Path) -> dict[str, Any]:
    root = Path(path).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    with Store(root, create=True) as store:
        return {
            "project_id": store.get_meta("project_id"),
            "project_root": str(root),
            "database": str(store.db_path),
            "schema_version": 1,
            "mode": store.get_meta("mode", "observe"),
        }


def _default_request_id(request_id: str | None) -> str:
    return request_id or new_id("req")


def _already_done(store: Store, request_id: str, command: str, request_payload: Any) -> dict[str, Any] | None:
    previous = store.get_request(request_id)
    if previous is not None:
        expected_hash = sha256_text(canonical_json({"command": command, "payload": request_payload}))
        if previous["command"] != command or previous["request_hash"] != expected_hash:
            raise GuardianError("INVALID_INPUT", "request_id was already used for a different command or payload.")
        result = dict(previous["result"])
        result["idempotent_replay"] = True
        return result
    if store.get_transaction_by_request(request_id) is not None:
        raise GuardianError("INVALID_INPUT", "request_id was already used for a transaction plan.")
    return None


def create_task(store: Store, objective: str, *, request_id: str | None = None, make_current: bool = True) -> dict[str, Any]:
    if not isinstance(objective, str) or not objective.strip():
        raise GuardianError("INVALID_INPUT", "Task objective must be a non-empty string.")
    assert_no_secrets(objective)
    req = _default_request_id(request_id)
    with store.atomic():
        request_payload = {"objective": objective.strip(), "make_current": make_current}
        previous = _already_done(store, req, "task.create", request_payload)
        if previous is not None:
            return previous
        now = utc_now()
        task = {"task_id": new_id("task"), "objective": objective.strip(), "status": "active",
                "created_at": now, "updated_at": now}
        store.save_task(task)
        if make_current:
            store.set_meta("current_task_id", task["task_id"])
        store.append_journal(None, "task.created", {"task_id": task["task_id"], "request_id": req})
        store.remember_request(req, "task.create", task, request_payload)
        return task


def switch_task(store: Store, task_id: str, *, request_id: str | None = None) -> dict[str, Any]:
    req = _default_request_id(request_id)
    with store.atomic():
        request_payload = {"task_id": task_id}
        previous = _already_done(store, req, "task.switch", request_payload)
        if previous is not None:
            return previous
        task = store.get_task(task_id)
        if task is None:
            raise GuardianError("INVALID_INPUT", f"Unknown task: {task_id}.")
        old = store.get_meta("current_task_id")
        store.set_meta("current_task_id", task_id)
        task["updated_at"] = utc_now()
        store.save_task(task)
        store.append_journal(None, "task.switched", {"from": old, "to": task_id, "request_id": req})
        result = {"current_task_id": task_id, "objective": task["objective"]}
        store.remember_request(req, "task.switch", result, request_payload)
        return result


def current_task(store: Store) -> dict[str, Any] | None:
    task_id = store.get_meta("current_task_id")
    return store.get_task(task_id) if task_id else None


def add_item(store: Store, raw: dict[str, Any], *, request_id: str | None = None) -> dict[str, Any]:
    req = _default_request_id(request_id)
    with store.atomic():
        previous = _already_done(store, req, "item.add", raw)
        if previous is not None:
            return previous
        task = current_task(store)
        item = normalize_item(raw, task_id=raw.get("task_id") or (task["task_id"] if task else None))
        if item.get("task_id") and store.get_task(item["task_id"]) is None:
            raise GuardianError("INVALID_INPUT", f"Unknown task: {item['task_id']}.")
        existing = store.get_item(item["item_id"])
        if existing and existing != item:
            raise GuardianError("STATE_CHANGED", f"Context item ID already exists with different content: {item['item_id']}.")
        store.save_item(item)
        store.append_journal(None, "context_item.created", {"item_id": item["item_id"], "task_id": item.get("task_id"), "request_id": req})
        store.remember_request(req, "item.add", item, raw)
        return item


def create_checkpoint(store: Store, payload: dict[str, Any], *, request_id: str | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise GuardianError("INVALID_INPUT", "Checkpoint input must be a JSON object.")
    assert_no_secrets(payload)
    req = _default_request_id(request_id)
    with store.atomic():
        previous = _already_done(store, req, "checkpoint.create", payload)
        if previous is not None:
            return previous
        task_id = payload.get("task_id")
        task = store.get_task(task_id) if task_id else current_task(store)
        if task_id and task is None:
            raise GuardianError("INVALID_INPUT", f"Unknown task: {task_id}.")
        objective = payload.get("objective") or (task.get("objective") if task else None)
        if task is None:
            if not objective:
                raise GuardianError("INVALID_INPUT", "Create a task or provide an objective before checkpointing.")
            now = utc_now()
            task = {"task_id": new_id("task"), "objective": str(objective), "status": "active", "created_at": now, "updated_at": now}
            store.save_task(task)
            store.set_meta("current_task_id", task["task_id"])
        if task is None or (task_id and store.get_task(task_id) is None):
            raise GuardianError("INVALID_INPUT", f"Unknown task: {task_id}.")
        task_id = task["task_id"]
        supplied_items = payload.get("items", [])
        if not isinstance(supplied_items, list):
            raise GuardianError("INVALID_INPUT", "Checkpoint items must be an array.")
        for raw_item in supplied_items:
            item = normalize_item(raw_item, task_id=task_id)
            if item.get("task_id") != task_id:
                raise GuardianError("INVALID_INPUT", "Checkpoint items must belong to the checkpoint task.")
            if store.get_task(item["task_id"]) is None:
                raise GuardianError("INVALID_INPUT", f"Unknown task: {item['task_id']}.")
            existing = store.get_item(item["item_id"])
            if existing is not None and existing != item:
                raise GuardianError("STATE_CHANGED", f"Checkpoint input cannot overwrite an existing context item: {item['item_id']}.")
            if existing is None:
                store.save_item(item)
        all_items = store.list_items(task_id=task_id, include_archived=True)
        now = utc_now()
        prior = store.list_checkpoints(task_id=task_id)
        parent_checkpoint_id = payload.get("parent_checkpoint_id") or (prior[0]["checkpoint_id"] if prior else None)
        if parent_checkpoint_id and store.get_checkpoint(parent_checkpoint_id) is None:
            raise GuardianError("INVALID_INPUT", f"Unknown parent checkpoint: {parent_checkpoint_id}.")
        checkpoint = {
            "checkpoint_id": payload.get("checkpoint_id") or new_id("ckpt"),
            "project_id": store.get_meta("project_id"),
            "task_id": task_id,
            "branch_id": payload.get("branch_id"),
            "created_at": now,
            "parent_checkpoint_id": parent_checkpoint_id,
            "protocol_version": PROTOCOL_VERSION,
            "policy_version": store.get_meta("policy_version", "v1.0"),
            "objective": str(objective),
            "scope": payload.get("scope", ""),
            "requirements": payload.get("requirements", []),
            "protected_constraints": payload.get("protected_constraints", []),
            "decisions": payload.get("decisions", []),
            "active_files": payload.get("active_files", []),
            "active_symbols": payload.get("active_symbols", []),
            "implementation_state": payload.get("implementation_state", ""),
            "completed_work": payload.get("completed_work", []),
            "unresolved_issues": payload.get("unresolved_issues", []),
            "open_questions": payload.get("open_questions", []),
            "tests": payload.get("tests", []),
            "blockers": payload.get("blockers", []),
            "current_branch": payload.get("current_branch"),
            "dependencies": payload.get("dependencies", []),
            "next_actions": payload.get("next_actions", []),
            "items": all_items,
            "item_refs": [item["item_id"] for item in all_items],
        }
        if not isinstance(checkpoint["requirements"], list) or not isinstance(checkpoint["protected_constraints"], list):
            raise GuardianError("INVALID_INPUT", "requirements and protected_constraints must be arrays.")
        for list_field in ("decisions", "active_files", "active_symbols", "completed_work", "unresolved_issues",
                           "open_questions", "tests", "blockers", "dependencies", "next_actions"):
            if not isinstance(checkpoint[list_field], list):
                raise GuardianError("INVALID_INPUT", f"{list_field} must be an array.")
        store.save_checkpoint(checkpoint)
        store.append_journal(None, "checkpoint.created", {"checkpoint_id": checkpoint["checkpoint_id"], "task_id": task_id, "request_id": req})
        store.remember_request(req, "checkpoint.create", checkpoint, payload)
        return checkpoint


def status_report(store: Store, *, used_tokens: int | None = None, total_tokens: int | None = None,
                  upcoming_tokens: int | None = None) -> dict[str, Any]:
    task = current_task(store)
    items = store.list_items(task_id=task["task_id"] if task else None)
    active_tasks = store.list_tasks(status="active")
    pressure = pressure_report(items, active_task_count=max(1, len(active_tasks)), used_tokens=used_tokens,
                               total_tokens=total_tokens, upcoming_tokens=upcoming_tokens)
    return {
        "project_id": store.get_meta("project_id"),
        "project_root": str(store.project_root),
        "mode": store.get_meta("mode", "observe"),
        "current_task": task,
        "active_task_count": len(active_tasks),
        "context_item_count": len(items),
        "protected_item_count": sum(1 for item in items if item.get("protection") in {"LOCKED", "CRITICAL", "IMPORTANT"}),
        "pressure": pressure,
        "journal": store.verify_journal(),
    }


def retrieve(store: Store, query: str, *, task_id: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
    terms = [term for term in re.findall(r"[\w.-]+", query.casefold()) if len(term) > 1]
    if not terms:
        return []
    items = store.list_items(task_id=task_id, include_archived=True)
    scored = []
    for item in items:
        content = str(item.get("content", "")).casefold()
        matches = sum(1 for term in terms if term in content)
        if not matches:
            continue
        lifecycle_bonus = {"HOT": 1.0, "WARM": 0.75, "COLD": 0.5, "ARCHIVED": 0.25}.get(item.get("lifecycle"), 0.25)
        protection_bonus = {"LOCKED": 0.2, "CRITICAL": 0.15, "IMPORTANT": 0.1}.get(item.get("protection"), 0.0)
        score = matches / len(set(terms)) + lifecycle_bonus * 0.1 + protection_bonus
        scored.append((score, item))
    scored.sort(key=lambda pair: (-pair[0], pair[1].get("created_at", ""), pair[1]["item_id"]))
    return [{**item, "retrieval_score": round(score, 4)} for score, item in scored[:max(1, min(limit, 100))]]


def protect_item(store: Store, item_id: str, level: str | None, *, request_id: str | None = None) -> dict[str, Any]:
    req = _default_request_id(request_id)
    with store.atomic():
        request_payload = {"item_id": item_id, "level": level.upper() if level else "NORMAL"}
        previous = _already_done(store, req, "protect.change", request_payload)
        if previous is not None:
            return previous
        item = store.get_item(item_id)
        if item is None:
            raise GuardianError("INVALID_INPUT", f"Unknown context item: {item_id}.")
        old = item["protection"]
        if level is not None:
            level = level.upper()
            if level not in {"LOCKED", "CRITICAL", "IMPORTANT", "NORMAL", "DISCARDABLE"}:
                raise GuardianError("INVALID_INPUT", f"Unsupported protection level: {level}.")
            item["protection"] = level
        else:
            item["protection"] = "NORMAL"
        store.save_item(item)
        result = {"item_id": item_id, "old_level": old, "protection": item["protection"]}
        store.append_journal(None, "context_item.protection_changed", {**result, "request_id": req})
        store.remember_request(req, "protect.change", result, request_payload)
        return result


def _item_fingerprint(item: dict[str, Any]) -> str:
    return sha256_text(canonical_json(item))


def plan_transaction(store: Store, payload: dict[str, Any], *, request_id: str | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise GuardianError("INVALID_INPUT", "Transaction plan must be a JSON object.")
    assert_no_secrets(payload)
    req = _default_request_id(request_id)
    previous_result = _already_done(store, req, "transaction.plan", payload)
    if previous_result is not None:
        return previous_result
    operation = str(payload.get("operation", "")).lower()
    if operation not in {"archive", "summarize"}:
        raise GuardianError("CAPABILITY_UNAVAILABLE", "V1 supports reversible archive and caller-supplied summarize transactions only; discard and provider compaction are disabled.")
    item_ids = payload.get("item_ids")
    if not isinstance(item_ids, list) or not item_ids or any(not isinstance(item_id, str) for item_id in item_ids):
        raise GuardianError("INVALID_INPUT", "item_ids must be a non-empty array of item IDs.")
    unique_ids = list(dict.fromkeys(item_ids))
    items = []
    for item_id in unique_ids:
        item = store.get_item(item_id)
        if item is None:
            raise GuardianError("INVALID_INPUT", f"Unknown context item: {item_id}.")
        if item["lifecycle"] == "ARCHIVED":
            raise GuardianError("STATE_CHANGED", f"Context item is already archived: {item_id}.")
        if item["protection"] in {"LOCKED", "CRITICAL", "IMPORTANT"}:
            raise GuardianError("PROTECTED_ITEM", f"Protected item cannot be transformed: {item_id}.")
        items.append(item)
    summary = payload.get("summary")
    if operation == "summarize" and (not isinstance(summary, str) or not summary.strip()):
        raise GuardianError("INVALID_INPUT", "Summarize transactions require caller-supplied summary text; Guardian does not generate summaries in V1.")
    summary_type = str(payload.get("summary_type", "IMPLEMENTATION_STATE")).upper()
    tx_id = new_id("tx")
    now = datetime.now(timezone.utc)
    plan = {
        "operation": operation,
        "item_ids": unique_ids,
        "item_fingerprints": {item["item_id"]: _item_fingerprint(item) for item in items},
        "summary": summary.strip() if isinstance(summary, str) else None,
        "summary_type": summary_type,
        "preview": {"affected_items": [{"item_id": item["item_id"], "type": item["type"], "protection": item["protection"]} for item in items],
                    "action": "archive" if operation == "archive" else "archive sources and create a caller-supplied summary"},
        "created_at": now.isoformat().replace("+00:00", "Z"),
        "policy_version": store.get_meta("policy_version", "v1.0"),
    }
    if summary_type not in {"IMPLEMENTATION_STATE", "COMPLETED_TASK", "ARCHITECTURE", "DECISION"}:
        raise GuardianError("INVALID_INPUT", "summary_type must be IMPLEMENTATION_STATE, COMPLETED_TASK, ARCHITECTURE, or DECISION.")
    transaction = {"transaction_id": tx_id, "request_id": req, "operation": operation, "state": "planned",
                   "plan": plan, "snapshot": None, "result": None,
                   "created_at": plan["created_at"], "expires_at": (now + timedelta(minutes=15)).isoformat().replace("+00:00", "Z"),
                   "updated_at": plan["created_at"], "rolled_back_by": None}
    with store.atomic():
        store.save_transaction(transaction)
        store.append_journal(tx_id, "transaction.planned", {"operation": operation, "item_ids": unique_ids, "request_id": req})
        result = {"transaction_id": tx_id, "state": "planned", "expires_at": transaction["expires_at"], "plan": plan}
        store.remember_request(req, "transaction.plan", result, payload)
    return result


def _read_verified_snapshot(store: Store, reference: dict[str, Any]) -> dict[str, Any]:
    relative = Path(str(reference.get("path", "")))
    snapshot_path = (store.data_dir / relative).resolve()
    if store.data_dir.resolve() not in snapshot_path.parents:
        raise GuardianError("RECOVERY_UNAVAILABLE", "Snapshot path is outside the Guardian data directory.")
    try:
        raw = snapshot_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GuardianError("RECOVERY_UNAVAILABLE", "Recovery snapshot is missing or unreadable.") from exc
    if sha256_text(raw) != reference.get("sha256"):
        raise GuardianError("STORAGE_CORRUPT", "Recovery snapshot hash does not match its journal reference.")
    return json.loads(raw)


def _write_verified_snapshot(store: Store, tx_id: str, content: dict[str, Any]) -> dict[str, Any]:
    snapshot_dir = store.data_dir / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    resolved_dir = snapshot_dir.resolve()
    if store.data_dir.resolve() not in resolved_dir.parents:
        raise GuardianError("RECOVERY_UNAVAILABLE", "Snapshot directory resolves outside the Guardian data directory.")
    target = snapshot_dir / f"{tx_id}.json"
    temporary = snapshot_dir / f"{tx_id}.{new_id('tmp')}.tmp"
    raw = canonical_json(content)
    with temporary.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(target)
    verified = target.read_text(encoding="utf-8")
    digest = sha256_text(verified)
    if verified != raw or json.loads(verified) != content:
        raise GuardianError("RECOVERY_UNAVAILABLE", "Recovery snapshot failed read-back verification.")
    return {"path": str(target.relative_to(store.data_dir)), "sha256": digest}


def apply_transaction(store: Store, transaction_id: str, *, confirmed: bool) -> dict[str, Any]:
    transaction = store.get_transaction(transaction_id)
    if transaction is None:
        raise GuardianError("INVALID_INPUT", f"Unknown transaction: {transaction_id}.")
    if transaction["state"] == "committed":
        return {"transaction_id": transaction_id, "state": "committed", "result": transaction["result"], "idempotent_replay": True}
    if transaction["state"] != "planned":
        raise GuardianError("STATE_CHANGED", f"Transaction is not applicable from state {transaction['state']}.")
    if not confirmed:
        raise GuardianError("PERMISSION_DENIED", "Applying a context transaction requires the explicit --confirm flag.")
    if datetime.fromisoformat(transaction["expires_at"].replace("Z", "+00:00")) < datetime.now(timezone.utc):
        raise GuardianError("PLAN_EXPIRED", "Transaction plan expired; create a new plan.")
    plan = transaction["plan"]
    items = []
    for item_id in plan["item_ids"]:
        item = store.get_item(item_id)
        if item is None or _item_fingerprint(item) != plan["item_fingerprints"][item_id]:
            raise GuardianError("STATE_CHANGED", f"Context item changed after planning: {item_id}.")
        if item["protection"] in {"LOCKED", "CRITICAL", "IMPORTANT"}:
            raise GuardianError("PROTECTED_ITEM", f"Context item became protected after planning: {item_id}.")
        items.append(item)
    snapshot_content = {"transaction_id": transaction_id, "created_at": utc_now(), "items": items, "created_item_ids": []}
    snapshot_ref = _write_verified_snapshot(store, transaction_id, snapshot_content)
    with store.atomic():
        transaction = store.get_transaction(transaction_id)
        if transaction is None or transaction["state"] != "planned":
            raise GuardianError("STATE_CHANGED", "Transaction state changed before apply.")
        fresh_items = []
        for item_id in plan["item_ids"]:
            current = store.get_item(item_id)
            if current is None or _item_fingerprint(current) != plan["item_fingerprints"][item_id]:
                raise GuardianError("STATE_CHANGED", f"Context item changed immediately before apply: {item_id}.")
            if current["protection"] in {"LOCKED", "CRITICAL", "IMPORTANT"}:
                raise GuardianError("PROTECTED_ITEM", f"Context item became protected immediately before apply: {item_id}.")
            fresh_items.append(current)
        items = fresh_items
        transaction["state"] = "applying"
        transaction["snapshot"] = snapshot_ref
        transaction["updated_at"] = utc_now()
        store.save_transaction(transaction)
        store.append_journal(transaction_id, "transaction.applying", {"snapshot": snapshot_ref})
        applied_items = []
        for item in items:
            item["lifecycle"] = "ARCHIVED"
            store.save_item(item)
            applied_items.append(item)
        created_ids = []
        if plan["operation"] == "summarize":
            summary = normalize_item({
                "type": plan["summary_type"],
                "content": plan["summary"],
                "task_id": items[0].get("task_id"),
                "source": {"kind": "guardian_transaction", "transaction_id": transaction_id,
                           "source_item_ids": plan["item_ids"]},
                "protection": "NORMAL",
                "lifecycle": "HOT",
                "supersedes": plan["item_ids"],
            }, task_id=items[0].get("task_id"))
            store.save_item(summary)
            created_ids.append(summary["item_id"])
        snapshot_content["created_item_ids"] = created_ids
        snapshot_ref = _write_verified_snapshot(store, transaction_id, snapshot_content)
        after_fingerprints = {item["item_id"]: _item_fingerprint(store.get_item(item["item_id"])) for item in applied_items}
        after_fingerprints.update({item_id: _item_fingerprint(store.get_item(item_id)) for item_id in created_ids})
        result = {"archived_item_ids": plan["item_ids"], "created_item_ids": created_ids,
                  "after_fingerprints": after_fingerprints, "snapshot": snapshot_ref, "rollback_available": True}
        transaction["state"] = "committed"
        transaction["snapshot"] = snapshot_ref
        transaction["result"] = result
        transaction["updated_at"] = utc_now()
        store.save_transaction(transaction)
        store.append_journal(transaction_id, "transaction.committed", result)
    return {"transaction_id": transaction_id, "state": "committed", "result": result}


def rollback_transaction(store: Store, transaction_id: str, *, confirmed: bool) -> dict[str, Any]:
    transaction = store.get_transaction(transaction_id)
    if transaction is None:
        raise GuardianError("INVALID_INPUT", f"Unknown transaction: {transaction_id}.")
    if transaction["state"] == "rolled_back":
        return {"transaction_id": transaction_id, "state": "rolled_back", "rollback_id": transaction["rolled_back_by"], "idempotent_replay": True}
    if transaction["state"] != "committed" or not transaction.get("snapshot"):
        raise GuardianError("RECOVERY_UNAVAILABLE", "Only committed transactions with a verified snapshot can be rolled back.")
    if not confirmed:
        raise GuardianError("PERMISSION_DENIED", "Rollback requires the explicit --confirm flag.")
    snapshot = _read_verified_snapshot(store, transaction["snapshot"])
    rollback_id = new_id("rb")
    with store.atomic():
        transaction = store.get_transaction(transaction_id)
        if transaction is None or transaction["state"] != "committed":
            raise GuardianError("STATE_CHANGED", "Transaction state changed before rollback.")
        expected_after = (transaction.get("result") or {}).get("after_fingerprints", {})
        for item_id, expected_hash in expected_after.items():
            current = store.get_item(item_id)
            if current is None or _item_fingerprint(current) != expected_hash:
                raise GuardianError("STATE_CHANGED", f"Context item changed after the transaction; refusing to overwrite it during rollback: {item_id}.")
        for item in snapshot["items"]:
            store.save_item(item)
        for item_id in snapshot.get("created_item_ids", []):
            item = store.get_item(item_id)
            if item:
                item["lifecycle"] = "ARCHIVED"
                item["source"] = {**item.get("source", {}), "rolled_back_by": rollback_id}
                store.save_item(item)
        transaction["state"] = "rolled_back"
        transaction["rolled_back_by"] = rollback_id
        transaction["updated_at"] = utc_now()
        transaction["result"] = {"rollback_id": rollback_id, "restored_item_ids": [item["item_id"] for item in snapshot["items"]],
                                  "archived_derived_item_ids": snapshot.get("created_item_ids", [])}
        store.save_transaction(transaction)
        store.append_journal(transaction_id, "transaction.rolled_back", transaction["result"])
    return {"transaction_id": transaction_id, "state": "rolled_back", **transaction["result"]}


def integrity_check(store: Store, checkpoint_id: str, current_state: dict[str, Any]) -> dict[str, Any]:
    checkpoint = store.get_checkpoint(checkpoint_id)
    if checkpoint is None:
        raise GuardianError("INVALID_INPUT", f"Unknown checkpoint: {checkpoint_id}.")
    return integrity_report(checkpoint, current_state)


def compare_checkpoints(store: Store, left_id: str, right_id: str) -> dict[str, Any]:
    left = store.get_checkpoint(left_id)
    right = store.get_checkpoint(right_id)
    if left is None:
        raise GuardianError("INVALID_INPUT", f"Unknown checkpoint: {left_id}.")
    if right is None:
        raise GuardianError("INVALID_INPUT", f"Unknown checkpoint: {right_id}.")
    fields = ("objective", "scope", "requirements", "protected_constraints", "decisions", "active_files",
              "active_symbols", "implementation_state", "completed_work", "unresolved_issues", "open_questions",
              "tests", "blockers", "current_branch", "dependencies", "next_actions")
    changes = []
    for field in fields:
        if left.get(field) != right.get(field):
            changes.append({"field": field, "left": left.get(field), "right": right.get(field)})
    left_items = {item.get("item_id"): item for item in left.get("items", [])}
    right_items = {item.get("item_id"): item for item in right.get("items", [])}
    item_changes = []
    for item_id in sorted(set(left_items) | set(right_items)):
        old, new = left_items.get(item_id), right_items.get(item_id)
        if old != new:
            item_changes.append({"item_id": item_id, "left": old, "right": new})
    return {"left_checkpoint_id": left_id, "right_checkpoint_id": right_id,
            "identical": not changes and not item_changes,
            "changed_fields": changes, "changed_items": item_changes}


def handle_claude_hook(store: Store, hook: dict[str, Any]) -> dict[str, Any]:
    from .claude_adapter import normalize_hook

    normalized = normalize_hook(hook)
    if normalized is None:
        return {"status": "ignored", "reason": "unsupported_event"}
    with store.atomic():
        event_id = store.save_event(normalized["name"], "claude-code", normalized["payload"])
    checkpoint_id = None
    if normalized["name"] == "compaction.pre":
        task = current_task(store)
        if task:
            checkpoint = create_checkpoint(store, {
                "task_id": task["task_id"],
                "objective": task["objective"],
                "scope": "Pre-compaction snapshot of Guardian-managed state.",
                "next_actions": [],
            }, request_id=new_id("req"))
            checkpoint_id = checkpoint["checkpoint_id"]
    return {"status": "recorded", "event_id": event_id, "event": normalized["name"],
            "checkpoint_id": checkpoint_id,
            "integrity_status": "unverified" if normalized["name"] == "compaction.post" else None}


def handle_codex_hook(store: Store, hook: dict[str, Any]) -> dict[str, Any]:
    from .codex_adapter import normalize_hook

    normalized = normalize_hook(hook)
    if normalized is None:
        return {"status": "ignored", "reason": "unsupported_event"}
    with store.atomic():
        event_id = store.save_event(normalized["name"], "codex-cli", normalized["payload"])
    checkpoint_id = None
    if normalized["name"] == "compaction.pre":
        task = current_task(store)
        if task:
            checkpoint = create_checkpoint(store, {
                "task_id": task["task_id"],
                "objective": task["objective"],
                "scope": "Pre-compaction snapshot of Guardian-managed state.",
                "next_actions": [],
            }, request_id=new_id("req"))
            checkpoint_id = checkpoint["checkpoint_id"]
    return {"status": "recorded", "event_id": event_id, "event": normalized["name"],
            "checkpoint_id": checkpoint_id,
            "integrity_status": "unverified" if normalized["name"] == "compaction.post" else None}
