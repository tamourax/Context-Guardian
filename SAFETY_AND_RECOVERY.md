# Safety and Recovery

**Status:** V1 requirements  
**Rule:** No destructive context operation without a recovery path.

## 1. Protected state

The runtime MUST NOT automatically archive, summarize, overwrite, or discard:

- `LOCKED` or `CRITICAL` items;
- explicit hard constraints or current requirements;
- active task objectives;
- unresolved security or compliance issues;
- API contracts marked as protected;
- any item with an unresolved conflict or unknown provenance when the operation could lose it.

Protection is deterministic. A classifier may recommend protection, but it cannot silently downgrade a user-set protection level.

## 2. Risk classes and authorization

| Operation | Default mode | Required control |
|---|---|---|
| Read status, list, retrieve | Observe | No confirmation |
| Create a new checkpoint | Observe | No overwrite; report ID |
| Add protection | Observe | No confirmation |
| Remove protection | Assist | Explicit confirmation and journal |
| Archive or summarize | Assist | Preview, confirmation, verified snapshot |
| Discard | Disabled in V1 | Future opt-in policy, retention, backup, explicit confirmation |
| Invoke provider compaction | Disabled in V1 | Agent-native controls and user confirmation |
| Inject recovered context | Assist | Preview exact package and confirm |

No mode may bypass the protection rules. Auto mode remains disabled until separate release criteria are approved.

## 3. Context transactions and recovery

Before applying a transformation, create a transaction containing:

- transaction ID and request ID;
- source item IDs and source checkpoint;
- immutable snapshot of affected Guardian-managed records;
- exact planned actions and policy version;
- before-state hashes and recovery location;
- approval actor and timestamp when approval is required.

The runtime must verify snapshot readability before mutation. After mutation it verifies the resulting state and records the outcome. If verification fails, it attempts rollback and reports both the original failure and rollback result.

Rollback restores Guardian-managed records and metadata. It does not reverse a provider's compaction or restore a private transcript that the provider never exposed. In that case recovery means creating a sourced package that the agent can re-read or the user can paste back.

## 4. Journal and corruption handling

- The operation journal is append-only during normal use.
- Checkpoints are immutable; edits create a new version with a parent reference.
- A write uses temporary data, validation, then atomic replacement where the platform supports it.
- Detect corrupt or mismatched hashes before using a snapshot.
- On storage corruption, stop mutations, preserve files for diagnosis, and offer the latest verified recovery point.
- A failed rollback is a high-severity error; do not continue with further mutations.

## 5. Privacy and local-first boundary

- Guardian MUST NOT upload project context to a Guardian cloud service in V1.
- Agent providers may receive context under their own service behavior and user settings. Guardian must not promise that all context stays on the device.
- Store project data in an isolated local directory and expose retention controls.
- Do not persist full prompts, full tool output, or source files unless needed and explicitly configured.
- Redact recognized credentials from diagnostics. Never copy secrets into checkpoints as a default behavior.
- The V1 credential filter rejects several common key/token formats before persistence, but it is heuristic and is not a complete secret scanner.
- Telemetry is off by default. If later added, it must be opt-in and must not include source code or raw conversation content.

## 6. Conflicts and authority

The current explicit user instruction takes precedence for the current task. Current repository evidence may supersede older implementation notes, but it cannot override a current user requirement. If two current authoritative sources conflict, mark both, show source and date, and ask the user. Do not delete the losing record; mark it superseded only after the conflict is resolved.

## 7. Failure-closed behavior

When the runtime, adapter, or recovery store is unavailable:

- continue the user's coding task where possible;
- do not claim a successful checkpoint, integrity check, or recovery;
- do not perform cleanup or compaction;
- mark the operation unsupported or failed;
- provide the user with the manual recovery information that is actually available.

Safety state and protection metadata must be checked again immediately before every mutation to prevent stale plans from bypassing newer protection.
