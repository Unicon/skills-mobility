---
name: design-writer
description: Interactive authoring or review of a docs/3_design/<component>.md doc for this repo, with the user in the loop. Use when asked to design, draft, review, refine, or scope how a component should be built. Dispatches the software-architect, surfaces its questions to the user, folds the answers back in, and produces a design doc following the pattern in .claude/design-template.md. Advisory: does not modify docs or code unless asked and approved.
---

# Design writing and review

Turn an approved requirements doc (or an existing design draft) into a solid
`docs/3_design/<component>.md`, with the user in the loop. The `software-architect` does
the deep work: constraints, alternatives, and one recommended approach, drafted in the
established pattern. The clarification loop is what makes this more than a one-shot
pass: the architect surfaces questions whose answers would actually change the design,
you relay those to the user, get answers, and continue the architect with that new
information before finalizing.

Read `.claude/design-template.md` first — it describes the recurring section pattern
already in use, derived from the existing docs. Also read `docs/3_design/README.md` for
the live conventions and `docs/3_design/poc-component-boundaries.md` for current
component boundaries and naming, and `.claude/architecture-overview.md` for system
grounding (especially the ADR-0007/ADR-0011 contracts if the component touches an LLM
Decision Service or the orchestrator).

This is advisory. It produces drafted doc text; it doesn't write to `docs/` or code
unless the user asks and approves. When approved, write directly to
`docs/3_design/<component>.md` and update `docs/3_design/README.md`'s Contents table.

## Model and orchestration

You, the main session on the strong model, orchestrate. Dispatch the `software-architect`
with the Agent tool and **no `model` override**; it pushes its own context-heavy reading
to cheaper sub-agents (`Explore` on Haiku for location, Sonnet for read-and-reason and
web). Do not read large docs or run web lookups inline.

The agent is a sub-agent and **cannot talk to the user**. Every question it raises comes
back in its output, and you broker it: collect, prioritize, ask the user with
`AskUserQuestion`, then continue the agent with the answers via `SendMessage`. Keep its
agent id from the Agent tool so you can continue it.

## 1. Intake

Identify what you're working from:

- The component's requirements doc (`docs/2_requirements/<component>.md`) — read it in
  full; the design must satisfy it. If it doesn't exist yet, say so and suggest the
  `requirements-writer` skill runs first — designing without settled requirements just
  produces rework.
- An existing design draft, if reviewing/refining one.
- Neighboring design docs the component integrates with, and
  `docs/3_design/poc-component-boundaries.md` for boundary/naming alignment.
- Every ADR the requirements doc links to, plus any others the design will need to
  respect (module dependency rules, the orchestration runtime contract if this component
  is a step the orchestrator invokes).

If there's no requirements doc and no existing design draft to review, say so and stop.

## 2. Design pass (software-architect)

Dispatch the `software-architect` agent with an excellent, self-contained prompt: the
requirements doc verbatim, the neighboring design docs, and the relevant ADRs. Ask it to
return, grounded in the actual repo:

- **Constraints and forces**: what the requirements doc and existing ADRs already
  settle, and what's still open.
- **Genuine alternatives** (at least two or three) with tradeoffs, and one recommended
  approach — reuse before rebuild, simplest correct design for a POC.
- **A draft of the doc** following `.claude/design-template.md`'s recurring sections:
  Overview, Phase Split if applicable, flow sketch, Contracts (with concrete JSON
  examples where relevant), Logical Modules, Execution Flow, State and Storage, Local vs
  AWS if applicable, Testing, Build Order.
- **Architecture risks**: a change to the LLM/deterministic-validation contract, a
  module-boundary crossing, a new AWS resource needing CloudFormation (ADR-0003,
  revised — CDK was superseded), a warranted new ADR.
- **OPEN QUESTIONS for the human**, prioritized, same format as the requirements-writer
  skill: `[BLOCKING|non-blocking] <crisp question> (why it matters: <one line>). Options: A) … B) … [recommended: X]`.

Keep its agent id. Reason over its summary; don't redo its reading.

## 3. Clarify with the user (loop)

Same loop as `requirements-writer`: batch blocking questions through `AskUserQuestion`
(up to four per call, recommended option first), continue the architect via `SendMessage`
with the answers, cap at ~2 rounds, and record any residual unknown as an explicit open
question or a build-order step gated on a decision, rather than guessing.

## 4. Present

Verdict first: the recommended approach and why, against the alternatives considered (one
line each for the rejected ones); the drafted doc in the canonical pattern; architecture
risks and any ADR that should exist but doesn't yet (name it and offer to draft it in
Proposed status — see `.claude/architecture-overview.md` for the current ADR governance
state before treating an existing ADR as immutable); remaining open questions.

Write to `docs/3_design/<component>.md` and update the README index only on explicit
request and approval of the wording.
