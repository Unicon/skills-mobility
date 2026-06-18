# 3 — Design

**Intent:** Capture *how* the system is built — overall architecture and per-component design (modules, APIs, data models, build order). Significant cross-cutting choices are recorded as ADRs in [`../decisions/`](../decisions/); design docs reference them rather than re-deciding.

## Contents

| Doc | Scope |
|---|---|
| [`poc-component-boundaries.md`](./poc-component-boundaries.md) | Top-level boundary matrix for the target POC architecture: component ownership, non-ownership, inputs/outputs, dependencies, observability model, and supporting stores |
| [`mock-lms.md`](./mock-lms.md) | Design for the **Mock LMS** (Event Producer + LMS Resource APIs + Demo UI) — modules, event model, Actions, data model (CSV roster + generated layer), phasing, local-vs-AWS, build order |
| [`architecture/`](./architecture/) | Architecture diagrams (below) |

[`poc-component-boundaries.md`](./poc-component-boundaries.md) is the current top-level design reference for the POC component model. It is the place to align terminology such as **Orchestrator**, **LMS Resource APIs**, **Admin UI**, and the specialized LLM decision services before writing more detailed per-component design docs.

[`mock-lms.md`](./mock-lms.md) is currently the only component-specific design doc in this directory. Follow-up component docs should stay consistent with the boundary matrix as they are added. The Mock LMS *requirements* are split across three docs in [`../2_requirements/`](../2_requirements/) (event-producer / apis / ui); design is kept as one document because the parts interact closely.

### `architecture/`

| File | What it shows |
|---|---|
| `enablement-layer-data-mapping-flow.png` | Canonical source flow from the POC requirements doc (source event → delivery target, by stage). Component names and boundaries have since been refined by the ADRs and [`poc-component-boundaries.md`](./poc-component-boundaries.md). |
| `aws-poc-architecture.jpg` | Early AWS-oriented architecture sketch. Useful for rough infrastructure shape, but it predates ADR-0011 and the current Orchestrator-centered boundary model. |
| `whiteboard-component-overview.png` | Early whiteboard sketch of the Mock LMS and downstream components. Useful context, but the current authoritative component naming and ownership model is in [`poc-component-boundaries.md`](./poc-component-boundaries.md). |
| `whiteboard-happy-paths.png` | Happy paths (Badge Awarded / Skill Mastered / Course Completed), Canvas-style endpoint table, Canvas Live Events references |

The diagrams are helpful context, but the boundary matrix is now the clearest statement of the current intended component partitioning.

## Conventions

- **Naming:** design docs match their requirements counterparts in `../2_requirements/` and stay cross-linked.
- **Boundary source of truth:** use [`poc-component-boundaries.md`](./poc-component-boundaries.md) for current component names, ownership boundaries, and logical store definitions.
- Diagrams live in `architecture/` with descriptive filenames (originals were clipboard exports — see git history for original names).

## Workflows

- **Archiving:** set `Status: Superseded` and move retired design docs to `3_design/archive/`; supersede outdated diagrams by replacing them and noting the change in this README.
