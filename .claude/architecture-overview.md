# Architecture overview

Durable context for the `software-architect` and `business-analyst` subagents and the
`requirements-writer`/`design-writer`/`code-review`/`spike-and-stabilize` skills. This is
a grounding reference, not a policy document — `AGENTS.md` remains the source of truth
for behavioral rules, tech stack, and conventions.

This POC moves fast (single team, ~6-week timeline, commonly 15-20+ open PRs at once).
Anything that changes at that pace does **not** belong hand-copied into this doc as a
frozen snapshot — it'll be stale before the next session. This doc sticks to what's
genuinely stable (the architectural spine, the foundational Accepted ADRs) and points to
live sources for everything else. When in doubt, re-derive from the repo rather than
trust a table here.

## The shape of the system

Learner/credential events flow: **Event Consumer** ingests an event → **Orchestrator**
runs the plan (gated by two Workflow Actions stages and informed by the Delivery Targets
and Transformation Mappings LLM Decision Services) → validated steps deliver transformed
credentials to **LearnCloud/LearnCard** and **SmartResume**. Every LLM decision is paired
with deterministic **Policy Rules Service** validation before anything executes, and a
complete audit trace is recorded. This LLM-reasoning-plus-deterministic-validation
contract is the architectural spine of the project (`AGENTS.md`, ADR-0007, ADR-0011 §9)
— never let LLM output flow straight to delivery. Treat any change that weakens this
pairing as a bug, not a style preference, regardless of how the change is phrased.

## Checking current state — don't trust a snapshot

Given the pace of work, this doc does not maintain a "what's implemented" table. Check
live instead:

- **What's merged**: `ls services/ apps/ libs/` on the current branch, or `git log
  --oneline main` for what's landed. A component with a `docs/2_requirements/` or
  `docs/3_design/` doc is not necessarily implemented yet — docs are often written and
  merged ahead of the implementation PR.
- **What's in flight**: `gh pr list` — a large fraction of real work lives in open PRs at
  any given time on this project. Before assuming a component doesn't exist, check open
  PRs, not just `main`.
- **What's intended**: `docs/2_requirements/README.md` and `docs/3_design/README.md`'s
  own Contents tables are the maintained, current index of components — more complete and
  more current than anything this file could cache. Read those directly.
- **What's decided**: `docs/decisions/README.md`'s index, and each ADR's own `Status:`
  line (not just the index table — see the flagged discrepancy below).

## ADRs — the architectural spine

Full, current index: `docs/decisions/README.md`. Don't rely on a copied list here; ADRs
are added and amended faster than this doc gets updated (16+ at last check, and growing).
Three are genuinely foundational and worth knowing by number because the rest of the
system assumes them:

- **ADR-0007** — decomposes "the LLM Decision Service" into three: Delivery Targets,
  Workflow Actions, Transformation Mappings. Delivery Targets must resolve *before*
  Transformation Mappings (hard sequencing dependency).
- **ADR-0009** — Workflow Actions is two-stage hierarchical: Stage 1 pre-target gate
  (terminate vs. continue) before Delivery Targets; Stage 2 delivery-phase planning after
  Delivery Targets.
- **ADR-0011** — a project-internal orchestration service is the plan executor, not AWS
  Step Functions (Step Functions may still appear as edge plumbing, never as the
  authoritative workflow model).

## ADR-0007 and ADR-0011, in depth

These two are cited often enough by the subagents that it's worth having their contracts
on hand — but they can still be amended in place, so verify against the live file before
treating a specific field name or rule as unchanged.

**ADR-0007 (LLM Decision Service Decomposition).** Three services, not one monolithic
call, because each has different inputs, prompt strategy, confidence profile, and failure
modes — one prompt carrying all three degrades quality and complicates iteration/
testing/audit. Revisit triggers: multi-call overhead becomes unacceptable with equivalent
quality achievable via a combined approach; the three decisions turn out to share enough
context for one prompt; or the Delivery-Targets→Transformation-Mappings sequencing causes
unacceptable latency.

**ADR-0011 (Orchestration Runtime Technology).** Rejects Step Functions because ADR-0009's
two-stage hierarchical model means the workflow structure is generated at runtime by an
LLM, not known ahead of time — a poor fit for predefined state machines. Ranked fallback
if the internal runtime proves insufficient: Temporal (strongest candidate), Conductor,
Camunda, Step Functions, Dagster/Airflow — a migration should preserve the same abstract
plan contract, not redesign the orchestration model. Key contracts:

- **Versioned Action Registry** — each action needs `action_id`, a human-readable
  description (exposed to the Workflow Actions prompt), an implementation/adapter
  binding, input/output schemas, idempotency requirements, default timeout/retry,
  side-effecting flag, iteration-eligibility flag. **The LLM must never choose raw URLs,
  Lambda names, queue names, credentials, or arbitrary code to run** — only registry
  `action_id`s.
- **Plan shape** — a declarative, engine-neutral abstract plan. Minimum fields:
  `plan_schema_version`, `plan_id`, `generated_at`, `generator`, `applicability`,
  `confidence`, `rationale`, ordered `steps` (each with `step_id`, `type`
  [`call`|`wait`|`for_each`|`terminate`], `action_id`, `condition`, `inputs`, `produces`,
  `timeout`, `retry_policy`, `on_failure`, `metadata`). **No arbitrary Python/JavaScript
  execution in generated plans.**
- **Plan reuse** — only delivery-phase plans (never pre-target gate decisions), only
  post-Policy-Rules-validated plans; re-validate reused plans before execution; record
  generated-vs-reused in the audit trail.
- **Audit/trace minimum fields** — event id, workflow execution id, correlation id,
  pre-target gate outcome, selected delivery targets, selected/generated plan id + schema
  version, Workflow Actions model/prompt version, plan confidence/rationale, Policy Rules
  validation result, per-step inputs/outputs/attempts/timings/outcomes, downstream
  delivery results, final workflow outcome.
- **Explicit non-goals** — the LLM cannot invent new executable actions at runtime; no
  arbitrary loops/graph mutation; no mid-flight replanning after delivery-phase execution
  begins in v1; this does not replace Policy Rules; not a general job scheduler.

`docs/2_requirements/orchestrator.md` and `docs/3_design/orchestrator.md` show this
contract applied concretely, including the Phase 1 stubbed version — read those for the
current, most-detailed version rather than treating this summary as complete.

## Flagged: ADR-0010 status discrepancy

`docs/decisions/0010-llm-model-access-strategy.md`'s own `Status:` line may say
"Proposed" while `docs/decisions/README.md`'s index table says "Accepted" (or vice versa
— check both, this kind of drift is exactly what this project's ADR governance PRs are
addressing). Don't treat its Bedrock/structured-output requirements as fully settled
without checking the live file.

## ADR governance: amend-in-place (ADR-0019)

ADRs are living documents during the POC: edit in place for clarifications, and for a
reversal of an accepted decision, keep it visible — update `Status`, add a `Supersedes:`
header, and keep the prior option under "Options Considered." See ADR-0019
(`docs/decisions/0019-adr-governance-and-lifecycle.md`) and `AGENTS.md`'s Git & PR
conventions section, both of which now state this convention directly.

## Requirements & design doc conventions

No GitHub issue template or ticket-tracking convention exists in this repo (no
`.github/` directory, no `CONTRIBUTING.md`) — work items live as docs, not tickets. The
real conventions:

- `docs/2_requirements/README.md` and `docs/3_design/README.md` — the live indexes and
  conventions, one doc per component, requirements and design cross-linked.
- `.claude/requirements-template.md` and `.claude/design-template.md` — the recurring
  section pattern observed in the existing docs (derived from them, not invented), used
  by the `requirements-writer` and `design-writer` skills.
- `docs/2_requirements/poc-requirements.md` (preserved stakeholder baseline) vs.
  `docs/2_requirements/target-poc-requirements.md` (the evolving working requirements) —
  two intentionally separate docs; don't rewrite the former when the latter changes.
