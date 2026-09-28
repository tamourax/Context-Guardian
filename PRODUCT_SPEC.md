# Context Guardian — V1 Product Specification

**Status:** Draft implementation target  
**Parent vision:** [context_guardian_master_spec.md](context_guardian_master_spec.md)  
**Scope:** Local context continuity for one coding-agent integration

## Product statement

Context Guardian stores and manages a compact, structured representation of the state needed to continue a coding task. It protects important user requirements, checkpoints active work, and checks whether expected state is present after a context transition.

Guardian manages its own context records and recovery packages. It does not claim to control an agent's private context window unless that agent exposes a supported interface for doing so.

## V1 users and job

**Primary user:** a developer using one supported coding agent for multi-step repository work.

**Job:** resume work after context compaction or task switching without repeating requirements, decisions, unresolved issues, and next steps.

## V1 includes

1. Project-local storage and a doctor command that reports storage and adapter capabilities.
2. A structured task record containing objective, requirements, protected constraints, decisions, active files, completed work, unresolved issues, and next actions.
3. Explicit user protection for individual context items.
4. Checkpoint create, list, read, and compare operations.
5. Deterministic integrity comparison between an expected checkpoint and a supplied current-state package.
6. Retrieval of task-relevant stored items with source, timestamp, and confidence metadata.
7. Observe and assist modes. Observe is the default; assist requires confirmation before mutation.
8. A single reference adapter, selected only after its lifecycle capabilities pass the gates in `ADAPTER_SPEC.md`.
9. An append-only operation journal and rollback for Guardian-managed transformations.

## V1 excludes

- Silent deletion, automatic provider compaction, and automatic rollback into an agent session.
- Cross-agent synchronization, cloud services, team policy, enterprise controls, and shared state.
- Claims of exact token accounting where the adapter supplies only estimates.
- A general-purpose vector database or whole-conversation replay.
- Automatic conflict resolution where evidence is ambiguous.
- Predictive pressure modeling and learned policies.

## Operating modes

| Mode | V1 behavior |
|---|---|
| Observe | Read state and report recommendations. No mutations. Default. |
| Assist | Prepare a preview and ask before applying a mutation. |
| Auto | Reserved for a later version after recovery and evaluation gates pass. |
| Strict | Reserved for team or enterprise policy enforcement. |

## User-visible guarantees

- Guardian does not require uploading project context to a Guardian cloud service.
- The agent provider may process context according to that agent's own product and account settings; Guardian cannot override that.
- Guardian never silently discards a protected item, hard constraint, current requirement, unresolved security issue, or active task objective.
- If required adapter data is unavailable, the result is marked unknown or unsupported, not inferred as a successful check.
- Every accepted operation reports what changed, what was preserved, and whether recovery is available.

## V1 acceptance criteria

- A user can create and reopen a checkpoint after restarting the CLI.
- Protected items remain present after every supported Guardian transformation.
- Integrity output identifies each expected item as preserved, missing, conflicting, or unverified and includes evidence references.
- The score is reproducible from the same input and policy version.
- Each mutation has a journal entry and a verified recovery path before it is applied.
- Observe mode makes no writes other than explicitly configured diagnostic logs; it never changes context state.
- The first adapter reports its supported events and limitations through `cg doctor`.
- Benchmark results compare the same scenarios with and without Guardian and include overhead and context-loss metrics.

## Release sequence

1. Validate protocol and one adapter's observable lifecycle.
2. Ship read-only status, task inspection, checkpointing, and integrity reports.
3. Add protected context and retrieval in assist mode.
4. Add reversible archive/summarize transactions only after recovery tests pass.
5. Consider a second adapter after the first adapter's reliability is measured.

## Open decisions

- Confirm the reference adapter after the capability spike; Claude Code is a candidate, not yet a validated integration.
- Define supported minimum agent versions from observed hook behavior.
- Select the V1 token estimator and record its accuracy limits.
- Decide whether checkpoint contents are encrypted at rest in the first release.
