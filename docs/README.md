# Documentation

Docs are organized by **lifecycle phase**, with a `README.md` in each directory describing its intent, contents, and workflows.

| Directory | Holds |
|---|---|
| [`1_product/`](./1_product/) | Why the system exists — vision, goals, success criteria, scope |
| [`2_requirements/`](./2_requirements/) | What it must do — system and per-component requirements |
| [`3_design/`](./3_design/) | How it's built — architecture diagrams and per-component design |
| [`4_operations/`](./4_operations/) | How it's run — deployment, runbooks, observability |
| [`decisions/`](./decisions/) | Architecture Decision Records (ADRs) — cross-cutting, not a phase |

## Conventions

- **Phase + component axes.** The top level is by phase. Within `2_requirements/` and `3_design/`, docs are named after the component (e.g. `mock-lms-*.md`), so a component's requirements and design are easy to find even though they live in different phase directories. A component may split into several requirements docs (e.g. Mock LMS → event-producer / apis / ui) while keeping a single design doc. Cross-link related docs via each file's `Related:` header.
- **Status header.** Each doc starts with `Status:` (Draft / Accepted / Superseded) and `Date:`.
- **ADRs** record decisions that cut across components; they stay in `decisions/` and are referenced from requirements/design docs rather than duplicated.
- **Archiving.** When a doc is retired, set `Status: Superseded` (note what replaced it) and move it to an `archive/` subfolder within its phase directory (e.g. `2_requirements/archive/`). ADRs are never moved — they are immutable history; mark them `Status: Superseded by ADR-XXXX` instead.

> This structure is a working convention for the POC and may be revisited as content grows or if the project is open-sourced.
