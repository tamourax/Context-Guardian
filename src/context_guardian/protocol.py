"""Protocol types and deterministic V1 scoring functions."""

from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

PROTOCOL_VERSION = "1.0"

ITEM_TYPES = {
    "GOAL", "REQUIREMENT", "HARD_CONSTRAINT", "DECISION", "ASSUMPTION",
    "ACTIVE_FILE", "ACTIVE_SYMBOL", "IMPLEMENTATION_STATE", "UNRESOLVED_ERROR",
    "RESOLVED_ERROR", "TEST_RESULT", "TOOL_OUTPUT", "DEBUGGING_ATTEMPT",
    "USER_PREFERENCE", "ARCHITECTURE", "DEPENDENCY", "OPEN_QUESTION", "TODO",
    "COMPLETED_TASK", "BRANCH_STATE", "EXTERNAL_REFERENCE", "NOISE",
}
PROTECTION_LEVELS = {"LOCKED", "CRITICAL", "IMPORTANT", "NORMAL", "DISCARDABLE"}
LIFECYCLE_STATES = {"HOT", "WARM", "COLD", "ARCHIVED"}

PRESSURE_WEIGHTS = {
    "window_usage": 30,
    "redundancy": 15,
    "staleness": 15,
    "task_fragmentation": 15,
    "tool_output_pollution": 10,
    "upcoming_operation": 10,
    "conflict_risk": 5,
}

INTEGRITY_WEIGHTS = {
    "HARD_CONSTRAINT": 5,
    "GOAL": 5,
    "REQUIREMENT": 5,
    "DECISION": 4,
    "UNRESOLVED_ERROR": 4,
    "OPEN_QUESTION": 4,
    "ACTIVE_FILE": 3,
    "ACTIVE_SYMBOL": 3,
    "IMPLEMENTATION_STATE": 3,
}

_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|client[_-]?secret)\s*[:=]\s*['\"]?([A-Za-z0-9_./+=-]{16,})", re.IGNORECASE),
)


class GuardianError(Exception):
    """An expected runtime error with a stable protocol code."""

    def __init__(self, code: str, message: str, *, details: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def assert_no_secrets(value: Any) -> None:
    """Reject common credential formats before they enter local persistence."""
    if isinstance(value, str):
        if any(pattern.search(value) for pattern in _SECRET_PATTERNS):
            raise GuardianError("SENSITIVE_DATA", "Input appears to contain a credential; remove it before saving.")
    elif isinstance(value, dict):
        for nested in value.values():
            assert_no_secrets(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            assert_no_secrets(nested)


def estimate_tokens(content: str) -> int:
    """Conservative, explicitly approximate character-based estimate."""
    return max(1, math.ceil(len(content) / 4))


def normalize_item(raw: dict[str, Any], *, task_id: str | None = None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise GuardianError("INVALID_INPUT", "A context item must be a JSON object.")
    assert_no_secrets(raw)
    item_type = str(raw.get("type", "")).upper()
    if item_type not in ITEM_TYPES:
        raise GuardianError("INVALID_INPUT", f"Unsupported context item type: {item_type or '(empty)'}.")
    content = raw.get("content")
    if not isinstance(content, str) or not content.strip():
        raise GuardianError("INVALID_INPUT", "Context item content must be a non-empty string.")
    protection = str(raw.get("protection", "NORMAL")).upper()
    lifecycle = str(raw.get("lifecycle", "HOT")).upper()
    if protection not in PROTECTION_LEVELS:
        raise GuardianError("INVALID_INPUT", f"Unsupported protection level: {protection}.")
    if lifecycle not in LIFECYCLE_STATES:
        raise GuardianError("INVALID_INPUT", f"Unsupported lifecycle state: {lifecycle}.")
    token_data = raw.get("token_estimate")
    if not isinstance(token_data, dict) or not isinstance(token_data.get("value"), (int, float)):
        token_data = {"value": estimate_tokens(content), "method": "character-estimate-4-to-1"}
    else:
        token_data = {"value": max(1, int(token_data["value"])), "method": str(token_data.get("method", "provided"))}
    now = utc_now()
    return {
        "item_id": str(raw.get("item_id") or new_id("ctx")),
        "type": item_type,
        "content": content.strip(),
        "source": raw.get("source") if isinstance(raw.get("source"), dict) else {"kind": "agent_supplied"},
        "created_at": str(raw.get("created_at") or now),
        "last_used_at": raw.get("last_used_at"),
        "confidence": _bounded_number(raw.get("confidence", 1.0), "confidence"),
        "importance": _bounded_number(raw.get("importance", 0.5), "importance"),
        "relevance": _bounded_number(raw.get("relevance", 0.5), "relevance"),
        "freshness": _bounded_number(raw.get("freshness", 1.0), "freshness"),
        "protection": protection,
        "lifecycle": lifecycle,
        "task_id": raw.get("task_id") or task_id,
        "branch_id": raw.get("branch_id"),
        "agent_id": raw.get("agent_id"),
        "file_refs": raw.get("file_refs") if isinstance(raw.get("file_refs"), list) else [],
        "symbol_refs": raw.get("symbol_refs") if isinstance(raw.get("symbol_refs"), list) else [],
        "supersedes": raw.get("supersedes") if isinstance(raw.get("supersedes"), list) else [],
        "conflicts_with": raw.get("conflicts_with") if isinstance(raw.get("conflicts_with"), list) else [],
        "token_estimate": token_data,
        "sensitivity": str(raw.get("sensitivity", "normal")),
    }


def _bounded_number(value: Any, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise GuardianError("INVALID_INPUT", f"{field} must be a number from 0 to 1.") from exc
    if not 0 <= result <= 1:
        raise GuardianError("INVALID_INPUT", f"{field} must be between 0 and 1.")
    return result


def _item_tokens(item: dict[str, Any]) -> int:
    estimate = item.get("token_estimate")
    if isinstance(estimate, dict) and isinstance(estimate.get("value"), (int, float)):
        return max(1, int(estimate["value"]))
    return estimate_tokens(str(item.get("content", "")))


def pressure_report(
    items: Iterable[dict[str, Any]],
    *,
    active_task_count: int = 1,
    used_tokens: int | None = None,
    total_tokens: int | None = None,
    upcoming_tokens: int | None = None,
    stale_after_days: int = 30,
    now: datetime | None = None,
) -> dict[str, Any]:
    if used_tokens is not None and used_tokens < 0:
        raise GuardianError("INVALID_INPUT", "used_tokens cannot be negative.")
    if total_tokens is not None and total_tokens <= 0:
        raise GuardianError("INVALID_INPUT", "total_tokens must be greater than zero.")
    if upcoming_tokens is not None and upcoming_tokens < 0:
        raise GuardianError("INVALID_INPUT", "upcoming_tokens cannot be negative.")
    rows = [item for item in items if item.get("lifecycle", "HOT") != "ARCHIVED"]
    total_item_tokens = sum(_item_tokens(item) for item in rows)
    components: dict[str, float] = {}

    if used_tokens is not None and total_tokens is not None and total_tokens > 0:
        components["window_usage"] = min(100.0, max(0.0, 100.0 * used_tokens / total_tokens))

    seen: set[str] = set()
    duplicate_tokens = 0
    for item in rows:
        text = re.sub(r"\s+", " ", str(item.get("content", ""))).strip().casefold()
        if text in seen:
            duplicate_tokens += _item_tokens(item)
        else:
            seen.add(text)
    if total_item_tokens:
        duplicate_share = duplicate_tokens / total_item_tokens
        components["redundancy"] = min(100.0, duplicate_share / 0.30 * 100.0)

    reference_time = now or datetime.now(timezone.utc)
    stale_tokens = 0
    for item in rows:
        if item.get("protection") in {"LOCKED", "CRITICAL"}:
            continue
        stamp = item.get("last_used_at") or item.get("created_at")
        try:
            parsed = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if (reference_time - parsed).total_seconds() > stale_after_days * 86400:
            stale_tokens += _item_tokens(item)
    if total_item_tokens:
        components["staleness"] = min(100.0, stale_tokens / total_item_tokens / 0.50 * 100.0)

    if active_task_count >= 1:
        components["task_fragmentation"] = min(100.0, max(0, active_task_count - 1) / 3 * 100.0)

    tool_tokens = sum(_item_tokens(item) for item in rows if item.get("type") in {"TOOL_OUTPUT", "NOISE"})
    if total_item_tokens:
        components["tool_output_pollution"] = min(100.0, tool_tokens / total_item_tokens / 0.40 * 100.0)

    if used_tokens is not None and total_tokens is not None and upcoming_tokens is not None:
        remaining = max(0, total_tokens - used_tokens)
        components["upcoming_operation"] = 100.0 if remaining == 0 and upcoming_tokens > 0 else (
            min(100.0, 100.0 * upcoming_tokens / remaining) if remaining else 0.0
        )

    conflict_pairs: set[tuple[str, str]] = set()
    for item in rows:
        for other in item.get("conflicts_with", []):
            left, right = sorted((str(item.get("item_id", "")), str(other)))
            conflict_pairs.add((left, right))
    components["conflict_risk"] = min(100.0, 25.0 * len(conflict_pairs))

    available_weight = sum(PRESSURE_WEIGHTS[name] for name in components)
    score = (
        sum(components[name] * PRESSURE_WEIGHTS[name] for name in components) / available_weight
        if available_weight else None
    )
    if score is None:
        label = "unknown"
    elif score < 40:
        label = "normal"
    elif score < 50:
        label = "review"
    elif score < 65:
        label = "propose_cleanup"
    elif score < 75:
        label = "checkpoint_and_plan"
    elif score < 90:
        label = "high_pressure"
    else:
        label = "emergency_preservation"
    return {
        "status": "ok" if available_weight >= 60 else "partial",
        "score": round(score, 2) if score is not None else None,
        "label": label,
        "coverage": round(available_weight / 100.0, 2),
        "components": {name: round(value, 2) for name, value in components.items()},
        "weights": PRESSURE_WEIGHTS,
        "policy_version": "v1.0",
        "automatic_action_allowed": False,
        "decision_note": "Pressure scores recommend review; they do not authorize a mutation in V1.",
        "uncertainty": [] if available_weight >= 60 else ["Available pressure inputs cover less than 60% of configured weight."],
    }


def _normal_content(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _integrity_weight(item_type: str) -> int:
    return INTEGRITY_WEIGHTS.get(item_type, 1)


def _structured_state_items(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Expose checkpoint sections as comparable items without inventing evidence."""
    rows = [item for item in (state.get("items") or []) if isinstance(item, dict)]
    sections = (
        ("requirements", "REQUIREMENT", "IMPORTANT"),
        ("protected_constraints", "HARD_CONSTRAINT", "LOCKED"),
        ("decisions", "DECISION", "IMPORTANT"),
        ("unresolved_issues", "UNRESOLVED_ERROR", "CRITICAL"),
        ("open_questions", "OPEN_QUESTION", "IMPORTANT"),
        ("active_files", "ACTIVE_FILE", "NORMAL"),
        ("active_symbols", "ACTIVE_SYMBOL", "NORMAL"),
        ("blockers", "UNRESOLVED_ERROR", "CRITICAL"),
        ("next_actions", "TODO", "NORMAL"),
        ("completed_work", "COMPLETED_TASK", "NORMAL"),
        ("tests", "TEST_RESULT", "NORMAL"),
        ("dependencies", "DEPENDENCY", "NORMAL"),
    )
    for field, item_type, protection in sections:
        values = state.get(field, [])
        if not isinstance(values, list):
            raise GuardianError("INVALID_INPUT", f"{field} must be an array in a state package.")
        for value in values:
            content = value if isinstance(value, str) else canonical_json(value)
            if not content.strip():
                continue
            item_id = "state_" + sha256_text(item_type + "\0" + content)[:24]
            rows.append({"item_id": item_id, "type": item_type, "content": content, "protection": protection})
    for field, item_type, protection in (
        ("objective", "GOAL", "CRITICAL"),
        ("implementation_state", "IMPLEMENTATION_STATE", "NORMAL"),
        ("current_branch", "BRANCH_STATE", "NORMAL"),
    ):
        value = state.get(field)
        if value not in (None, "", [], {}):
            content = value if isinstance(value, str) else canonical_json(value)
            item_id = "state_" + sha256_text(item_type + "\0" + content)[:24]
            rows.append({"item_id": item_id, "type": item_type, "content": content, "protection": protection})
    unique = {}
    for item in rows:
        key = (str(item.get("type", "")).upper(), _normal_content(item.get("content")))
        unique.setdefault(key, item)
    return list(unique.values())


def integrity_report(checkpoint: dict[str, Any], current_state: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(checkpoint, dict) or not isinstance(current_state, dict):
        raise GuardianError("INVALID_INPUT", "Checkpoint and current-state input must be objects.")
    expected_raw = checkpoint.get("items") or []
    observed_raw = current_state.get("items") or []
    if not isinstance(expected_raw, list) or not isinstance(observed_raw, list):
        raise GuardianError("INVALID_INPUT", "Checkpoint and current-state items must be arrays.")
    expected = _structured_state_items(checkpoint)
    observed = _structured_state_items(current_state)
    if not expected:
        return {
            "status": "not_applicable", "score": None, "coverage": 0.0,
            "items": [], "expected_weight": 0, "preserved_weight": 0,
            "policy_version": "v1.0",
        }
    by_id = {str(item.get("item_id")): item for item in observed if isinstance(item, dict) and item.get("item_id")}
    coverage_info = current_state.get("coverage") or {}
    if not isinstance(coverage_info, dict):
        raise GuardianError("INVALID_INPUT", "Current-state coverage must be an object.")
    complete = bool(coverage_info.get("complete", False))
    results = []
    expected_weight = 0
    preserved_weight = 0
    critical_problem = False
    critical_unknown = False
    for old in expected:
        if not isinstance(old, dict):
            continue
        item_id = str(old.get("item_id", ""))
        item_type = str(old.get("type", "NOISE")).upper()
        weight = _integrity_weight(item_type)
        expected_weight += weight
        found = by_id.get(item_id)
        evidence = None
        state = "unverified"
        if found is not None:
            evidence = found.get("item_id")
            if _normal_content(found.get("content")) == _normal_content(old.get("content")) and str(found.get("type", "")).upper() == item_type:
                state = "preserved"
            else:
                state = "conflicting"
        else:
            exact = next((item for item in observed if isinstance(item, dict)
                          and str(item.get("type", "")).upper() == item_type
                          and _normal_content(item.get("content")) == _normal_content(old.get("content"))), None)
            explicit_conflict = next((item for item in observed if isinstance(item, dict) and (
                item_id in item.get("conflicts_with", []) or item_id in item.get("supersedes", [])
            )), None)
            if exact is not None:
                state, evidence = "preserved", exact.get("item_id")
            elif explicit_conflict is not None:
                state, evidence = "conflicting", explicit_conflict.get("item_id")
            elif complete:
                state = "missing"
        if state == "preserved":
            preserved_weight += weight
        is_critical = weight >= 4 or old.get("protection") in {"LOCKED", "CRITICAL"}
        if is_critical and state in {"missing", "conflicting"}:
            critical_problem = True
        if is_critical and state == "unverified":
            critical_unknown = True
        results.append({
            "item_id": item_id,
            "type": item_type,
            "state": state,
            "weight": weight,
            "evidence_item_id": evidence,
        })
    score = 100.0 * preserved_weight / expected_weight if expected_weight else None
    if critical_problem:
        status = "fail"
    elif critical_unknown or any(item["state"] == "unverified" for item in results):
        status = "inconclusive"
    else:
        status = "pass"
    return {
        "status": status,
        "score": round(score, 2) if score is not None else None,
        "coverage": round(sum(1 for item in results if item["state"] != "unverified") / len(results), 2) if results else 0.0,
        "items": results,
        "expected_weight": expected_weight,
        "preserved_weight": preserved_weight,
        "policy_version": "v1.0",
    }
