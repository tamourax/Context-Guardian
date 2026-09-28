# Context Guardian Evaluation Plan

**Status:** Draft benchmark contract  
**Purpose:** Establish measurable evidence before making product or savings claims.

## 1. Evaluation principles

- Compare the same task with the same model, agent version, repository snapshot, and task instructions, with and without Guardian.
- Randomize run order where practical and repeat tasks to estimate variance.
- Separate deterministic protocol tests from model-dependent task outcomes.
- Publish scenario definitions, scoring rubrics, policy versions, and raw aggregate results.
- Do not count estimated or unavailable token measurements as exact.
- Do not publish illustrative results as measured results.

## 2. Core metrics

| Metric | Definition |
|---|---|
| Task completion rate | Share of runs meeting the predefined task rubric without violating constraints. |
| Critical context loss rate | Share of transitions after which an expected protected/critical item is missing or conflicting. |
| Forgotten constraints | Count of explicit constraints violated or re-requested after transition. |
| Manual restatements | User messages needed only to repeat previously supplied task state. |
| Context tokens | Agent-reported value or clearly labeled estimate; report source and uncertainty. |
| Tokens recovered | Reduction in active context attributable to a verified Guardian transaction; never infer from a summary alone. |
| Integrity precision/recall | Accuracy of preserved/missing/conflicting classification against labeled ground truth. |
| False-safe rate | Share of cases reported safe despite a missing critical item. Target is zero on the deterministic critical-state suite. |
| Latency overhead | Added wall-clock time from Guardian operations, reported median and p95. |
| Interruption rate | User confirmations or questions caused by Guardian per task. |
| Recovery success | Share of injected transaction failures whose state is restored and verified. |

## 3. Benchmark scenarios

At minimum include:

1. Multi-file feature with explicit hard constraints.
2. Production bug with unresolved issue state and later context transition.
3. Long debugging session with repeated terminal output and failed hypotheses.
4. Task switch between two unrelated branches and later resume.
5. Conflicting old note versus current repository evidence.
6. Compaction where one protected requirement is deliberately omitted from the resulting state.
7. Compaction where no critical information is lost (false-alarm check).
8. Transaction failure during archive/summarize and rollback verification.
9. Adapter hook missing, delayed, malformed, or reporting truncated state.
10. Sensitive content / credential fixture to verify redaction and no Guardian cloud transmission.

## 4. Deterministic release gates

Before any mutating feature ships:

- 100% of labeled `LOCKED` and `CRITICAL` items survive every allowed transformation, or the operation is rejected.
- Every accepted transaction has a readable pre-state snapshot and a verified rollback path.
- Expired or stale plans are rejected.
- Integrity scoring is reproducible from identical inputs and policy versions.
- Missing adapter evidence is reported as unknown/unverified, never as preserved.
- The false-safe rate is zero on the deterministic critical-state suite.
- No Guardian cloud transmission occurs in V1 network-capture evaluation.

## 5. Model-dependent pilot gates

Do not claim improved task completion until a preregistered paired evaluation shows a meaningful improvement with confidence intervals and no material increase in constraint violations, latency, or user interruptions. Report per-scenario results; an overall average must not hide regressions in critical scenarios.

## 6. Result format

Each evaluation report records:

- benchmark version, date, repository fixture and commit;
- agent/model/provider versions and relevant settings;
- Guardian/runtime/adapter/policy versions;
- task scenario and success rubric;
- sample size and run order;
- each core metric with measurement source and uncertainty;
- failures, exclusions, and deviations;
- reproducible instructions for rerunning the evaluation.

## 7. Initial milestone

The first milestone is not a token-savings claim. It is protocol correctness: preserve protected state, detect injected context loss, report unsupported evidence honestly, and recover Guardian-managed state after a failed transaction.

## 8. Initial implementation gate results — 2026-09-28

- Deterministic protocol, storage, transaction, and CLI suite: **24 tests passed**.
- Protected-item rejection, explicit transaction confirmation, stale-plan rejection, snapshot verification, rollback, and rollback conflict protection: **passed**.
- Integrity behavior for complete, partial, empty, and structured critical-state packages: **passed**.
- Static audit for Guardian network-client imports: **passed**. Packet-level network capture remains required before a packaged release.
- Claude Code executable/version probe: **passed** (`2.1.274`).
- Real `PreCompact` callback observation: **blocked**; no such hook group is configured in this environment.
- Real `SessionStart(compact)` callback observation: **blocked**; an unrelated event group exists, but no Guardian callback is configured and no event was observed.
- Post-transition state package from the adapter: **unsupported**. Manual state packages can be checked with the integrity CLI.
- Automatic compaction and event-driven integrity release gate: **blocked and disabled**. No synthetic lifecycle event was used to mark it passed.
- Model-dependent task-completion pilot: **not run**; this build provides the protocol/core and manual workflow, not an enabled event-driven agent integration.
