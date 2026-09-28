# Agent Adapter Specification

**Status:** Draft V1 adapter contract  
**Reference adapter:** Codex CLI, capability spike in progress; live hook delivery remains a release gate.

## 1. Purpose

An adapter translates one agent's observable lifecycle and context data into the normalized protocol in `PROTOCOL.md`. It must not put vendor-specific assumptions in the core runtime.

## 2. Capability declaration

Every adapter exposes a machine-readable capability report:

```json
{
  "adapter_id": "claude-code",
  "adapter_version": "0.1",
  "agent_version": "unknown",
  "capabilities": {
    "session_start": "supported",
    "prompt_events": "supported|partial|unsupported",
    "tool_events": "supported|partial|unsupported",
    "file_change_events": "supported|partial|unsupported",
    "context_usage": "supported|estimated|unsupported",
    "pre_compaction": "supported|unsupported",
    "post_compaction": "supported|partial|unsupported",
    "context_injection": "supported|user_confirmed_only|unsupported"
  },
  "limitations": []
}
```

The actual report must use one enum value per capability. `cg doctor` reports the detected agent version, configured hooks, readable inputs, and missing permissions. Merely finding an agent executable is not evidence that hooks are installed or working.

## 3. Reference adapter decision

Codex CLI is the V1 reference adapter. Its official hooks documentation lists `SessionStart`, `PreCompact`, and `PostCompact`; the installed Codex CLI also reports its `hooks` feature as enabled. These facts establish documented/configured capability, not successful delivery. The project-local hooks must still be reviewed in Codex and observed from a real session before the event-driven release gate passes.

Codex's `PostCompact` payload reports lifecycle metadata such as session, turn, and trigger, but does not include the resulting context state package. Therefore the adapter can record a real post-compaction signal, but automatic integrity verification remains unsupported until an agent supplies a state package through the explicit CLI workflow. It must not read a transcript as a substitute.

The Claude Code adapter remains available as a separate earlier capability spike. OpenCode remains unimplemented.

## 4. Adapter interface

Each adapter implements:

```text
id() -> AdapterId
detect() -> DetectionResult
capabilities() -> CapabilityReport
subscribe(config) -> EventStream
normalize(raw_event) -> NormalizedEvent | UnsupportedEvent
read_context_usage() -> Measurement | Unsupported
read_current_state() -> StatePackage | Unsupported
prepare_injection(package) -> Preview
inject(package, approval) -> InjectionResult
health_check() -> HealthReport
```

`inject` is optional and unavailable in V1 automatic behavior. If provided, it must require explicit assist-mode confirmation and return a preview of the exact content to be inserted.

## 5. Event mapping requirements

Adapters map only facts they can observe. Each mapped value identifies its provenance as `observed` or `inferred`, includes the raw event reference where permissible, and marks truncation. Tool output is referenced or summarized according to policy; large output is not copied into Guardian storage by default.

For compaction:

- Before compaction, capture or request a checkpoint and expected critical-item set when a supported hook permits it.
- After compaction, collect the new state package only if supported by an explicit event or documented resume mechanism.
- Compare like-for-like data and report missing evidence as `unverified`.
- Never claim the provider's complete hidden context was inspected unless the provider exposes it.

## 6. Installation and configuration

The adapter MUST document:

- minimum agent version;
- exact hook or plugin configuration written;
- files and permissions required;
- how to disable/uninstall the integration;
- whether context snippets can be sent to the agent provider;
- recovery behavior if a hook fails or the runtime is missing.

Installation should preserve existing user configuration, write only the minimum scoped integration, and produce a diff/preview before changing agent settings. V1 defaults to project-local configuration where supported.

## 7. Capability spike exit criteria

Select a reference adapter only when all of the following are demonstrated on a clean test project:

1. Session start can be identified without reading unrelated session data.
2. A user-approved objective or task state can be captured.
3. A pre-transition checkpoint can be triggered reliably, or the limitations are accepted for manual-only compaction support.
4. A post-transition state can be supplied for meaningful integrity comparison, or automatic verification remains disabled.
5. Hook failure is observable and does not block the user's agent session.
6. Installation and removal preserve pre-existing configuration.

## 8. Adapter failure behavior

On timeout, malformed event, runtime failure, or version mismatch: continue the agent session, record a diagnostic without raw sensitive context, mark the affected capability unavailable, and do not run a mutation. A hook must have a bounded time budget and must never hold the agent indefinitely.

## 9. Claude Code capability spike (historical)

Read-only probe run on 2026-09-28 using `cg adapter doctor claude-code`:

- Claude Code CLI detected: `2.1.274`.
- An existing settings file contains a `SessionStart(compact)` event group. Its command is not Context Guardian's hook, so this is not treated as Guardian integration.
- No `PreCompact` event group was configured.
- Neither `PreCompact` nor `SessionStart(compact)` has been observed by Context Guardian.
- The recognized `SessionStart(compact)` signal does not provide a current-state package; automatic integrity verification remains unsupported without an agent-supplied package.
- Release status: manual checkpoints and manual integrity input are available; event-driven compaction verification is blocked. Automatic compaction remains disabled.
- No agent settings were written or changed during the spike.

## 10. Codex capability spike

Read-only capability probe on 2026-09-28 found Codex CLI `0.151.0` and `hooks stable true`. The official [Codex hooks documentation](https://developers.openai.com/codex/hooks/) documents all three events used by the project-local configuration in `.codex/hooks.json`.

- The project hook configuration is scoped to this workspace and does not install `SKILL.md` or edit user-level Codex settings.
- Codex requires review/trust for non-managed hooks. The project hooks are not considered active merely because the JSON file exists.
- Guardian has not yet observed actual `SessionStart`, `PreCompact`, or `PostCompact` stdin from a Codex session. These release gates remain blocked until the hooks are reviewed and invoked for real.
- `PostCompact` provides no current-state package. Post-transition integrity remains `unverified`; automatic compaction and automatic integrity verification remain disabled.
- Hook handlers persist allowlisted lifecycle metadata only. They do not read transcript content, prompts, or transcript paths.
