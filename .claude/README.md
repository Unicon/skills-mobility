# `.claude/` — AI agent config for this repo

Claude Code config for working on Skills Mobility Infrastructure: subagents, skills, and
reference docs that package repeatable ways of working with this codebase, instead of
re-explaining conventions and architecture every conversation.

## Contents

- **`CLAUDE.md`** — imports the canonical, tool-agnostic `../AGENTS.md` (behavioral
  rules, tech stack, testing strategy, git/PR conventions) plus a couple of
  Claude-Code-specific notes. `AGENTS.md` is the source of truth; keep project guidance
  there so every coding agent (not just Claude Code) reads the same rules.
- **`agents/`** — `business-analyst` and `software-architect`, advisory read-only
  sub-agents for requirements review/authoring and architecture/design decisions.
- **`skills/`** — `requirements-writer` and `design-writer` (interactive doc drafting,
  each dispatches its matching agent), `code-review`, `spike-and-stabilize`.
- **`architecture-overview.md`**, **`requirements-template.md`**, **`design-template.md`**
  — reference docs the agents and skills ground their judgment in: the system's
  architectural spine, the ADR-0007/ADR-0011 contracts in depth, and the recurring
  section patterns already used in `docs/2_requirements/` and `docs/3_design/`.
- **`settings.local.json`** — personal permission overrides, gitignored; create your own
  after cloning if you need one, nothing here depends on it existing.
- **`scratch/`** — personal scratchpad for one-off draft documents (PR descriptions and
  the like), gitignored. Use a fixed filename per draft type, overwritten in place, not a
  new file per draft.

## Why bother with all this?

Claude Code reads everything here automatically at the start of a session, so repo
conventions, the LLM/deterministic-validation architectural contract, and current POC
scope boundaries don't need re-explaining every conversation. The agents and skills
package repeatable workflows (requirements/design doc drafting, architecture review) so
the process is the same regardless of who's driving, and the reference docs mean the AI
catches repo-specific rules (module boundaries, the ADR-0007/ADR-0011 contracts) that
generic use would miss. It's plain text, so it's cheap to maintain and cheap to delete if
a piece stops pulling its weight — nothing here is load-bearing infrastructure.

This project moves fast and the underlying docs/ADRs churn accordingly (see
`architecture-overview.md`'s note on not hand-tracking implementation state) — treat
everything in here as a living aid, not a frozen spec, and update it when it drifts from
what the repo actually does.

## Using it day to day

- **Writing or reviewing a component's requirements** (`docs/2_requirements/<component>.md`):
  the `requirements-writer` skill. Dispatches the `business-analyst` and asks you the
  questions that actually change the doc.
- **Writing or reviewing a component's design** (`docs/3_design/<component>.md`): the
  `design-writer` skill, once requirements are settled. Dispatches the
  `software-architect`.
- **Architecture or design question, not tied to a specific doc**: just ask; the
  `software-architect` agent gets pulled in automatically when it's relevant.
- **Implementing a non-trivial change**: the `spike-and-stabilize` skill — survey the
  code, get one combined clarify-and-plan approval, write a thin throwaway spike, then
  stabilize it (types, tests, checks, review). Skip it for trivial changes like renames
  or typo fixes.
- **Reviewing a diff or PR**: the `code-review` skill — checked against this repo's own
  `AGENTS.md` checklist, not a generic pass.
- **Drafting a PR description, issue text, or similar one-off**: ask Claude to put it in
  `.claude/scratch/` under a fixed filename (e.g. `pr-description.md`) so it's easy to
  find and never accidentally committed.
- **Everything else** (`CLAUDE.md`, `architecture-overview.md`) loads as background
  context automatically. You never invoke it directly — it's just informing every
  response.
