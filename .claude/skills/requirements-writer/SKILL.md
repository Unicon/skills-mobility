---
name: requirements-writer
description: Interactive authoring or review of a docs/2_requirements/<component>.md doc for this repo, with the user in the loop. Use when asked to write, draft, review, refine, or scope a component's requirements. Dispatches the business-analyst, surfaces its questions to the user, folds the answers back in, and produces a requirements doc following the pattern in .claude/requirements-template.md. Advisory: does not modify docs unless asked and approved.
---

# Requirements writing and review

Turn a rough component idea, an existing draft, or a "what should this component do"
question into a solid `docs/2_requirements/<component>.md` doc, with the user in the
loop. The `business-analyst` does the deep work: recovering true intent, checking scope
against `AGENTS.md`'s POC boundaries, and drafting in the established pattern. What makes
this different from a one-shot pass is the clarification loop: the analyst surfaces
questions whose answers would actually change the doc, you relay those to the user, get
answers, and continue the analyst with that new information before finalizing.

Read `.claude/requirements-template.md` first — it describes the recurring section
pattern already in use, derived from the existing docs, not an invented format. Also read
`docs/2_requirements/README.md` for the live conventions and index, and
`.claude/architecture-overview.md` for system grounding.

This is advisory. It produces drafted doc text; it doesn't write to `docs/` unless the
user asks and approves the wording. When approved, write directly to
`docs/2_requirements/<component>.md` and update `docs/2_requirements/README.md`'s
Contents table (and, if the component is new, note that a design doc is a natural
follow-up — see the `design-writer` skill).

## Model and orchestration

You, the main session on the strong model, orchestrate. Dispatch the `business-analyst`
with the Agent tool and **no `model` override**, so it inherits your model; it pushes its
own context-heavy reading down to cheaper sub-agents (`Explore` on Haiku for location,
Sonnet for read-and-reason). Do not read large docs or run web lookups inline.

The agent is a sub-agent and **cannot talk to the user**. Every question it raises comes
back in its output, and you broker it: collect, prioritize, ask the user with
`AskUserQuestion`, then continue the agent with the answers via `SendMessage` (which
preserves its context). Keep its agent id from the Agent tool so you can continue it.

## 1. Intake

Identify what you're working from:

- An existing doc: read it. A component name with no doc yet: treat it as a request to
  draft one from scratch.
- Read the component's neighbors for calibration: a similar-weight existing requirements
  doc (thin adapter vs. a central component like the orchestrator), so the new doc's
  weight matches its actual complexity rather than defaulting to maximal detail.
- Check `docs/3_design/poc-component-boundaries.md` for how this component's boundaries
  are currently named, so the requirements doc uses consistent terminology.
- Check whether a design doc already exists for this component (`docs/3_design/<component>.md`)
  — if so, the requirements doc should be consistent with it, not contradict it; flag any
  mismatch rather than silently picking one side.

If there's nothing to draft from and no clear component to scope, say so and stop.

## 2. Requirements pass (business-analyst)

Dispatch the `business-analyst` agent with an excellent, self-contained prompt: the
existing doc or component description verbatim, the neighboring docs you gathered, and
the ADRs already known to bear on it. Ask it to return, grounded in the actual repo:

- **True intent and scope**: the real role(s) this component serves, and whether the
  request drifts into `AGENTS.md`'s explicitly out-of-scope territory or otherwise
  gold-plates past what the current phase needs.
- **Findings**, grouped and anchored: Missing / Open question / Contradiction (with an
  existing ADR or the design doc) / Out-of-scope / Improvement.
- **A draft of the doc** following `.claude/requirements-template.md`'s recurring
  sections — Purpose, Responsibilities (including "not responsible for"), Inputs and
  Outputs, Phase scope if applicable, Functional Requirements (numbered, SHALL/MAY
  language), Out of Scope.
- **OPEN QUESTIONS for the human**, prioritized, formatted as:
  `[BLOCKING|non-blocking] <crisp question> (why it matters: <one line>). Options: A) … B) … [recommended: X]`
  Only questions whose answer would actually change the doc, 2-4 candidate answers each
  with a recommended default.

Keep its agent id. Reason over its summary; don't redo its reading.

## 3. Clarify with the user (loop)

If the analyst raised blocking questions:

1. Merge and dedupe, blocking first.
2. Ask the user with `AskUserQuestion`: up to four per call, batching across calls if
   more. Map each question to one item: the text, a short `header`, and the analyst's
   candidate answers as options with the recommended one first, labeled "(Recommended)."
   Don't add an "Other" option; the tool always offers free text.
3. Continue the analyst via `SendMessage` with the user's answers. Ask it to fold them in
   and raise any *new* blocking question the answers created.
4. Repeat only while new blocking questions appear, capped at ~2 rounds; treat any
   residual unknown as an explicit open question in the doc rather than interrogating
   further, or mark that requirement as deferred to a later phase.

If the user defers a decision, don't guess: state the open question plainly in the doc
rather than picking an answer.

## 4. Present

Verdict first: the true-intent summary and scope read (in POC scope, or which
out-of-scope boundary it brushes against); the drafted doc in the canonical pattern;
findings (Missing / Open question / Contradiction / Out-of-scope / Improvement); any
remaining open questions. Note explicitly if a design doc doesn't yet exist for this
component — that's the natural next step (`design-writer` skill), not something this
skill should attempt itself.

Write to `docs/2_requirements/<component>.md` and update the README index only on
explicit request and approval of the wording.
