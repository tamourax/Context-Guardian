"""Claude Code capability probe and real hook-event normalization.

This module never fabricates lifecycle events. It recognizes only payloads
received on stdin from an actual Claude Code hook invocation.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .protocol import GuardianError

RECOGNIZED_HOOK_EVENTS = {"PreCompact", "SessionStart"}


def normalize_hook(raw: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        raise GuardianError("INVALID_INPUT", "Claude hook input must be a JSON object.")
    provider_event = raw.get("hook_event_name")
    session_id = raw.get("session_id")
    if not isinstance(provider_event, str) or not isinstance(session_id, str):
        raise GuardianError("INVALID_INPUT", "Claude hook input is missing hook_event_name or session_id.")
    if provider_event == "PreCompact":
        return {
            "name": "compaction.pre",
            "payload": {
                "provider_event": "PreCompact",
                "session_id": session_id,
                "trigger": raw.get("trigger", "unknown"),
                "state_package_available": False,
                "observed_or_inferred": "observed",
            },
        }
    if provider_event == "SessionStart":
        start_source = raw.get("source", "unknown")
        if start_source == "compact":
            return {
                "name": "compaction.post",
                "payload": {
                    "provider_event": "SessionStart",
                    "session_start_source": "compact",
                    "session_id": session_id,
                    "state_package_available": False,
                    "integrity_status": "unverified",
                    "observed_or_inferred": "observed",
                },
            }
        return {
            "name": "session.started",
            "payload": {
                "provider_event": "SessionStart",
                "session_start_source": start_source,
                "session_id": session_id,
                "observed_or_inferred": "observed",
            },
        }
    return None


def _hook_event_names(settings_path: Path) -> tuple[list[str], list[str], list[str], str]:
    if not settings_path.is_file():
        return [], [], [], "not_found"
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], [], [], "invalid"
    hooks = data.get("hooks") if isinstance(data, dict) else None
    if not isinstance(hooks, dict):
        return [], [], [], "no_hooks"
    names = sorted(str(name) for name in hooks.keys())
    compact_session_start = False
    guardian_events = []
    session_start = hooks.get("SessionStart")
    for event_name in ("PreCompact", "SessionStart"):
        groups = hooks.get(event_name)
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            if event_name == "SessionStart" and group.get("matcher") in (None, "", "compact"):
                compact_session_start = True
            handlers = group.get("hooks", [])
            if isinstance(handlers, list) and any(
                isinstance(handler, dict) and handler.get("type") == "command"
                and re.search(r"(?:^|[\s/\\])cg(?:\.exe)?\s+adapter\s+hook\s+claude-code(?:\s|$)", str(handler.get("command", "")))
                for handler in handlers
            ):
                guardian_events.append("PreCompact" if event_name == "PreCompact" else "SessionStart(compact)")
    configured = []
    if isinstance(hooks.get("PreCompact"), list) and hooks.get("PreCompact"):
        configured.append("PreCompact")
    if compact_session_start:
        configured.append("SessionStart(compact)")
    return names, configured, guardian_events, "valid"


def _version(executable: str | None) -> tuple[str | None, str | None]:
    if not executable:
        return None, None
    try:
        completed = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None, "version_probe_failed"
    value = (completed.stdout or completed.stderr).strip().splitlines()
    return (value[0] if value and completed.returncode == 0 else None), (None if completed.returncode == 0 else "version_probe_failed")


def capability_report(project_root: Path, store: Any | None = None) -> dict[str, Any]:
    executable = shutil.which("claude")
    version, version_error = _version(executable)
    settings = [
        project_root / ".claude" / "settings.json",
        project_root / ".claude" / "settings.local.json",
        Path.home() / ".claude" / "settings.json",
    ]
    discovered_settings = []
    all_event_names: set[str] = set()
    configured_events: set[str] = set()
    guardian_events: set[str] = set()
    invalid_settings = []
    for path in settings:
        names, configured, guardian, status = _hook_event_names(path)
        if status != "not_found":
            discovered_settings.append({"path": str(path), "status": status})
            all_event_names.update(names)
            configured_events.update(configured)
            guardian_events.update(guardian)
            if status == "invalid":
                invalid_settings.append(str(path))
    observed = {"PreCompact": False, "SessionStart(compact)": False}
    if store is not None:
        for event in store.list_events(limit=10000):
            payload = event.get("payload") or {}
            if payload.get("provider_event") == "PreCompact":
                observed["PreCompact"] = True
            if payload.get("provider_event") == "SessionStart" and payload.get("session_start_source") == "compact":
                observed["SessionStart(compact)"] = True
    cli_present = executable is not None and version is not None
    pre_gate = "pass" if observed["PreCompact"] else "blocked_not_observed"
    post_signal_gate = "pass" if observed["SessionStart(compact)"] else "blocked_not_observed"
    return {
        "adapter_id": "claude-code",
        "adapter_version": "0.1.0",
        "agent_executable_found": executable is not None,
        "agent_version": version,
        "version_probe_error": version_error,
        "settings_files": discovered_settings,
        "agent_event_groups_present_in_settings": sorted(configured_events),
        "guardian_hook_events_configured": sorted(guardian_events),
        "other_configured_event_names": sorted(all_event_names - RECOGNIZED_HOOK_EVENTS),
        "invalid_settings_files": invalid_settings,
        "recognized_event_names": sorted(RECOGNIZED_HOOK_EVENTS),
        "observed_events": observed,
        "capabilities": {
            "pre_compaction_signal": "observed" if observed["PreCompact"] else (
                "guardian_hook_configured_not_observed" if "PreCompact" in guardian_events else (
                    "other_agent_hook_group_present" if "PreCompact" in configured_events else "not_configured"
                )
            ),
            "post_transition_signal": "observed" if observed["SessionStart(compact)"] else (
                "guardian_hook_configured_not_observed" if "SessionStart(compact)" in guardian_events else (
                    "other_agent_hook_group_present" if "SessionStart(compact)" in configured_events else "not_configured"
                )
            ),
            "post_transition_state_package": "not_provided_by_hook",
            "automatic_integrity_verification": "unsupported_without_agent_supplied_state_package",
            "context_usage": "unsupported",
            "context_injection": "unsupported_in_v1",
        },
        "release_gates": {
            "cli_detected": "pass" if cli_present else "blocked",
            "pre_compaction_event_observed": pre_gate,
            "post_transition_signal_observed": post_signal_gate,
            "post_transition_state_package_available": "blocked",
            "adapter_status": "manual_checkpoint_and_integrity_only" if cli_present else "unavailable",
            "automatic_compaction_enabled": False,
        },
        "privacy_note": "Only hook metadata is recorded. Transcript contents and paths are not read or persisted by the adapter.",
    }


def hook_settings_fragment() -> dict[str, Any]:
    """Return a mergeable sample; this does not install or alter settings."""
    command = "cg adapter hook claude-code"
    return {
        "hooks": {
            "PreCompact": [{"hooks": [{"type": "command", "command": command}]}],
            "SessionStart": [{"matcher": "compact", "hooks": [{"type": "command", "command": command}]}],
        }
    }
