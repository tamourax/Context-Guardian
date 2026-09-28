# Context Guardian

Context Guardian is a local-first runtime for managing task-critical context during long AI-assisted software sessions. It gives an agent structured tasks, protected context items, immutable checkpoints, integrity comparisons, and reversible archive or caller-supplied summary transactions.

> An agent can lose track of a task. Context Guardian keeps its important state inspectable and recoverable.

## Project status

This is an experimental V1 implementation, not a release-ready product. The protocol, SQLite storage, JSON-first CLI, reversible Guardian-managed transactions, and a Codex CLI hook adapter are implemented. The Codex project hooks are configured, but live hook delivery has not yet been observed. Post-compaction integrity verification also remains unavailable until an agent supplies a current-state package.

| Area | Current state |
| --- | --- |
| Runtime and storage | Implemented; local SQLite under `.context-guardian/` |
| Tasks, context items, checkpoints | Implemented |
| Integrity comparison | Implemented for caller-supplied state packages |
| Archive and summarize | Reversible transactions; explicit plan, confirmation, snapshot, and rollback |
| Codex CLI adapter | Project-local `SessionStart`, `PreCompact`, and `PostCompact` hooks configured; live events unverified |
| Automatic provider compaction | Disabled |
| Automatic post-compaction integrity | Disabled; Codex hook does not provide resulting state |
| Privacy evaluation | Static audit done; packet-level network capture remains outstanding |
| Model-dependent benefit evaluation | Not run |

The project [`SKILL.md`](SKILL.md) is a source document in this checkout. It is **not installed** into Codex or another agent. The Codex integration here is a project-local hook configuration in [`.codex/hooks.json`](.codex/hooks.json); it does not edit `~/.codex`.

For a plain-language, detailed explanation of what the project runtime and agent skill do, see the [Arabic project guide](PROJECT_GUIDE_AR.md).

## How it fits together

```text
Agent (Codex CLI today)
  └─ project-local hook adapter
       └─ Context Guardian CLI
            ├─ protocol and deterministic scoring
            ├─ local SQLite state and hash-chained journal
            ├─ checkpoints and integrity comparison
            └─ reversible Guardian-managed transactions
```

The adapter reports only what the agent actually exposes. Guardian does not inspect an agent transcript to guess that a lifecycle event occurred. A configured hook is not treated as proof that it ran.

## Requirements

- Python 3.11 or later.
- SQLite (included with standard Python builds).
- Optional: Codex CLI with hooks enabled to try the project-local Codex adapter. The current development probe found Codex CLI `0.151.0` and `hooks` enabled.

The runtime has no third-party Python dependencies.

## Install and initialize

From the project directory, install the CLI in editable mode and initialize project-local state:

```powershell
python --version
python -m pip install -e .
cg init
cg doctor
cg status
```

For a checkout without package installation, run the same commands through the source runner:

```powershell
python cg.py init
python cg.py doctor
python cg.py status
```

`init` creates `.context-guardian/guardian.sqlite3`. The directory is local application data and is excluded by `.gitignore`; it is not included in source publication. Most commands accept `--project PATH`; by default they use the current directory (or its initialized parent project).

## Try the Codex CLI adapter

The tracked `.codex/hooks.json` declares project-local command hooks for:

- `SessionStart` (`startup`, `resume`, and `clear`): records a session-start event.
- `PreCompact` (`manual` and `auto`): records the real pre-compaction event and creates a checkpoint of Guardian-managed state when a task is active.
- `PostCompact` (`manual` and `auto`): records that compaction occurred. Codex does not provide the post-compaction state package in this hook, so the result is `unverified`.

To try them with Codex CLI:

1. Initialize Guardian in the project with `python cg.py init` if it has not been initialized.
2. Start Codex CLI from the project root with `codex`.
3. In the Codex CLI session, open `/hooks`. Review the three Context Guardian command hooks and trust them only if they match this project configuration. Codex may skip unreviewed hooks.
4. Start a fresh Codex session in this project so `SessionStart` can be observed.
5. Create or select a Guardian task before compaction if you want `PreCompact` to create a task checkpoint:

   ```powershell
   python cg.py task create --objective "Describe the task being tested"
   ```

6. Let Codex perform or explicitly trigger a supported compaction, then inspect the adapter report:

   ```powershell
   python cg.py adapter doctor codex --project .
   ```

The report distinguishes configured hooks from observed events. Do not pipe invented hook payloads into `cg adapter hook codex` to claim lifecycle support. The hook command is an adapter entry point, not a test-event generator.

For a fresh checkout, review and trust the hooks in Codex before expecting events. The hook command assumes Codex starts in the project root. The configuration is project-local and does not install `SKILL.md`, change global Codex settings, or access transcript contents.

Manual checkpointing and integrity checks can be used without any adapter hooks.

## CLI reference

After installation, use `cg`; in a source checkout, replace `cg` with `python cg.py`.

| Command | Purpose |
| --- | --- |
| `cg init` | Initialize the local project database |
| `cg doctor` | Check runtime, storage, journal, and Codex adapter gates |
| `cg status` | Show project and current context status |
| `cg pressure` | Calculate deterministic pressure; optional `--used-tokens` and `--total-tokens` accept agent-reported values |
| `cg task create --objective TEXT` | Create and activate a task |
| `cg task current` / `cg task list` | Inspect task state |
| `cg task switch TASK_ID` | Switch the active task |
| `cg item add --input -` | Add a structured context item from a protocol envelope on stdin |
| `cg item list [--task TASK_ID] [--include-archived]` | List context items |
| `cg item show ITEM_ID` | Show one item |
| `cg protect add --item ITEM_ID --level LEVEL` | Change an item's protection level |
| `cg protect remove --item ITEM_ID --confirm` | Remove protection with explicit confirmation |
| `cg checkpoint create --input -` | Save an immutable structured checkpoint |
| `cg checkpoint list [--task TASK_ID]` / `show CHECKPOINT_ID` | Inspect checkpoints |
| `cg checkpoint compare LEFT_ID RIGHT_ID` | Compare two checkpoints |
| `cg retrieve --query TEXT [--task TASK_ID] [--limit N]` | Search locally stored context lexically |
| `cg integrity verify --checkpoint ID --input -` | Compare a supplied current-state package to a checkpoint |
| `cg transaction plan --input -` | Preview an archive or caller-supplied summary transaction |
| `cg transaction apply --plan TX_ID --confirm` | Apply a current transaction plan |
| `cg transaction rollback TX_ID --confirm` | Restore a committed transaction from its verified snapshot |
| `cg transaction show TX_ID` | Inspect transaction state |
| `cg journal verify` / `cg journal list` | Verify or inspect the append-only journal |
| `cg adapter doctor codex` | Inspect Codex CLI, hook configuration, observed events, and release gates |
| `cg adapter config codex` | Print a sample hook configuration; does not write settings |

Every command accepts `--format json`. Project-scoped commands accept `--project PATH`. Mutating requests also accept `--request-id ID` for retry-safe behavior.

Use `cg --help` and `cg COMMAND --help` for the installed command's full option list.

## Structured input and examples

Commands that accept `--input -` read a JSON protocol envelope from stdin. A request ID is bound to the command and payload; reusing it with different content is rejected.

Create a checkpoint in PowerShell:

```powershell
@'
{
  "protocol_version": "1.0",
  "request_id": "req_checkpoint_001",
  "command": "checkpoint.create",
  "payload": {
    "objective": "Fix refund retries without changing the public API",
    "scope": "Trace retry handling and add regression coverage",
    "requirements": ["Retries remain idempotent"],
    "protected_constraints": ["Do not change the public API"],
    "decisions": [],
    "active_files": [],
    "active_symbols": [],
    "implementation_state": "Investigation started",
    "completed_work": [],
    "unresolved_issues": [],
    "open_questions": [],
    "tests": [],
    "blockers": [],
    "dependencies": [],
    "next_actions": ["Inspect the retry handler"]
  }
}
'@ | cg checkpoint create --input -
```

Use the same envelope shape with `"command": "item.add"` to add an item. For example, the payload may contain:

```json
{
  "type": "HARD_CONSTRAINT",
  "content": "Do not change the public API",
  "protection": "CRITICAL",
  "source": { "kind": "user_message" }
}
```

Supported item types include `GOAL`, `REQUIREMENT`, `HARD_CONSTRAINT`, `DECISION`, `IMPLEMENTATION_STATE`, `COMPLETED_TASK`, `UNRESOLVED_ERROR`, `OPEN_QUESTION`, `ACTIVE_FILE`, `ACTIVE_SYMBOL`, `TEST_RESULT`, `TOOL_OUTPUT`, and `USER_PREFERENCE`. Protection levels are `LOCKED`, `CRITICAL`, `IMPORTANT`, `NORMAL`, and `DISCARDABLE`.

To verify state after a transition, provide a state package with the same structured fields as the checkpoint. The package must represent what is actually present in the agent's active state; Guardian does not extract it from a transcript.

```powershell
@'
{
  "protocol_version": "1.0",
  "request_id": "req_integrity_001",
  "command": "integrity.verify",
  "payload": {
    "objective": "Fix refund retries without changing the public API",
    "requirements": ["Retries remain idempotent"],
    "protected_constraints": ["Do not change the public API"],
    "decisions": [],
    "active_files": [],
    "active_symbols": [],
    "implementation_state": "Investigation resumed",
    "completed_work": [],
    "unresolved_issues": [],
    "open_questions": [],
    "tests": [],
    "blockers": [],
    "dependencies": [],
    "next_actions": ["Inspect the retry handler"]
  }
}
'@ | cg integrity verify --checkpoint CHECKPOINT_ID --input -
```

IDs such as `CHECKPOINT_ID` are returned by the corresponding create command. Integrity results classify expected state as preserved, missing, conflicting, or unverified and include a deterministic score with policy version and evidence coverage.

## Reversible context transactions

V1 supports `archive` and caller-supplied `summarize`. It does not generate summaries itself. Protected items cannot be transformed. Plans expire and are rejected if their source items change before application.

Create a plan by sending a `transaction.plan` envelope, for example:

```json
{
  "protocol_version": "1.0",
  "request_id": "req_archive_001",
  "command": "transaction.plan",
  "payload": {
    "operation": "archive",
    "item_ids": ["ctx_example"]
  }
}
```

Pipe the JSON to `cg transaction plan --input -`, inspect the returned preview, then apply the returned transaction ID with `cg transaction apply --plan TX_ID --confirm`. Roll back with `cg transaction rollback TX_ID --confirm`. Rollback refuses to overwrite records changed after the transaction. Each accepted transaction has a pre-state snapshot, hashes, and journal entries.

## Storage, privacy, and recovery

- Project data lives in `.context-guardian/`; the directory is ignored by Git.
- The runtime uses local SQLite, immutable checkpoints, verified snapshots, and an append-only hash-chained journal.
- Context processing by Guardian does not require a Guardian cloud service. The coding agent or its model provider may process context under that product's own settings; Guardian cannot promise that all context stays on the device.
- The Codex hook stores allowlisted lifecycle metadata only. It does not read prompts, transcript contents, source files, or transcript paths.
- Common credential patterns are rejected before saving. This is a heuristic filter, not a complete secret scanner. Do not submit real credentials as context.
- Inspect `cg doctor` and `cg journal verify` before recovery work. If a database or snapshot is corrupt, stop mutations and preserve the local data for diagnosis.

See [`SAFETY_AND_RECOVERY.md`](SAFETY_AND_RECOVERY.md) for the recovery and authorization contract.

## Development and verification

Run the deterministic suite from the project root:

```powershell
python -m unittest discover -s tests -v
```

The suite covers protocol validation, scoring, SQLite storage, idempotency, protected-item rejection, transaction confirmation and rollback, integrity reports, and Codex hook normalization/reporting. Passing these tests does not prove Codex invoked the configured hooks. Live hook observation, packet-level privacy capture, and model-dependent evaluation are separate gates.

Key design and implementation documents:

- [`PRODUCT_SPEC.md`](PRODUCT_SPEC.md) — V1 product scope, guarantees, and release sequence.
- [`SKILL.md`](SKILL.md) — normative agent behavior; not installed by this repository.
- [`PROTOCOL.md`](PROTOCOL.md) — schemas, scoring rules, state transitions, and errors.
- [`ADAPTER_SPEC.md`](ADAPTER_SPEC.md) — agent adapter contract and Codex capability spike.
- [`SAFETY_AND_RECOVERY.md`](SAFETY_AND_RECOVERY.md) — protected state, confirmation, privacy, and recovery.
- [`EVALS.md`](EVALS.md) — deterministic and model-dependent release gates.
- [`context_guardian_master_spec.md`](context_guardian_master_spec.md) — long-term product vision and roadmap.

## Current release gates

As of 2026-09-28, the deterministic test suite passes, Codex CLI `0.151.0` is detected with hooks enabled, and the project-local hook configuration contains all three declared event groups. Actual Codex `SessionStart`, `PreCompact`, and `PostCompact` callbacks have not yet been observed. Codex does not provide a post-compaction state package through these hooks, so automatic post-transition integrity remains disabled. Packet-level network capture and the model-dependent pilot have not been run. See [`EVALS.md`](EVALS.md) for the detailed gate status.

## License

No license has been selected yet. Until a license is added, do not assume this source is available for reuse under an open-source license.
