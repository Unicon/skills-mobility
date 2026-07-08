# 0019. ADR Governance and Lifecycle: Living Documents with Visible Reversals

- Status: Proposed
- Date: 2026-06-29
- Related: [ADR-0001](./0001-repo-structure.md)

## Context

The repository currently gives two contradictory instructions for how ADRs are maintained:

- `docs/decisions/README.md` (Conventions): *"ADRs in this repo are maintained **in place**. When a decision evolves, update the existing ADR so it stays coherent with the current architecture and index."*
- `AGENTS.md` (Git & PR conventions): *"ADRs are immutable history — supersede, don't rewrite."*

Actual practice has followed the README: ADR-0009 was rewritten in place (peer/hierarchical → two-stage hierarchical), ADR-0011 was edited to match, and the Field Mapping PR (#27) edits ADR-0005/0007/0008/0010/0013. The contradiction surfaced as review friction on #25 (ADR-0009 rewritten rather than superseded) and again on #26 (Admin UI), where the question was raised explicitly. We need one rule both documents point to.

The underlying tension is real: editing in place keeps a fast-moving POC's ADRs coherent (a reader sees the *current* decision, not a chain of supersessions to reconstruct), but it can also silently erase the prior decision and its rationale — which is the whole point of an ADR.

## Decision Drivers

- Keep ADRs coherent and low-ceremony while the POC is pre-implementation and decisions are still moving.
- Don't silently lose a decision that was reversed — the prior rationale should remain discoverable.
- Resolve the README ↔ AGENTS.md contradiction with a single source of truth.
- Match what the team is already doing, rather than impose a process no one follows.

## Decision

**During the POC, ADRs are living documents and MAY be edited in place.** The strict "immutable, supersede-only" rule is relaxed for this phase. To keep that from erasing decision history, edits are governed by their kind:

1. **Clarifications, corrections, and elaborations** (typo fixes, wording, added detail, updating links, reconciling with a newer ADR) — edit in place freely. Git history is sufficient provenance; no ceremony required.

2. **Reversing or materially changing an accepted decision** — edit in place, but make the change visible:
   - keep the `Status` line current (`Proposed` → `Accepted` → `Superseded`/`Deprecated`),
   - add a header line recording what changed and when — `Supersedes: the <date> <short description> decision` (the pattern ADR-0009 already uses), and
   - preserve the prior option in **Options Considered** (marked e.g. *"accepted <date>, superseded by this revision"*) so the reasoning isn't lost.
   A net-new ADR that supersedes the old one is also acceptable when the change is large enough to warrant its own record.

3. **Header convention** — every ADR carries `Status` and `Date`; a reversed ADR additionally carries `Supersedes`. The `Date` reflects the most recent material decision.

This is deliberately scoped to the POC. **If/when the project graduates past the POC** (production hardening, external consumers of the decision record), revisit this and move to strict supersede-don't-rewrite, where the immutable trail matters more than day-to-day coherence.

## Options Considered

| Option | Description | Main concern |
|---|---|---|
| Strict immutable / supersede-only | Never edit an accepted ADR; every change is a new superseding ADR (the current AGENTS.md rule) | High ceremony for a fast-moving POC; doesn't match practice; a reader must walk a supersession chain to find the current decision |
| Free in-place editing (current README rule) | Edit any ADR any time; rely on git history | A reversed decision and its rationale can vanish from the rendered doc with no signal — defeats the ADR's purpose |
| **Living docs with visible reversals (chosen)** | Edit in place; clarifications are free, but decision reversals must record `Status` + `Supersedes` + keep the prior option | One extra convention to remember on reversals; the in-place/supersede boundary needs judgment |

## Consequences

### Positive
- Resolves the README ↔ AGENTS.md contradiction with one rule both will reference.
- ADRs stay coherent and readable (current decision is the body) without losing reversed decisions (header + Options Considered + git).
- Codifies the pattern already used on ADR-0009, so no rework of existing ADRs is required beyond optionally back-filling a `Supersedes` line where a reversal lacks one.

### Negative
- "Material change vs. clarification" is a judgment call; borderline edits may get inconsistent treatment.
- In-place history still relies on git for anything not captured in the header — a reader off-platform sees only the current state.

### Revisit Triggers
- The project graduates past the POC, or an external/audit consumer needs an immutable decision trail.
- In-place reversals repeatedly lose rationale despite this rule (i.e., the `Supersedes`/Options-Considered discipline isn't followed).

## Implementation Implications

- **`AGENTS.md`** — replace *"ADRs are immutable history — supersede, don't rewrite"* with the living-docs rule and a pointer to this ADR.
- **`docs/decisions/README.md`** — expand the Conventions bullet to state the clarification-vs-reversal distinction and the `Status`/`Supersedes` header convention, pointing to this ADR.
- No existing ADR must change, though a `Supersedes` line may be back-filled on any past in-place reversal that lacks one (e.g., ADR-0011's edits for the two-stage model).
