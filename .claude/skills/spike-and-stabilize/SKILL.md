---
name: spike-and-stabilize
description: Incremental coding methodology for non-trivial tasks in this repo. Survey the code, get one combined clarify-and-plan approval, write a thin throwaway spike, then stabilize it (types, tests, lint, review). Skip the flow for trivial tasks like renames, typo fixes, and one-liners.
---

# Spike & Stabilize

This skill is a *process* wrapped around `AGENTS.md`'s existing behavioral rules (stop
and ask when uncertain, simplicity first, surgical changes, test-driven execution) — it
doesn't replace them. For every non-trivial task, run these four steps in order. Don't
reorder, skip, or merge them; if a step doesn't apply, say why and move on.

1. Recon
2. Clarify and plan (one approval gate)
3. Spike
4. Stabilize

## Trivial escape hatch

Skip the flow for obviously trivial work: renames, typo fixes, one-line changes, import
tweaks. Say "Trivial: <reason>", make the fix, run one relevant check
(`uv run pytest <path>` or `npm run build`), present the result. "Small" or
"well-understood" is not trivial; only the absence of business logic and branching is.

## 1. Recon

Before touching code, get a high-level map, then narrow to the few files that matter.
Delegate broad searches to an `Explore` sub-agent (Haiku for plain location, Sonnet when
it must reason about behavior) so file dumps stay out of the main context. Read into your
own context only the specific files the task touches. Report back:

- Existing patterns for similar work, with file paths (e.g. how `services/mock-lms` or
  `services/orchestrator` structure their FastAPI app, tests, and fixtures).
- Reusable code the work can build on (`libs/events`, existing helpers) — reuse before
  rebuild.
- Where new code should live, respecting the module dependency rules in `AGENTS.md`
  (`apps/` → `packages/` only; `services/` → `libs/` only, never another service
  directly; `libs/` depends on neither).
- Conflicts and surprises: a component with requirements/design docs but no merged
  implementation yet (this project moves fast with many open PRs — check `ls
  services/<component>/src` and `gh pr list` rather than assuming a docs-described
  component is implemented, merged, or absent), naming drift, an ADR that already
  settled the question.

Use the findings to answer your own questions before asking the developer.

## 2. Clarify and plan

Do the clarify-and-plan work in plan mode (`EnterPlanMode`). Ask focused questions with
`AskUserQuestion` (2-4 options each), then present a short plan. Do not write any
implementation code, including illustrative snippets, until the developer approves the
plan via `ExitPlanMode`.

- Enumerate edge cases yourself and propose handling — but keep them proportionate to a
  POC (`AGENTS.md`: "skip elaborate edge-case testing... be reasonable, not exhaustive").
  Async/event ordering, idempotency, and JSONata mapping edge cases are the usual traps
  here.
- Present options when interpretations differ; don't pick silently.
- Zero questions is fine when recon resolved it: confirm your assumptions and proceed.
- For a significant, hard-to-reverse decision (new dependency, a change to the LLM
  Decision Service contracts, a new module boundary, an AWS resource shape) that's new,
  draft an ADR in Proposed status under `docs/decisions/` and name it in the plan. If
  it's an existing decision evolving, amend the existing ADR in place instead — that's
  the team's actual practice (see `.claude/architecture-overview.md` for the current
  state of the governance convention), not a new ADR every time something changes.

On plan approval, delegate the implementation to a `general-purpose` sub-agent on Sonnet
via the Agent tool. Brief it with the approved plan, the target files, and the
conventions to follow (this repo's style, `AGENTS.md`'s rules). Stay on the strong model
to run the gates and do the final review; don't write the code yourself.

## 3. Spike

Have the implementation sub-agent write the thinnest vertical slice that does something
real end-to-end. Rough is fine. Brief it with these rules:

- Happy path only; defer error handling and edge cases.
- Loose types where the shape is unclear; tighten later.
- Hard limit ~50 lines. If it doesn't fit, narrow the scope, don't raise the cap.
- Mark it `# SPIKE: shape not final`.
- Before writing logic that already exists elsewhere (`libs/events`, an existing
  service's helpers), reuse it or say why it doesn't fit.

Show the developer the result and confirm the shape before stabilizing.

## 4. Stabilize

Once the shape is confirmed, add no new features. Hand the same sub-agent (continue it
via `SendMessage` so it keeps context) these steps in order:

1. Tighten types: full annotations, Pydantic models where the shape crosses a boundary
   (API request/response, event payload), matching `mypy --strict`.
2. Write tests: one per behavior, not per function — "what would tell me this works?"
   Unit tests do the bulk of the work per the testing pyramid; add an API test via
   FastAPI's `TestClient` if the change touches an endpoint.
3. Run checks until clean: `uv run ruff check .` (and `--fix` where safe), `uv run mypy
   libs/*/src services/*/src`, targeted `uv run pytest <path>` for the affected package,
   `npm run build` for any `apps/` change. Never suppress a check to go green.
4. Apply the rule of three: don't extract shared code until a third caller needs it.
5. Report: what's covered, which checks ran clean, what's next.

As the final step, you (the strong main model, not the sub-agent) run the `code-review`
skill on the diff. Fix anything it flags as wrong before the change is done, then run
through `AGENTS.md`'s pre-completion checklist explicitly.

## Expand

For the next increment, repeat the clarify-and-plan gate unless it's trivial. Pause and
confirm before significant complexity: a new dependency, a change to an LLM Decision
Service's inputs/outputs or the orchestrator's plan contract, a new module boundary, or
any ambiguity recon left open.

## When blocked

If the next step is low-confidence and high-cost, stop. Summarize what's not working,
give 2-3 options, and ask which path to take. Don't keep guessing.
