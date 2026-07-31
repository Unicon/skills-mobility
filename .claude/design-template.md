# Design doc conventions

This is a description of the pattern already in use under `docs/3_design/` — not a rigid
mandatory form. Section numbers and names vary by component complexity; match the weight
of the doc to the component (compare `orchestrator.md`, which is large because it owns
the plan contract, against a thinner adapter doc). The `design-writer` skill and the
`software-architect` agent use this to draft or review a design doc.

Full conventions live in `docs/3_design/README.md` — read it first, and read
`docs/3_design/poc-component-boundaries.md` for current component boundaries and naming
before writing a new design doc, so terminology stays aligned across components.

## Header block

Same shape as the requirements doc: `Status: Draft`, `Date`, and a `Related` line linking
back to the requirements counterpart (`docs/3_design/README.md`: "design docs match their
requirements counterparts... and stay cross-linked"), to neighboring component design
docs it integrates with, to `poc-component-boundaries.md`, and to every ADR whose
decision the design implements.

## Recurring sections

Observed across existing docs (`orchestrator.md`, `context-builder.md`,
`delivery-router-service.md`, the `learncard-*` adapter docs), roughly in this order —
use only the sections a given component needs:

1. **Overview** — a short table (`Part | Expected path | Tech | Role`) naming the real
   repo path the implementation lives at, plus a paragraph on the core design constraint.
2. **Phase Split** — a table (`Concern | Phase 1 | Target POC`) when the component is
   built incrementally, naming exactly what's stubbed now vs. what the target behavior
   is, per concern. This is the design-side counterpart to the requirements doc's Phase
   scope section — keep them consistent.
3. **Recommended shape / flow** — an ASCII or Mermaid sketch of the call/data flow.
4. **Contracts** — the concrete shapes this component owns: request/response schemas,
   plan or artifact JSON shapes, state machines. Use realistic JSON examples, not
   abstract descriptions — the orchestrator design doc's plan-shape examples are the
   model to follow. Name which ADR the contract implements (e.g. plan shape per
   ADR-0011).
5. **Logical Modules** — a bullet list of the internal module breakdown, matching the
   real or intended `src/<package>/` layout.
6. **Execution Flow** — numbered step-by-step walkthrough(s) of the component's main
   path(s) (e.g. planner path / executor path), concrete enough to build directly from.
7. **State and Storage** — states (as an enum list), the minimum persisted fields per
   artifact, and the storage rule of thumb (what's inline vs. out-of-line/referenced).
   Cite the storage ADR (currently ADR-0014) rather than re-deciding storage strategy.
8. **Local vs AWS** — a table of what differs by environment when a component has both a
   local dev shape and an AWS-shaped target; state explicitly that the *logical*
   contract doesn't change, only the transport.
9. **Testing** — a bullet list of test types this component needs (unit / API /
   integration with fakes / e2e), matching the testing pyramid in `AGENTS.md`. State
   what routine tests should *not* require (e.g. "should not require live LearnCard
   access").
10. **Build Order** — a numbered sequence for implementing the component incrementally,
    schema/contract first, before the full action registry or AWS adapters.
11. **Implementation Decisions** — concrete choices pinned for this component's build
    (library selection, model choice, storage mechanism) where the design leaves genuine
    freedom. Content is component-specific — carry over only what's actually relevant (a
    library choice like `jsonata-python` won't apply outside Field Mapping, but the other
    services might have relevant libraries of their own). When pinning a Bedrock model
    choice, defer to the live model catalog at implementation time rather than hardcoding
    a specific model ID, so the doc doesn't go stale as models change.

## What "good" looks like

- Every contract shown has a concrete example, not just a prose description.
- The Phase Split table and the requirements doc's Phase scope section tell the same
  story from two angles (design mechanics vs. functional behavior) without contradicting
  each other.
- Local vs AWS differences are named as transport-only, not logical-contract changes.
- Build Order gives a developer (or coding agent) an actual sequence to follow, not just
  a feature list.
- Every design choice traces to an ADR or is flagged as a new decision that needs one.
