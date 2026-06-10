# 2 — Requirements

**Intent:** Capture *what* the system must do — scope, actors, functional and non-functional requirements, and success criteria — at both the system level and per component.

## Contents

| Doc | Scope |
|---|---|
| [`poc-requirements.md`](./poc-requirements.md) | **Master** POC requirements — scope/definitions, objectives, the full component breakdown, success criteria |
| [`mock-event-producer.md`](./mock-event-producer.md) | **Component** requirements for the Mock Event Producer ("Mock LMS") — Canvas-style metadata APIs, event emission, demo UI |

## Conventions

- **Naming:** one file per component, named after the component (`<component>.md`). Its design counterpart lives at `../3_design/<component>.md`; keep the two cross-linked via each doc's `Related:` header.
- Component requirements reference, but do not restate, the master `poc-requirements.md` and any relevant ADRs in [`../decisions/`](../decisions/).

## Workflows

- **Archiving:** set `Status: Superseded` (note the replacement) and move retired requirements to `2_requirements/archive/`.
