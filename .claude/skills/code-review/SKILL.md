---
name: code-review
description: Senior peer review of a diff for this repo, checked against AGENTS.md's own pre-completion checklist and the LLM/deterministic-validation architectural contract. Use when asked to review a PR, a branch, or a diff, or for a second opinion on changes. Also run as the final step of spike-and-stabilize. Review-only: surface findings with file:line anchors and a severity marker; never fix, commit, or push. Post to GitHub only when explicitly asked and approved.
---

# Code review

A senior peer review for this repo, built around `AGENTS.md`'s own "Checklist — run
before declaring any task complete" rather than a generic review pass. Surface what's
wrong and why; let the developer decide what to act on. Never apply fixes, commit, or
push from this skill.

## 1. Get the diff

Identify the target from what the developer asked: a PR number (`gh pr diff <n>`), a
branch, or working changes. Default to `git diff "$(git merge-base HEAD origin/main)"..HEAD`.
Read the diff and the code it directly calls at the diff's ref. When a finding needs to
know how changed code is used elsewhere, delegate that exploration to a Sonnet `Explore`
sub-agent and work from its summary. If the diff is empty, say so and stop.

If you need to actually run tests/lint/types against the PR's branch (not just read the
diff) and the branch predates a recent merge to `main` — common on this fast-moving
project, and it breaks the `uv` workspace when a member package is missing files that
landed later — don't modify the developer's checkout to fix it. Instead: `git worktree
add <tmp-path> <pr-head-sha> --detach`, `git merge origin/main --no-edit` inside that
worktree, run the checks there, then `git worktree remove <tmp-path> --force` when done.

## 2. Review

Check the dimensions the diff actually touches; skip the rest and say which you skipped.

- **Correctness**: logic, edge cases, error paths, async/None handling.
- **The architectural contract**: if the diff touches an LLM Decision Service or the
  orchestrator, confirm LLM output still passes through deterministic Policy Rules
  validation before it can affect delivery, and that the audit trail still captures what
  ADR-0011 §9 requires. This is the one thing in this codebase that must never regress
  quietly — treat any weakening of it as a `Bug.`, not a `Suggestion.`.
- **Module boundaries**: no import from `services/` into another `services/*` directly;
  `apps/` doesn't import `services/`; `libs/` doesn't import `apps/` or `services/`. Any
  AWS resource change goes through CDK in `infra/`, never an ad-hoc `aws-cli` call.
- **Data & fixtures**: mock data follows generate → capture → commit → replay
  (`AGENTS.md`); runtime code must load committed `fixtures/*.json`, never call the
  generator at request time; `generated-fixtures/` stays out of the diff (gitignored).
  Deterministic ids and same-seed byte-identical output for anything touching fixture
  generation.
- **Tests**: each behavior covered per the testing pyramid (`AGENTS.md`) — unit tests do
  the bulk of the work, API tests use FastAPI's `TestClient`, e2e stays happy-path only.
  No elaborate edge-case tests beyond what's reasonable for a POC. Assertions can
  actually fail; no vacuous tests. Fixtures/fakes over real network calls.
- **Types & lint**: would `uv run mypy libs/*/src services/*/src` and `uv run ruff check .`
  pass on the changed files? Note anything that looks like it'd fail either.
- **Secrets & generated artifacts**: no `.env`, credentials, hardcoded hostnames; nothing
  from the gitignored list (`audit-output/`, `execution-traces/`, `generated-fixtures/`,
  `logs/`, local DBs, `.venv/`, `node_modules/`, `dist/`) committed.
- **Surgical scope**: every changed line traces to the stated task; no adjacent
  refactors, no unused imports/variables introduced, no pre-existing dead code removed
  unless that was the task.
- **No AI attribution**: no `Co-Authored-By: Claude` or similar in commits, no
  `🤖 Generated with Claude Code` footers in PR text.
- **Docs/ADRs**: if the change affects structure or a decision already recorded in an
  ADR, check whether the ADR needs a corresponding update. ADRs are living documents
  during the POC — amend in place (ADR-0019, `docs/decisions/0019-adr-governance-and-lifecycle.md`);
  see `.claude/architecture-overview.md` for the convention in full.

## 3. Verify before asserting

A claim that sets a finding's severity needs a source: `file:line` or command output, not
memory. Checking a library's documented behavior is a web lookup — run it in a sub-agent,
never inline. If you can't back a claim, downgrade it to a question.

## 4. Present

Group findings by severity, each with a `file:line` anchor and a one-word marker:

- `Bug.` wrong behavior, a break in the LLM/deterministic-validation contract, or a
  module-boundary violation.
- `Question.` a premise you can't confirm; ask rather than assert.
- `Suggestion.` a real improvement that's optional.
- `Nit.` style or wording, lowest priority.

Open with a one-line verdict, then the findings, then run the `AGENTS.md` checklist as a
final pass/fail list (tests exist, tests pass, lint clean, types clean, no secrets, no AI
attribution, docs/ADRs updated if warranted) so the developer sees the full gate at a
glance. Direct, specific, no praise padding. Post to GitHub only if the developer asks and
approves the wording.
