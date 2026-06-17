# 3 — Design

**Intent:** Capture *how* the system is built — overall architecture and per-component design (modules, APIs, data models, build order). Significant cross-cutting choices are recorded as ADRs in [`../decisions/`](../decisions/); design docs reference them rather than re-deciding.

## Contents

| Doc | Scope |
|---|---|
| [`mock-lms.md`](./mock-lms.md) | Design for the **Mock LMS** (Event Producer + LMS Resource APIs + Demo UI) — modules, event model, Actions, real-time feed, data model, local-vs-AWS, build order |
| [`architecture/`](./architecture/) | Architecture diagrams (below) |

The Mock LMS *requirements* are split across three docs in [`../2_requirements/`](../2_requirements/) (event-producer / apis / ui); design is kept as one document because the parts interact closely.

### `architecture/`

| File | What it shows |
|---|---|
| `enablement-layer-data-mapping-flow.png` | **Canonical / source diagram** — the end-to-end data-mapping flow from the POC requirements doc (source event → delivery target, by stage) |
| `aws-poc-architecture.jpg` | POC architecture on AWS — EventBridge → Event Consumer → Step Functions, invoked services, data stores, logging, tech stack. *(Early sketch — predates ADR-0011's decision to run orchestration on a project-internal runtime rather than Step Functions.)* |
| `whiteboard-component-overview.png` | Mock LMS component breakdown (Event Producer, LMS Resource APIs) and downstream components |
| `whiteboard-happy-paths.png` | Happy paths (Badge Awarded / Skill Mastered / Course Completed), Canvas-style endpoint table, Canvas Live Events references |

`enablement-layer-data-mapping-flow.png` is the most authoritative of these — it came with the POC requirements. The whiteboard images are working sketches.

## Conventions

- **Naming:** design docs match their requirements counterparts in `../2_requirements/` and stay cross-linked.
- Diagrams live in `architecture/` with descriptive filenames (originals were clipboard exports — see git history for original names).

## Workflows

- **Archiving:** set `Status: Superseded` and move retired design docs to `3_design/archive/`; supersede outdated diagrams by replacing them and noting the change in this README.
