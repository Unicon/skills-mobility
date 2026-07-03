# Requirements doc conventions

This is a description of the pattern already in use under `docs/2_requirements/` — not
a rigid mandatory form. Section numbers and names vary by component complexity (compare
`orchestrator.md` against a thinner adapter doc); match the weight of the doc to the
weight of the component, and read a neighboring doc for a similar component before
writing a new one. The `requirements-writer` skill and the `business-analyst` agent use
this to draft or review a requirements doc.

Full conventions live in `docs/2_requirements/README.md` — read it first. This file
exists to save re-deriving the section skeleton from example docs each time.

## Header block

```
# <Component> Requirements

Status: Draft
Date: YYYY-MM-DD
Related: [Requirements overview](./README.md) · [Design](../3_design/<component>.md) · [ADR-XXXX](../decisions/XXXX-....md) · ...
```

`Status` starts `Draft`. Per `docs/decisions/README.md`'s convention (also being
reconciled into `AGENTS.md` — see `.claude/architecture-overview.md`), a superseded
requirements doc gets `Status: Superseded` and moves to `2_requirements/archive/`; it
does not get deleted or silently rewritten past recognition.

`Related` links both directions: back to the requirements index, sideways to the
component's design doc, and to every ADR whose decision the requirements depend on.
Reference an ADR rather than restating its content.

## Recurring sections

Observed across existing docs (`orchestrator.md`, `context-builder.md`,
`event-consumer.md`, and the `mock-lms-*` / `learncard-*` docs), roughly in this order:

1. **Purpose** — one paragraph: what this component is and its role in the workflow.
2. **Responsibilities** — two lists: what the component *is* responsible for, and what
   it explicitly is *not* (owned by a neighboring component instead). The "not
   responsible for" list is what keeps boundaries legible — don't skip it.
3. **Inputs and Outputs** — what it receives and from where; what it produces and to
   where.
4. **Phase scope** (when the component is being built incrementally — most are, per
   `docs/2_requirements/phase-1-poc-slice.md`) — a numbered walkthrough of the current
   phase's happy-path flow, and what's deferred to a later phase. Say explicitly which
   seams are preserved even when the current phase stubs them out, so the phase slice
   doesn't collapse into a dead-end flow.
5. **Functional Requirements** — numbered `FR-<COMPONENT>-N`, one requirement per bullet,
   RFC-2119-style normative language (SHALL / SHALL NOT / MAY). Split into sub-sections
   when one dimension deserves its own grouping (e.g. "Validation and Audit
   Requirements", "Local vs AWS Requirements") rather than one flat list.
6. **Out of Scope** — a bullet list of things this component's *initial* implementation
   does not need to provide. This is where POC scope discipline gets written down
   concretely per-component, in addition to the project-wide list in `AGENTS.md`.

Not every doc needs every section (a thin adapter doc doesn't need a "Local vs AWS"
split if there's only one deployment target) — match `docs/3_design/poc-component-boundaries.md`'s
scope for the component and don't pad.

## What "good" looks like

- Every SHALL is testable — a reviewer could point at code or a test and say yes/no.
- "Not responsible for" is as concrete as "responsible for."
- Phase scope names which seams are preserved so a later phase isn't a rewrite.
- Out of Scope calls out anything a reader might reasonably expect but that this
  component's current phase doesn't provide.
- Links to the design doc and every load-bearing ADR are present and correct.
