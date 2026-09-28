# Context Guardian
## Full Product, Business Model, Technical Architecture, and Agent Implementation Specification

**Version:** 1.0  
**Status:** Product Definition / Full Implementation Blueprint  
**Product Type:** Developer Infrastructure / AI Coding Agent Context Runtime  
**Primary Delivery Model:** Free, local-first developer tool  
**Long-Term Model:** Open-core / team / enterprise extensions  
**Primary Users:** Heavy AI coding-agent users, software engineers, AI-native teams  
**Initial Agent Targets:** Codex, Claude Code, OpenCode  
**Future Targets:** Cursor, Windsurf, custom MCP/agent runtimes, IDE agents, enterprise agent platforms

---

# 1. Executive Summary

Context Guardian is a local-first context lifecycle runtime for AI coding agents.

It is not a memory database, not a generic RAG framework, and not merely a better `/compact` command.

Its purpose is to continuously manage the useful working context of long-running AI coding sessions so that an agent can preserve important constraints, decisions, task state, unresolved issues, active files, and implementation intent while reducing low-value token usage.

The product should monitor context pressure, understand the semantic role of information, protect critical state, selectively compress or archive low-value content, create structured checkpoints, detect context loss after compaction, and automatically rehydrate missing information.

The long-term vision is to become a cross-agent **Context Runtime** that sits above individual coding agents and manages the lifecycle of their working context.

The core product promise is:

> **Your agent can forget. Your context shouldn't.**

The central design principle is:

> Do not blindly compact context. Decide what to preserve, summarize, archive, retrieve, or forget based on task relevance, risk, and expected future value.

---

# 2. Problem Definition

Modern coding agents can consume very large context windows, but long sessions still degrade because of:

- context-window limits;
- automatic compaction;
- lossy summarization;
- stale information;
- duplicate context;
- repeated terminal output;
- irrelevant tool output;
- task switching;
- branch switching;
- old debugging attempts;
- conflicting historical decisions;
- "lost in the middle" effects;
- inefficient retrieval;
- oversized repository context;
- multi-agent fragmentation;
- forgotten user constraints;
- lost implementation state after compaction;
- repeated rediscovery of already-known facts;
- high token usage without corresponding task value.

The raw size of the context window is not the real problem.

The actual problem is:

> **The agent lacks a reliable policy for deciding what deserves to stay in active context.**

A 200K-token context can still be poorly managed.

A well-managed 40K-token context may outperform it.

---

# 3. Core Thesis

Context Guardian should treat context as an operating resource similar to memory management in an operating system.

Information should not simply be "in context" or "out of context."

It should move through lifecycle tiers:

```text
HOT
- current objective
- current task state
- active files/symbols
- unresolved errors
- recent critical decisions

WARM
- related architecture
- nearby files
- historical decisions relevant to the current task
- recent completed sub-tasks

COLD
- resolved issues
- previous branches
- older debugging logs
- historical discussions
- archived checkpoints
```

The product dynamically moves information between these tiers.

---

# 4. Product Positioning

## 4.1 What Context Guardian Is

Context Guardian is:

- a live context lifecycle manager;
- a context observability layer;
- a structured task-state system;
- a context integrity system;
- a compaction safety layer;
- a cross-agent context runtime;
- a selective forgetting engine;
- a context optimization policy engine.

## 4.2 What It Is Not

Do not position or implement Context Guardian primarily as:

- a generic memory database;
- a vector database;
- a RAG framework;
- a chatbot memory plugin;
- a summarization utility;
- a note-taking tool;
- a single-agent history extension;
- a replacement LLM;
- a replacement for Git;
- a replacement for native agent compaction.

Context Guardian should **orchestrate existing agent capabilities** whenever possible.

---

# 5. Product Vision

Long term, a developer should be able to install Context Guardian once and use multiple AI coding agents without losing task continuity.

Example:

```text
Developer
   |
   +-- Codex
   +-- Claude Code
   +-- OpenCode
   +-- Cursor
   |
   v
Context Guardian
   |
   +-- task state
   +-- constraints
   +-- decisions
   +-- protected context
   +-- checkpoints
   +-- context branches
   +-- integrity verification
   +-- retrieval
   +-- policies
```

The developer should be able to move between agents while preserving the semantic state of the work rather than replaying the conversation.

---

# 6. Primary Value Proposition

Context Guardian improves:

- continuity of long-running coding sessions;
- preservation of user constraints;
- preservation of architectural decisions;
- task completion across compaction boundaries;
- token efficiency;
- context quality;
- cross-agent portability;
- visibility into context health;
- reliability of AI coding workflows.

Key measurable promise:

```text
More successful engineering work
per useful context token.
```

---

# 7. Core User Personas

## 7.1 Heavy AI Coding Developer

Characteristics:

- uses coding agents daily;
- runs long sessions;
- frequently hits context limits;
- works across large repositories;
- performs refactors and debugging;
- uses multiple agents;
- values continuity more than novelty.

Pain:

- agent forgets previous requirements;
- compaction loses implementation state;
- must repeatedly remind the agent;
- token usage grows rapidly;
- old terminal output pollutes context.

This is the initial ICP.

---

## 7.2 AI-Native Solo Builder

Characteristics:

- uses agents for most implementation work;
- works across backend/mobile/frontend;
- frequently changes tasks;
- may have many branches in parallel.

Pain:

- context becomes fragmented;
- task-switching causes forgotten state;
- different agents maintain incompatible histories.

---

## 7.3 Engineering Team

Characteristics:

- several developers use AI agents;
- wants consistent context policies;
- needs shared engineering decisions;
- wants observability and security.

Pain:

- each developer has separate agent memory;
- no shared context governance;
- difficult to audit what context agents used.

---

## 7.4 Enterprise AI Platform Team

Future customer.

Needs:

- privacy controls;
- local deployment;
- organization policies;
- audit trails;
- central context observability;
- shared agent state;
- access controls;
- retention rules.

---

# 8. Jobs To Be Done

The product must help users:

1. preserve important information before context degradation;
2. reduce low-value context automatically;
3. prevent important constraints from disappearing;
4. know when compaction is safe;
5. recover information lost after compaction;
6. switch tasks without losing previous state;
7. resume old tasks quickly;
8. move task context between coding agents;
9. see why context is consuming tokens;
10. measure whether context management improves outcomes.

---

# 9. Core Product Concept: Context Pressure

Context usage percentage alone is insufficient.

Context Guardian must compute an adaptive **Context Pressure Score**.

Example factors:

```text
Context Pressure Score =
    window_usage
  + redundancy
  + stale_context
  + task_fragmentation
  + tool_output_volume
  + unresolved_state_density
  + upcoming_operation_cost
  + conflict_risk
  - information_value
  - available_context_headroom
```

The exact weights must be configurable and later learnable.

---

# 10. Smart 40% Review

40% should be a default review milestone, not a forced compaction threshold.

Example:

```text
Context usage: 42%

Useful information density: HIGH
Redundancy: LOW
Task drift: LOW
Critical-state density: HIGH

Decision:
DO NOTHING
```

Another session:

```text
Context usage: 34%

Duplicate output: HIGH
Resolved debugging logs: HIGH
Task drift: MEDIUM
Old branch context: HIGH

Decision:
RUN CONTEXT GC
```

The system should act based on pressure and value, not percentage alone.

---

# 11. Context Milestones

Suggested default lifecycle:

```text
0-40%   Normal operation

40%     Context health review

50-60%  Garbage collection and selective compression if needed

65-75%  Archive inactive branches and summarize low-value history

75-85%  Structured checkpoint and proactive compaction planning

85-90%  High-pressure mode

90%+    Emergency state preservation + compact + integrity verification
```

Thresholds must be configurable.

---

# 12. Ambiguity-Aware User Interaction

Context Guardian must not constantly interrupt developers.

Ask the user only when the active priority is ambiguous.

Example:

```text
You have three active workstreams:

A. Payment integration
B. Notification bug
C. Admin dashboard

Which one should remain in hot context?

[A] [B] [C] [Keep all]
```

If the active goal is obvious, the system should act automatically.

---

# 13. Context Classification

Every relevant item should be classified.

Required semantic classes:

```text
GOAL
REQUIREMENT
HARD_CONSTRAINT
DECISION
ASSUMPTION
ACTIVE_FILE
ACTIVE_SYMBOL
IMPLEMENTATION_STATE
UNRESOLVED_ERROR
RESOLVED_ERROR
TEST_RESULT
TOOL_OUTPUT
DEBUGGING_ATTEMPT
USER_PREFERENCE
ARCHITECTURE
DEPENDENCY
OPEN_QUESTION
TODO
COMPLETED_TASK
BRANCH_STATE
EXTERNAL_REFERENCE
NOISE
```

Each item should have metadata:

```yaml
id:
type:
content:
source:
created_at:
last_used_at:
confidence:
importance:
relevance:
freshness:
protected:
task_id:
branch_id:
agent_id:
file_refs:
symbol_refs:
supersedes:
conflicts_with:
token_estimate:
```

---

# 14. Protected Context

Users and the runtime must be able to protect information.

Protection levels:

```text
LOCKED
CRITICAL
IMPORTANT
NORMAL
DISCARDABLE
```

Examples:

```text
LOCKED:
- "Database must remain SQLite"
- "Do not change public API"
- security requirements
- API contracts

CRITICAL:
- current architecture decision
- active task objective
- unresolved production bug

DISCARDABLE:
- old terminal output
- repeated explanations
- failed experiments
```

Protected items must survive normal compaction.

---

# 15. Semantic Compaction

Compaction must not treat all content equally.

Recommended policies:

| Context Type | Policy |
|---|---|
| Hard constraints | Preserve exact |
| API contracts | Preserve exact |
| Current objective | Preserve exact |
| Architecture decisions | Structured summary |
| Active implementation | Structured snapshot |
| Unresolved errors | Preserve |
| Resolved errors | Summarize |
| Tool output | Aggressive prune |
| Terminal logs | Aggressive prune |
| Failed hypotheses | Keep conclusion only |
| Repeated explanations | Remove duplicates |
| Old branches | Archive |
| Historical discussion | Compress |
| User preferences | Preserve relevant subset |

---

# 16. Context Garbage Collector

Context Guardian should include a context GC engine.

It should detect:

- duplicate messages;
- repeated code;
- repeated stack traces;
- stale terminal output;
- completed task logs;
- old search results;
- failed debugging attempts;
- superseded decisions;
- resolved errors;
- unnecessary tool chatter;
- repeated file contents.

Example output:

```text
Context GC

Removed / archived:

Terminal logs          7,420 tokens
Duplicate code         3,180 tokens
Resolved errors        2,950 tokens
Failed hypotheses      1,780 tokens
Repeated explanations  1,210 tokens

Recovered:
16,540 tokens
```

---

# 17. Structured Checkpoints

Before meaningful compaction or task switching, the system should generate a structured checkpoint.

Required format:

```yaml
checkpoint:
  objective:
  scope:
  requirements:
  protected_constraints:
  decisions:
  active_files:
  active_symbols:
  implementation_state:
  completed_work:
  unresolved_issues:
  open_questions:
  tests:
  blockers:
  current_branch:
  dependencies:
  next_actions:
  context_to_archive:
```

Checkpoints must be:

- versioned;
- timestamped;
- diffable;
- recoverable;
- linked to task/branch;
- exportable;
- human-readable.

---

# 18. Post-Compaction Integrity Verification

This is a flagship feature.

Before compaction, produce a critical-state fingerprint.

Example:

```text
Before compaction

18 decisions
7 hard constraints
9 active symbols
4 unresolved issues
6 requirements
```

After compaction:

```text
Integrity verification

18/18 decisions       OK
7/7 constraints       OK
8/9 active symbols    WARNING
4/4 unresolved issues OK
6/6 requirements      OK
```

If important state is missing:

```text
Missing:
RefundService.handlePartialRefund()

Action:
Rehydrate automatically
```

The system should generate an integrity score.

---

# 19. Context Integrity Score

Example:

```text
Context Integrity: 96%

Constraints       100%
Decisions         100%
Requirements      100%
Active state       91%
Unresolved issues 100%
```

This score should be measurable before and after optimization.

---

# 20. Context Branching

Developers commonly switch tasks.

Instead of mixing unrelated work:

```text
Payment
Notifications
Admin Dashboard
```

Context Guardian should model them as independent branches:

```text
root
├── payment
├── notifications
└── admin-dashboard
```

Each branch has:

- objective;
- checkpoint;
- active files;
- decisions;
- unresolved issues;
- historical summaries;
- branch status.

Commands:

```text
/context branches
/context switch payment
/context park notifications
/context merge payment checkout-refactor
/context archive old-auth-bug
```

---

# 21. Context Time Machine

Every important checkpoint should be recoverable.

Example:

```text
C0 Initial task
C1 Architecture selected
C2 Payment flow implemented
C3 Refund debugging
C4 Webhook fix
```

Commands:

```text
/context timeline
/context rewind C2
/context compare C2 C4
/context restore C3
```

This should restore task state, not blindly replay messages.

---

# 22. Predictive Context Management

The system should estimate future pressure.

Example:

```text
Current context: 56%

Expected next action:
Repository-wide search

Estimated additional context:
18K tokens

Recommendation:
Pre-compact 11K low-value tokens
```

Prediction signals may include:

- file scan size;
- expected tool calls;
- historical agent behavior;
- planned repository search;
- task complexity;
- remaining context budget.

---

# 23. Task Completion Garbage Collection

When a task completes:

```text
Task completed:
Fix partial refund bug
```

The system should transform detailed working history into a compact outcome record:

```yaml
task_summary:
  result: "Partial refund flow fixed"
  changed_files:
    - RefundService.php
    - LedgerService.php
  final_decisions:
    - "Ledger reversals must be idempotent"
  learned_constraints:
    - "Webhook retries may precede settlement update"
  tests:
    - "Partial refund integration test passing"
```

Raw debugging history may then move to cold storage.

---

# 24. Conflict and Staleness Detection

Context Guardian must detect conflicting state.

Example:

```text
Old memory:
Database = MySQL

Current repository:
Database = PostgreSQL
```

The system must not inject both equally.

Required conflict behavior:

1. detect inconsistency;
2. identify timestamps/source authority;
3. mark stale item;
4. prefer newer verified repository state;
5. optionally ask user if ambiguity remains.

Possible authority order:

```text
Current repository state
> explicit current user instruction
> current branch checkpoint
> recent decision
> old memory
```

This must be configurable.

---

# 25. Context ROI

Each context item should have a value estimate.

Example:

```text
Item                          Tokens    Value Score
Hard project constraints        420       0.99
Current task state             1850       0.96
Active source code             5800       0.89
Old terminal logs              7300       0.05
Resolved error history         2800       0.14
Repeated explanation           1600       0.03
```

Optimization objective:

> Maximize expected task value per token.

---

# 26. Context Observability Dashboard

CLI/TUI output should show:

```text
Context Guardian

Agent: Codex
Task: Refund architecture
Branch: payment/refunds

Window usage:      47%
Pressure score:    61/100
Integrity:         98%
Redundancy:        23%
Stale context:     11%

Hot context:       18.4K
Warm context:      27.2K
Cold context:      96.8K

Protected items:   14
Active files:      8
Open issues:       3

Recommended action:
Clean 9.6K tokens of low-value output
```

---

# 27. Multi-Agent Context Runtime

Long-term architecture should support multiple agents.

Example:

```text
Codex
- implementation

Claude Code
- code review

OpenCode
- debugging

Context Guardian
- shared task state
- constraints
- decisions
- active artifacts
```

Agents must not automatically receive the entire shared history.

Context Guardian should create role-specific context packages.

Example:

```text
Reviewer context:
- requirements
- architecture
- changed files
- tests
- known risks

Implementation context:
- current objective
- active files
- relevant code
- unresolved issues
```

---

# 28. Cross-Agent Portability

A user should be able to:

```text
/context handoff claude
```

and Context Guardian generates a portable state package.

Portable context package:

```yaml
task:
requirements:
constraints:
decisions:
files:
symbols:
open_issues:
tests:
recent_changes:
next_action:
```

This is a major long-term differentiator.

---

# 29. Agent Adapter Layer

Use an adapter architecture.

```text
Context Core
    |
    +-- CodexAdapter
    +-- ClaudeCodeAdapter
    +-- OpenCodeAdapter
    +-- CursorAdapter
    +-- GenericMCPAdapter
```

Each adapter should expose normalized lifecycle events:

```text
SESSION_START
PROMPT_SUBMITTED
TOOL_CALL
TOOL_RESULT
FILE_READ
FILE_EDIT
COMMAND_OUTPUT
TASK_CHANGED
CONTEXT_USAGE_CHANGED
PRE_COMPACT
POST_COMPACT
SESSION_END
```

If an agent does not expose a hook directly, support best-effort inference.

---

# 30. Local-First Architecture

Initial product must be local-first.

Requirements:

- no source-code upload by default;
- no mandatory cloud account;
- local storage;
- local embeddings where practical;
- clear telemetry opt-in;
- transparent data retention;
- encrypted sensitive metadata when needed;
- project-specific isolation.

Suggested directory:

```text
.context-guardian/
├── config.yaml
├── state/
├── tasks/
├── checkpoints/
├── branches/
├── index/
├── metrics/
├── policies/
└── logs/
```

---

# 31. Storage Model

Recommended implementation:

- SQLite for structured metadata;
- local files/JSON/YAML for human-readable checkpoints;
- optional local vector index;
- Git-aware references to commits/diffs;
- append-only event log where useful.

Avoid requiring a remote database.

---

# 32. Core Data Objects

Required entities:

```text
Project
Session
Agent
Task
Branch
ContextItem
Checkpoint
Decision
Constraint
Requirement
FileReference
SymbolReference
Issue
ContextEvent
CompactionEvent
IntegrityCheck
Policy
MetricSnapshot
```

---

# 33. Suggested Technical Components

Potential implementation stack:

```text
Core runtime:
Rust, Go, or TypeScript

CLI:
Rust / Go / TypeScript

Local database:
SQLite

Structured config:
YAML/TOML

Optional semantic indexing:
SQLite extensions / local embeddings / lightweight vector index

Agent integrations:
Hooks
MCP
CLI wrappers
agent plugin APIs

Metrics:
local event store
```

Language selection should prioritize:

- easy cross-platform distribution;
- low runtime overhead;
- CLI ergonomics;
- plugin compatibility.

---

# 34. Policy Engine

Policies must be configurable.

Example:

```yaml
context:
  review_threshold: 0.40
  warning_threshold: 0.70
  emergency_threshold: 0.90

protection:
  preserve_requirements: true
  preserve_constraints: true
  preserve_active_symbols: true

gc:
  terminal_output_ttl_minutes: 30
  resolved_error_policy: summarize
  duplicate_detection: true

integrity:
  minimum_score: 0.95
  auto_rehydrate: true
```

Later support organization policies.

---

# 35. Context Decision Engine

Every context item should receive:

```text
importance score
relevance score
freshness score
future-use probability
compression safety score
conflict risk
retrieval cost
token cost
```

Decision:

```text
KEEP_HOT
MOVE_WARM
ARCHIVE
SUMMARIZE
DISCARD
PROTECT
REHYDRATE
REQUEST_USER_DECISION
```

---

# 36. Smart Retrieval

When the current task needs archived information:

```text
Current task:
refund webhook race condition
```

retrieve only context relevant to:

- refunds;
- webhooks;
- financial state;
- affected files;
- prior architectural decisions.

Do not restore the whole session.

---

# 37. Repository Awareness

Context Guardian should understand:

- git branch;
- changed files;
- recent commits;
- diff;
- repository structure;
- active source files;
- code symbol references.

Git should be used as a source of truth for current implementation state whenever appropriate.

---

# 38. Code-Aware Context

Future versions should track symbols.

Example:

```text
RefundService.handlePartialRefund
PaymentGateway.capture
LedgerService.reverseEntry
```

This improves:

- relevant context retrieval;
- active implementation state;
- checkpoint quality;
- integrity verification.

---

# 39. Native Compaction Integration

Context Guardian should prefer native agent/provider compaction when available.

The product's role:

```text
observe
prepare
protect
checkpoint
select
invoke native compact
verify
rehydrate
```

Do not reimplement vendor functionality without a reason.

---

# 40. Manual Commands

Suggested CLI:

```text
cg status
cg inspect
cg optimize
cg gc
cg checkpoint
cg protect
cg unprotect
cg branches
cg switch
cg archive
cg timeline
cg rewind
cg integrity
cg metrics
cg doctor
cg adapters
cg policy
```

Possible slash commands:

```text
/context status
/context optimize
/context protect
/context checkpoint
/context switch
/context rewind
```

---

# 41. Automated Operation Modes

Modes:

```text
observe
assist
auto
strict
```

## Observe

No mutations.

Only metrics and recommendations.

## Assist

Ask before meaningful changes.

## Auto

Automatically perform safe optimizations.

## Strict

Enterprise policy mode.

---

# 42. Safety Rules

The system must never silently remove high-risk items.

Never automatically discard:

- explicit hard constraints;
- unresolved security issues;
- current requirements;
- active task objective;
- user-marked protected items;
- API contract state;
- compliance requirements.

When confidence is low:

```text
ASK > DELETE
```

---

# 43. Full Product Roadmap

This project should be implemented as a complete product architecture, not a throwaway MVP.

However, implementation must still be phased.

---

## Phase 0 — Foundation

Build:

- project format;
- config system;
- storage;
- event model;
- adapter interface;
- CLI skeleton;
- logging;
- metrics framework.

Deliverable:

```text
cg init
cg status
```

---

## Phase 1 — Context Observer

Build:

- context usage tracking;
- tool-output tracking;
- repository state tracking;
- token estimation;
- context-event stream;
- session state.

Deliverable:

```text
Context telemetry dashboard
```

---

## Phase 2 — Classification Engine

Build:

- semantic context types;
- critical-information extraction;
- importance score;
- relevance score;
- freshness score;
- duplicate detection;
- stale-state detection.

---

## Phase 3 — Smart Pressure Engine

Build:

- adaptive context pressure;
- configurable thresholds;
- 40% review;
- action recommendations;
- predictive pressure.

---

## Phase 4 — Protected Context

Build:

- explicit protection;
- automatic protected classes;
- policy-based protection;
- protected item viewer.

---

## Phase 5 — Context GC

Build:

- duplicate removal;
- tool output pruning;
- terminal output TTL;
- resolved-error cleanup;
- repeated-code detection;
- historical-noise compression.

---

## Phase 6 — Structured Checkpoints

Build:

- semantic checkpoint generation;
- checkpoint persistence;
- checkpoint diffs;
- checkpoint timeline;
- checkpoint restore.

---

## Phase 7 — Semantic Compaction

Build:

- category-specific compression;
- native compaction orchestration;
- safe compression policies;
- archive transitions.

---

## Phase 8 — Integrity Verification

Build:

- pre-compaction fingerprint;
- post-compaction state extraction;
- semantic comparison;
- integrity score;
- missing-item detection;
- automatic rehydration.

This is a flagship milestone.

---

## Phase 9 — Context Branching

Build:

- task branches;
- parking;
- switching;
- restoring;
- merging;
- branch-specific checkpoints.

---

## Phase 10 — Context Time Machine

Build:

- historical state graph;
- restore;
- compare;
- branch history;
- semantic timeline.

---

## Phase 11 — Predictive Context

Build:

- context growth estimation;
- operation-cost prediction;
- proactive compaction;
- future pressure warnings.

---

## Phase 12 — Cross-Agent Runtime

Build:

- normalized context schema;
- handoff packages;
- Codex adapter;
- Claude Code adapter;
- OpenCode adapter;
- agent-specific context policies.

---

## Phase 13 — Multi-Agent Shared State

Build:

- shared tasks;
- role-aware context packages;
- review context;
- implementation context;
- coordination state.

---

## Phase 14 — Advanced Observability

Build:

- task-level context metrics;
- token ROI;
- context-quality trends;
- integrity trends;
- saved-token estimates;
- failure analysis.

---

## Phase 15 — Team Features

Future:

- shared project policies;
- team context state;
- audit logs;
- organization dashboards;
- policy management;
- context ownership.

---

## Phase 16 — Enterprise

Future:

- self-hosted server;
- RBAC;
- SSO;
- retention policies;
- compliance controls;
- encrypted shared context;
- organization analytics.

---

# 44. Business Model

The initial product should be free.

Primary objective:

```text
Adoption
→ trust
→ benchmarks
→ ecosystem
→ category ownership
```

---

# 45. Free Version

Core functionality should remain free:

- local runtime;
- context monitoring;
- pressure engine;
- 40% review;
- protected context;
- semantic checkpoints;
- context GC;
- compaction integrity;
- branches;
- local metrics;
- agent adapters.

This maximizes adoption.

---

# 46. Potential Future Monetization

Do not monetize until the product proves repeat usage.

Potential paid areas:

## Teams

- shared team context;
- synchronized policies;
- project dashboards;
- team analytics;
- shared decisions;
- branch handoffs.

## Enterprise

- centralized governance;
- audit;
- compliance;
- SSO;
- retention;
- self-hosting support;
- security controls;
- organization policies.

## Cloud Sync

Optional:

- encrypted checkpoint sync;
- cross-device task continuation;
- hosted team state.

## Developer Platform

Potential API:

```text
Context Guardian API
```

for other agent products.

---

# 47. Recommended Long-Term Model

Best candidate:

```text
Open Core

Local Runtime:
Free + open source

Cloud/Team Control Plane:
Paid

Enterprise:
Paid
```

This balances:

- trust;
- adoption;
- developer distribution;
- monetization.

---

# 48. Go-To-Market

Initial GTM should be developer-led.

Channels:

- GitHub;
- Hacker News;
- Reddit;
- X;
- developer Discords;
- AI coding communities;
- Claude Code community;
- Codex community;
- OpenCode community;
- YouTube demonstrations;
- technical blog posts.

---

# 49. Launch Message

Do not lead with:

> "AI context optimization platform."

Lead with:

> "Your coding agent forgot the requirement after compacting again."

Then demonstrate:

```text
Before Context Guardian:
- 2 forgotten constraints
- 3 manual reminders
- 128K context usage

After:
- 0 forgotten constraints
- 42K tokens recovered
- context integrity 98%
```

---

# 50. Distribution Strategy

Priority:

1. GitHub repository;
2. one-command install;
3. OpenCode integration;
4. Claude Code integration;
5. Codex integration;
6. agent marketplaces where available;
7. MCP package;
8. plugin ecosystem.

---

# 51. Adoption Principle

Installation must be extremely simple.

Target:

```bash
npm install -g context-guardian
cg init
```

or equivalent package manager.

Then:

```text
Detected:
✓ Codex
✓ Claude Code
✓ OpenCode

Enable adapters?
```

---

# 52. Product Moat

The code itself is not a strong moat.

Potential moat must come from:

## 52.1 Context Policies

Data-driven understanding of which context should survive.

## 52.2 Evaluation System

The best benchmark for coding-agent context reliability.

## 52.3 Cross-Agent Compatibility

One portable context layer.

## 52.4 Integrity Engine

Reliable detection of lost context.

## 52.5 Developer Trust

Local-first and transparent.

## 52.6 Ecosystem

Adapters, community policies, plugins.

---

# 53. Platform Risk

Major risk:

Native agent providers may implement more context management.

Therefore avoid competing on:

```text
"we can summarize context"
```

Build differentiation around:

```text
cross-agent lifecycle
integrity verification
context policy
observability
branching
portability
team governance
```

---

# 54. Competitive Categories

Context Guardian competes indirectly with:

- native agent compaction;
- persistent-memory systems;
- RAG/context systems;
- coding-agent plugins;
- context engineering platforms;
- agent orchestration frameworks.

Examples in the ecosystem include:

```text
Mem0
Zep
Letta
Supermemory
OpenCode memory/context plugins
native Codex compaction
native Claude Code context mechanisms
```

Do not copy their core business.

Integrate when beneficial.

---

# 55. Key Differentiation

Primary category:

> **Live Context Lifecycle Management**

Key differentiation:

```text
Memory systems:
"What should I remember?"

Context Guardian:
"What should the agent know right now?"
```

Second differentiation:

```text
Compaction systems:
"How do I summarize?"

Context Guardian:
"What may safely disappear, and how do we verify nothing important was lost?"
```

---

# 56. Benchmark Strategy

Build a Context Guardian evaluation harness.

Test scenarios:

- large refactor;
- production bug;
- multi-file feature;
- long debugging session;
- task switching;
- branch switching;
- repeated compaction;
- architecture migration;
- multi-agent handoff.

---

# 57. Core Metrics

Measure:

```text
Task completion rate
Critical context loss rate
Forgotten constraints
Tokens consumed
Tokens recovered
Compaction count
Manual reminders
Context integrity
Rehydrations
Context switches
Latency overhead
Agent interruption count
```

---

# 58. North Star Metric

Recommended:

> **Successful coding tasks completed across context transitions without human restatement.**

Alternative:

> **Successful task work per 1K context tokens.**

---

# 59. Required A/B Benchmark

Each evaluation should compare:

```text
Baseline agent
vs
Agent + Context Guardian
```

Example:

```text
100 tasks

Baseline:
Task completion         76%
Forgotten constraints   14
Average tokens          104K

Context Guardian:
Task completion         89%
Forgotten constraints    2
Average tokens           71K
```

Do not publish performance claims without reproducible tests.

---

# 60. Telemetry

Telemetry must be opt-in.

Allowed anonymized metrics:

- context percentages;
- token counts;
- compaction count;
- integrity score;
- GC recovered tokens;
- adapter type;
- feature usage.

Do not collect code by default.

---

# 61. Privacy Principles

Default:

```text
Local first
No source-code upload
No mandatory account
No telemetry without consent
Human-readable local storage
```

Enterprise trust depends on this.

---

# 62. Security

Treat context data as sensitive.

Protect:

- code snippets;
- environment information;
- business requirements;
- credentials accidentally present in context;
- file paths;
- architecture information.

Add secret detection where practical.

Never persist known credentials unnecessarily.

---

# 63. Plugin / Skill Concept

Context Guardian may expose agent-specific skills.

Example:

```text
context-guardian/
  SKILL.md
  adapters/
  policies/
  commands/
```

Skill instructions should tell agents:

1. query current context health;
2. respect protected context;
3. checkpoint before risky compaction;
4. use Guardian retrieval rather than rereading everything;
5. run integrity check after compaction;
6. park inactive tasks;
7. avoid injecting stale context;
8. prefer minimal relevant context.

---

# 64. Agent Behavior Contract

Any integrated agent must follow:

```text
DO NOT:
- blindly compact;
- discard protected state;
- load entire history unless necessary;
- inject conflicting memories without resolution;
- repeatedly load large tool outputs.

DO:
- ask Context Guardian for task state;
- checkpoint before context transitions;
- use targeted retrieval;
- verify state after compaction;
- update task state after significant decisions.
```

---

# 65. Full Acceptance Criteria

The full product is considered functionally complete when:

## Context Management

- context usage is observable;
- pressure is calculated;
- low-value context is detected;
- protected state works;
- stale state is identified;
- semantic classes work.

## Compaction

- checkpoints are generated;
- native compaction can be invoked;
- integrity verification runs;
- missing state can be rehydrated.

## Task Lifecycle

- tasks can be created;
- branches can be parked;
- branches can be resumed;
- state can be rewound.

## Cross-Agent

- at least Codex, Claude Code, and OpenCode adapters work;
- context can be handed between supported agents;
- role-specific context packages can be generated.

## Metrics

- token usage is estimated;
- recovered context is measured;
- integrity is measured;
- task lifecycle metrics are recorded.

## Privacy

- product works without a cloud account;
- no source-code upload is required;
- telemetry is opt-in.

---

# 66. Non-Goals

Do not expand the product into:

- full IDE;
- coding agent;
- autonomous software factory;
- source-control replacement;
- generic team wiki;
- generic knowledge base;
- generic vector database;
- generic chat memory product.

Stay focused on context lifecycle.

---

# 67. Recommended Naming

Current preferred product name:

# Context Guardian

Alternatives:

```text
ContextOS
Context Runtime
Context Keeper
Context Sentinel
Agent Context Engine
```

Context Guardian communicates safety and continuity clearly.

---

# 68. Tagline Options

```text
Your agent can forget. Your context shouldn't.

Never blindly compact again.

Keep the context that matters.

Context integrity for coding agents.

The context runtime for AI coding.
```

---

# 69. Implementation Agent Instructions

The coding agent assigned to this repository must treat this document as the primary product specification.

The agent must:

1. implement the architecture in phases;
2. keep all core systems modular;
3. avoid hard-coding support to one agent;
4. create adapters for agent-specific behavior;
5. maintain local-first defaults;
6. add automated tests for all critical policies;
7. create reproducible benchmarks;
8. document all configuration;
9. preserve backwards compatibility after public release;
10. avoid fake metrics;
11. prefer deterministic behavior for protected/critical state;
12. implement clear failure handling;
13. maintain migration support for stored state;
14. create human-readable checkpoints;
15. maintain a changelog.

---

# 70. Implementation Priorities

Use this priority order:

```text
Reliability
> Context integrity
> Safety
> Agent compatibility
> Low token overhead
> Developer UX
> Performance
> Advanced intelligence
```

Do not optimize intelligence before reliability.

---

# 71. Architecture Quality Requirements

The codebase must:

- use explicit interfaces;
- support plugin adapters;
- isolate storage layer;
- isolate model/provider calls;
- allow local-only operation;
- support unit testing;
- support integration testing;
- support deterministic policy tests;
- avoid vendor-specific logic inside core modules.

---

# 72. Suggested Repository Structure

```text
context-guardian/
├── apps/
│   └── cli/
├── packages/
│   ├── core/
│   ├── context-model/
│   ├── pressure-engine/
│   ├── classifier/
│   ├── gc/
│   ├── checkpoint/
│   ├── integrity/
│   ├── retrieval/
│   ├── policies/
│   ├── storage/
│   ├── git/
│   ├── metrics/
│   └── adapters/
│       ├── codex/
│       ├── claude-code/
│       └── opencode/
├── benchmarks/
├── fixtures/
├── docs/
├── examples/
└── tests/
```

---

# 73. Testing Requirements

Required tests:

## Unit

- pressure score;
- policy decisions;
- classification;
- duplicate detection;
- protection;
- staleness;
- conflict detection;
- checkpoint generation;
- integrity comparison.

## Integration

- Codex lifecycle;
- Claude Code lifecycle;
- OpenCode lifecycle;
- pre/post compaction;
- task switching;
- branch restore.

## Regression

Every discovered context-loss failure must become a regression test.

---

# 74. Performance Targets

Initial targets:

```text
Context Guardian overhead:
< 5% of total agent token usage

Local decision latency:
< 250 ms where no LLM call is needed

Checkpoint generation:
< 3 seconds target

Integrity verification:
< 5 seconds target

No blocking cloud dependency
```

These may be revised based on real testing.

---

# 75. Intelligence Cost Control

Do not use a large model for every context operation.

Recommended hierarchy:

```text
Rules / heuristics
↓
local parsing
↓
embeddings / semantic similarity
↓
small model
↓
large model only when ambiguity requires it
```

The context manager must not become the largest source of token usage.

---

# 76. Policy Learning

Future:

Context Guardian may learn from:

- user corrections;
- restore events;
- missed-context incidents;
- branch switches;
- context items repeatedly rehydrated;
- items never used again.

Example:

```text
If a developer repeatedly restores architecture decisions,
increase architecture retention score.
```

Learning must remain transparent and resettable.

---

# 77. Community Strategy

If open source:

Encourage:

- adapter contributions;
- context policy packs;
- benchmark scenarios;
- integration plugins;
- language-specific context extractors.

Potential repository areas:

```text
community/adapters/
community/policies/
community/benchmarks/
```

---

# 78. Ecosystem Strategy

Possible future integrations:

- MCP;
- GitHub;
- GitLab;
- IDEs;
- CI;
- issue trackers;
- documentation platforms.

Do not integrate everything early.

Focus on coding-agent lifecycle first.

---

# 79. Product Success Stages

## Stage 1 — Technical Proof

Goal:

```text
Can we reduce context loss?
```

## Stage 2 — Developer Retention

Goal:

```text
Do users keep it installed?
```

## Stage 3 — Cross-Agent Value

Goal:

```text
Does portability make users depend on it?
```

## Stage 4 — Team Value

Goal:

```text
Will teams share context policies/state?
```

## Stage 5 — Category Ownership

Goal:

```text
Does "context management" become associated with Context Guardian?
```

---

# 80. Kill Criteria

The product thesis should be reconsidered if controlled tests show:

- negligible context-loss improvement;
- token overhead greater than savings;
- developers strongly prefer native agent behavior;
- integrity verification produces excessive false alarms;
- agent APIs do not expose enough lifecycle control;
- cross-agent state provides little practical value.

Do not continue based purely on enthusiasm.

---

# 81. Strongest Product Wedge

The recommended initial wedge is:

> **Compaction Integrity for long-running coding-agent sessions.**

User-facing experience:

```text
Context 43%

Guardian found:
14 critical decisions
6 active files
3 unresolved issues

Safe cleanup:
12.4K tokens

After compaction:
Integrity 100%

Nothing critical lost.
```

This communicates value immediately.

---

# 82. Full Strategic Direction

The product should evolve through this progression:

```text
Smart 40% Review
       ↓
Context Pressure Engine
       ↓
Protected Context
       ↓
Semantic Checkpoints
       ↓
Compaction Integrity
       ↓
Context GC
       ↓
Task Branches
       ↓
Context Time Machine
       ↓
Predictive Management
       ↓
Cross-Agent Context
       ↓
Multi-Agent Shared State
       ↓
Team Context Control Plane
```

---

# 83. Final Product Definition

Context Guardian is a **local-first context runtime for AI coding agents**.

It continuously observes working context, scores context pressure, identifies valuable and disposable information, protects critical project state, creates structured checkpoints, coordinates compaction, verifies context integrity, restores lost state, manages task branches, and enables context portability between coding agents.

Its long-term purpose is to make context a managed engineering resource instead of an accidental side effect of conversation history.

---

# 84. Final Principle

Every product decision should answer this question:

> **Does this help the agent retain the right information for the current engineering task while reducing unnecessary context?**

If the answer is no, the feature probably does not belong in Context Guardian.

---

# 85. One-Line Product Description

> **Context Guardian is the context runtime that keeps AI coding agents focused, efficient, and state-consistent across long sessions, compactions, task switches, and agent handoffs.**

