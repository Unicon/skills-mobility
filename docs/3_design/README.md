# 3 — Design

**Intent:** Capture *how* the system is built — overall architecture and per-component design (modules, APIs, data models, build order). Significant cross-cutting choices are recorded as ADRs in [`../decisions/`](../decisions/); design docs reference them rather than re-deciding.

## Contents

| Doc | Scope |
|---|---|
| [`mock-event-producer.md`](./mock-event-producer.md) | Design for the Mock Event Producer ("Mock LMS") — service, UI, event model, real-time feed, local-vs-AWS, build order |
| [`architecture/`](./architecture/) | Architecture diagrams (below) |

### `architecture/`

| File | What it shows |
|---|---|
| `aws-poc-architecture.jpg` | POC architecture on AWS — EventBridge → Event Consumer → Step Functions, invoked services, data stores, logging, tech stack |
| `enablement-layer-data-mapping-flow.png` | End-to-end data-mapping flow from source event to delivery target, by stage |
| `whiteboard-component-overview.png` | Mock LMS component breakdown (Event Producer, LMS Metadata APIs) and downstream components; "out of scope for happy path" |
| `whiteboard-happy-paths.png` | Happy paths (Badge Awarded / Skill Mastered / Course Completed), Canvas-style endpoint table, Canvas Live Events references |
| `whiteboard-all-paths.png` | "All paths" variant with AI-generated data-mapping / wallet-routing annotations |

## Conventions

- **Naming:** one design file per component (`<component>.md`), matching its requirements counterpart at `../2_requirements/<component>.md`; keep them cross-linked.
- Diagrams live in `architecture/` with descriptive filenames (originals were clipboard exports — see git history for original names).

## Workflows

- **Archiving:** set `Status: Superseded` and move retired design docs to `3_design/archive/`; supersede outdated diagrams by replacing them and noting the change in this README.
