"""Codex hook capability probe and real stdin-event normalization.

Only hook payloads received by the configured command are recorded. The
adapter never reads Codex transcripts, prompts, or transcript paths.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .protocol import GuardianError

RECOGNIZED_HOOK_EVENTS = {"SessionStart", "PreCompact", "PostCompact"}
_CODEX_HOOK_COMMAND = re.compile(r"adapter\s+hook\s+codex(?:\s|$)", re.IGNORECASE)


def normalize_hook(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize documented Codex hook stdin without inferring missing events."""
    if not isinstance(raw, dict):
        raise GuardianError("INVALID_INPUT", "Codex hook input must be a JSON object.")
    provider_event = raw.get("hook_event_name")
    session_id = raw.get("session_id")
    if not isinstance(provider_event, str) or not isinstance(session_id, str) or not session_id:
        raise GuardianError("INVALID_INPUT", "Codex hook input is missing hook_event_name or session_id.")
    if provider_event not in RECOGNIZED_HOOK_EVENTS:
        return None

    metadata: dict[str, Any] = {
        "provider_event": provider_event,
        "session_id": session_id,
        "observed_or_inferred": "observed",
        "state_package_available": False,
    }
    if provider_event in {"PreCompact", "PostCompact"}:
        metadata["trigger"] = raw.get("trigger", "unknown")
        metadata["turn_id"] = raw.get("turn_id")
        metadata["integrity_status"] = "unverified" if provider_event == "PostCompact" else None
        return {"name": "compaction.pre" if provider_event == "PreCompact" else "compaction.post",
                "payload": metadata}

    source = raw.get("source", "unknown")
    metadata["session_start_source"] = source
    if source == "compact":
        metadata["integrity_status"] = "unverified"
    return {"name": "session.started", "payload": metadata}


def _version(executable: str | None) -> tuple[str | None, str | None]:
    if not executable:
        return None, None
    try:
        completed = subprocess.run([executable, "--version"], capture_output=True,
                                   text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None, "version_probe_failed"
    value = (completed.stdout or completed.stderr).strip().splitlines()
    return (value[0] if value and completed.returncode == 0 else None,
            None if completed.returncode == 0 else "version_probe_failed")


def _hooks_feature(executable: str | None) -> str:
    if not executable:
        return "unavailable"
    try:
        completed = subprocess.run([executable, "features", "list"], capture_output=True,
                                   text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return "probe_failed"
    if completed.returncode != 0:
        return "probe_failed"
    for line in completed.stdout.splitlines():
        columns = line.split()
        if len(columns) >= 3 and columns[0] == "hooks":
            return "enabled" if columns[-1].lower() == "true" else "disabled"
    return "not_reported"


def _project_hook_config(path: Path) -> tuple[list[str], list[str], str]:
    if not path.is_file():
        return [], [], "not_found"
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], [], "invalid"
    hooks = config.get("hooks") if isinstance(config, dict) else None
    if not isinstance(hooks, dict):
        return [], [], "no_hooks"
    configured = sorted(str(name) for name, groups in hooks.items()
                        if isinstance(groups, list) and groups)
    guardian = []
    for event_name, groups in hooks.items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            handlers = group.get("hooks", [])
            if isinstance(handlers, list) and any(
                isinstance(handler, dict) and handler.get("type") == "command"
                and _CODEX_HOOK_COMMAND.search(str(handler.get("command", "")))
                for handler in handlers
            ):
                guardian.append(str(event_name))
                break
    return configured, sorted(set(guardian)), "valid"


def capability_report(project_root: Path, store: Any | None = None) -> dict[str, Any]:
    executable = shutil.which("codex")
    version, version_error = _version(executable)
    hooks_feature = _hooks_feature(executable)
    hooks_path = project_root / ".codex" / "hooks.json"
    configured, guardian_configured, config_status = _project_hook_config(hooks_path)

    observed = {"SessionStart": False, "PreCompact": False, "PostCompact": False}
    if store is not None:
        for event in store.list_events(limit=10000):
            payload = event.get("payload") or {}
            if payload.get("provider_event") in observed:
                observed[payload["provider_event"]] = True

    cli_detected = executable is not None and version is not None
    event_configured = set(guardian_configured)
    gates = {
        "cli_detected": "pass" if cli_detected else "blocked",
        "hooks_feature_enabled": "pass" if hooks_feature == "enabled" else "blocked",
        "project_hooks_configured": "pass" if {"SessionStart", "PreCompact", "PostCompact"}.issubset(event_configured) else "blocked",
        "session_start_observed": "pass" if observed["SessionStart"] else "blocked_not_observed",
        "pre_compaction_observed": "pass" if observed["PreCompact"] else "blocked_not_observed",
        "post_compaction_observed": "pass" if observed["PostCompact"] else "blocked_not_observed",
        "post_compaction_state_package_available": "blocked",
        "automatic_integrity_verification": "blocked_without_agent_supplied_state_package",
    }
    if not cli_detected:
        status = "unavailable"
    elif hooks_feature != "enabled":
        status = "manual_checkpoint_and_integrity_only"
    elif gates["project_hooks_configured"] != "pass":
        status = "hooks_supported_configuration_missing_or_incomplete"
    else:
        status = "configured_awaiting_real_hook_observation"

    return {
        "adapter_id": "codex-cli",
        "adapter_version": "0.1.0",
        "agent_executable_found": executable is not None,
        "agent_version": version,
        "version_probe_error": version_error,
        "hooks_feature": hooks_feature,
        "project_hook_settings": {"path": str(hooks_path), "status": config_status},
        "agent_event_groups_present_in_project_settings": configured,
        "guardian_hook_events_configured": guardian_configured,
        "recognized_event_names": sorted(RECOGNIZED_HOOK_EVENTS),
        "observed_events": observed,
        "capabilities": {
            "session_start": "supported" if hooks_feature == "enabled" else "unsupported_or_unavailable",
            "pre_compaction": "supported" if hooks_feature == "enabled" else "unsupported_or_unavailable",
            "post_compaction": "supported" if hooks_feature == "enabled" else "unsupported_or_unavailable",
            "post_transition_state_package": "not_provided_by_hook",
            "context_usage": "unsupported",
            "context_injection": "unsupported_in_v1",
            "hook_trust": "must_be_reviewed_in_codex",
        },
        "release_gates": {**gates, "adapter_status": status,
                           "guardian_automatic_compaction_enabled": False},
        "privacy_note": "Only allowlisted lifecycle metadata is recorded. Transcript contents, prompts, and transcript paths are not read or persisted.",
        "hooks_documentation": "https://developers.openai.com/codex/hooks/",
    }


def hook_settings_fragment() -> dict[str, Any]:
    """Return a project-local sample; this function never writes Codex settings."""
    command = "python cg.py adapter hook codex --project ."
    return {
        "description": "Context Guardian project-local lifecycle observations.",
        "hooks": {
            "SessionStart": [{"matcher": "startup|resume|clear", "hooks": [
                {"type": "command", "command": command, "timeout": 3,
                 "statusMessage": "Recording Context Guardian session start"}]}],
            "PreCompact": [{"matcher": "manual|auto", "hooks": [
                {"type": "command", "command": command, "timeout": 3,
                 "statusMessage": "Checkpointing Guardian-managed context"}]}],
            "PostCompact": [{"matcher": "manual|auto", "hooks": [
                {"type": "command", "command": command, "timeout": 3,
                 "statusMessage": "Recording Codex compaction event"}]}],
        },
    }
