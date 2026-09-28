# Context Guardian Runtime Protocol

**Status:** Draft V1 contract  
**Normative terms:** MUST, MUST NOT, SHOULD, and MAY have their usual requirements meaning.

## 1. Protocol boundaries

The runtime owns local context records, checkpoints, policies, integrity reports, and transaction journals. An adapter translates an agent's available lifecycle data into normalized events. The runtime MUST report the difference between observed data and inferred data. It MUST NOT claim access to private agent state that the adapter did not provide.

The agent skill is a caller of this protocol. It is not the storage engine or policy engine.

## 2. Common JSON envelope

Every request and response uses UTF-8 JSON. CLI commands accept `--format json`; commands that accept structured input read one JSON document from stdin when passed `--input -`.

```json
{
  "protocol_version": "1.0",
  "request_id": "req_01...",
  "project_id": "prj_...",
  "session_id": "ses_...",
  "agent_id": "claude-code",
  "command": "checkpoint.create",
  "payload": {}
}
```

Response envelope:

```json
{
  "protocol_version": "1.0",
  "request_id": "req_01...",
  "status": "ok",
  "data": {},
  "warnings": [],
  "error": null
}
```

`status` is one of `ok`, `partial`, or `error`. Mutating requests MUST be idempotent for the same `request_id`. Timestamps use RFC 3339 UTC. Unknown fields MUST be preserved where safe or rejected with a clear schema error; they MUST NOT be silently reinterpreted.

## 3. Context item

```json
{
  "item_id": "ctx_...",
  "type": "HARD_CONSTRAINT",
  "content": "Keep the public API backward compatible.",
  "source": {"kind": "user_message", "ref": "event_..."},
  "created_at": "2026-09-28T10:00:00Z",
  "last_used_at": null,
  "confidence": 1.0,
  "importance": 1.0,
  "relevance": 1.0,
  "freshness": 1.0,
  "protection": "LOCKED",
  "lifecycle": "HOT",
  "task_id": "task_...",
  "branch_id": null,
  "agent_id": "claude-code",
  "file_refs": [],
  "symbol_refs": [],
  "supersedes": [],
  "conflicts_with": [],
  "token_estimate": {"value": 12, "method": "adapter-estimate"},
  "sensitivity": "normal"
}
```

Required item types: `GOAL`, `REQUIREMENT`, `HARD_CONSTRAINT`, `DECISION`, `ASSUMPTION`, `ACTIVE_FILE`, `ACTIVE_SYMBOL`, `IMPLEMENTATION_STATE`, `UNRESOLVED_ERROR`, `RESOLVED_ERROR`, `TEST_RESULT`, `TOOL_OUTPUT`, `DEBUGGING_ATTEMPT`, `USER_PREFERENCE`, `ARCHITECTURE`, `DEPENDENCY`, `OPEN_QUESTION`, `TODO`, `COMPLETED_TASK`, `BRANCH_STATE`, `EXTERNAL_REFERENCE`, `NOISE`.

Protection is one of `LOCKED`, `CRITICAL`, `IMPORTANT`, `NORMAL`, or `DISCARDABLE`. Lifecycle is one of `HOT`, `WARM`, `COLD`, or `ARCHIVED`; protection and lifecycle are independent. Missing values are null/unknown, never silently defaulted to verified.

## 4. Normalized events

Adapters MAY emit the following event names. Each event includes `event_id`, `occurred_at`, `session_id`, `agent_id`, `source_version`, `observed_or_inferred`, and a typed `payload`.

| Event | Required payload |
|---|---|
| `session.started` | session identifier and project reference |
| `prompt.submitted` | prompt reference or user-approved extracted items |
| `tool.started` | tool name and call identifier |
| `tool.completed` | call identifier, result reference, truncation status |
| `file.changed` | repository-relative path and change reference when available |
| `task.changed` | previous and current task identifiers or objectives |
| `context.usage` | used and total values, unit, measurement source |
| `compaction.pre` | trigger and current-state package reference, if exposed |
| `compaction.post` | resulting-state package reference, if exposed |
| `session.ended` | end reason when known |

Adapters MUST declare event support in `cg doctor`. Missing `compaction.post` means post-compaction integrity cannot be verified automatically.

## 5. Checkpoint

A checkpoint contains `checkpoint_id`, `project_id`, `task_id`, `branch_id`, `created_at`, `parent_checkpoint_id`, `protocol_version`, `policy_version`, `objective`, `scope`, `requirements`, `protected_constraints`, `decisions`, `active_files`, `active_symbols`, `implementation_state`, `completed_work`, `unresolved_issues`, `open_questions`, `tests`, `blockers`, `current_branch`, `dependencies`, `next_actions`, and `item_refs`.

Each fact SHOULD include source references and a verification state: `verified`, `reported`, `inferred`, or `unknown`. A checkpoint is immutable; updates create a new checkpoint with a parent reference.

## 6. Deterministic Context Pressure V1

Each available component is normalized to 0–100. The V1 weighted score is:

| Component | Weight | V1 normalized signal |
|---|---:|---|
| Window usage | 30% | `100 × used / total`, clamped to 0–100 |
| Redundancy | 15% | Duplicate-token share scaled linearly to 100 at 30% duplicate share |
| Staleness | 15% | Stale-token share scaled linearly to 100 at 50% stale share |
| Task fragmentation | 15% | 0 for one active task; linear to 100 at four or more |
| Tool-output pollution | 10% | Tool-output token share scaled to 100 at 40% |
| Upcoming operation | 10% | Estimated added tokens / remaining capacity × 100, clamped |
| Conflict risk | 5% | 25 points per unresolved conflict, capped at 100 |

V1 defines an item as stale when its `last_used_at` (or `created_at` if never used) is more than 30 days old. The default is policy-versioned and configurable in a later policy command; `LOCKED` and `CRITICAL` items are excluded from the stale-token numerator. A missing or invalid timestamp is unknown and is excluded rather than treated as fresh or stale.

The total is the weighted mean over available components; unavailable components are excluded and remaining weights are renormalized. The response MUST include `coverage` (available weight divided by 100), component inputs, policy version, and uncertainty warnings. A score with less than 60% coverage is `partial` and MUST NOT trigger an automatic action.

Default interpretation: 0–39 normal; 40–49 review; 50–64 propose cleanup; 65–74 checkpoint and plan; 75–89 high pressure; 90–100 emergency preservation. A score recommends work; it does not authorize a destructive operation.

## 7. Deterministic Integrity V1

Each expected item is compared against supplied current-state evidence and assigned `preserved`, `missing`, `conflicting`, or `unverified`. Weights are: hard constraints 5, requirements 5, decisions 4, unresolved issues 4, active implementation 3, useful history 1.

`integrity = 100 × sum(weights for preserved items) / sum(weights for all expected items)`.

Missing, conflicting, and unverified items receive zero preserved weight. The response MUST also include per-category results, evidence references, total expected weight, policy version, and coverage. If any `LOCKED` or `CRITICAL` item is missing or conflicting, overall status is `fail` regardless of numeric score. If any expected item is unverified, status is `inconclusive`; absence from a partial package is never treated as loss or preservation. An empty baseline returns `not_applicable`, never 100%.

## 8. Context Transaction

Every persistent state-changing command MUST create an operation-journal entry. Any operation that overwrites, archives, summarizes, deduplicates, discards, or otherwise transforms existing Guardian-managed context is a transaction with these states:

`planned → approved → applying → verified → committed`

Failure transitions to `failed` and initiates recovery. A transaction record includes ID, request ID, operation, affected item IDs, source snapshot references, policy version, preview, approval actor/time, before/after hashes, result, rollback capability, and timestamps.

Checkpoint creation and protection changes are also journaled and reversible; immutable checkpoints are withdrawn by creating a superseding record rather than deleting history. `plan` is read-only and returns a stable preview plus expiry time.
2. `apply` MUST reject an expired or changed plan and MUST re-check protection.
3. Before mutation, the runtime MUST write and verify a recovery snapshot and append a journal intent.
4. After mutation, it MUST verify the result and append a commit record.
5. `rollback` restores Guardian-managed records from the snapshot and records the recovery action.

Provider-side compaction cannot be undone by Guardian. Its recovery promise is reinjection of a verified recovery package, not restoration of the provider's original private transcript.

## 9. Proposed CLI surface

```text
cg doctor --format json
cg status --format json
cg task current --format json
cg retrieve --query <text> --format json
cg checkpoint create --input - --format json
cg checkpoint list --task <id> --format json
cg checkpoint show <id> --format json
cg integrity verify --checkpoint <id> --input - --format json
cg protect add --item <id> --level <level> --format json
cg protect remove --item <id> --format json
cg transaction plan --input - --format json
cg transaction apply --plan <id> --format json
cg transaction rollback <transaction-id> --format json
```

Commands that mutate state MUST return the transaction or checkpoint ID. Human-readable output is optional sugar over the JSON contract.

## 10. Error codes

Minimum stable codes: `NOT_INITIALIZED`, `ADAPTER_UNSUPPORTED`, `CAPABILITY_UNAVAILABLE`, `INVALID_INPUT`, `SCHEMA_VERSION_UNSUPPORTED`, `PROTECTED_ITEM`, `PLAN_EXPIRED`, `STATE_CHANGED`, `RECOVERY_UNAVAILABLE`, `ROLLBACK_FAILED`, `CONFLICT_REQUIRES_USER`, `STORAGE_CORRUPT`, `PERMISSION_DENIED`.

Errors MUST fail closed: no partial destructive action is reported as success. Partial read-only results may return `status: partial` with explicit warnings.
