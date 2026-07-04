# 3 — Design

**Intent:** Capture *how* the system is built — overall architecture and per-component design (modules, APIs, data models, build order). Significant cross-cutting choices are recorded as ADRs in [`../decisions/`](../decisions/); design docs reference them rather than re-deciding.

## Contents

| Doc | Scope |
|---|---|
| [`poc-component-boundaries.md`](./poc-component-boundaries.md) | Top-level boundary matrix for the target POC architecture: component ownership, non-ownership, inputs/outputs, dependencies, observability model, and supporting stores |
| [`event-consumer.md`](./event-consumer.md) | Design for the **Event Consumer** ingress boundary — runtime shape, logical modules, idempotency behavior, and Orchestrator handoff |
| [`orchestrator.md`](./orchestrator.md) | Design for the **Orchestrator** — plan acquisition, constrained step execution, Phase 1 stub seams, execution state, and local-vs-AWS invocation model |
| [`mock-lms.md`](./mock-lms.md) | Design for the **Mock LMS** (Event Producer + LMS Resource APIs + Demo UI) — modules, event model, Actions, data model (CSV roster + generated layer), phasing, local-vs-AWS, build order |
| [`context-builder.md`](./context-builder.md) | Design for the **Context Builder** — deterministic fetch profiles, chained LMS lookups, bundle assembly, and local-vs-AWS behavior |
| [`field-mapping-llm-decision-service.md`](./field-mapping-llm-decision-service.md) | Design for the Field Mapping LLM Decision Service — mapping-spec contract, prompt structure, Bedrock invocation, validation, and local-vs-AWS runtime shape |
| [`admin-ui.md`](./admin-ui.md) | Design for the **Admin UI** — read-only SPA over the Orchestrator's execution store: data contract, polling model, IA (list → workflow → step), frontend stack, and the three-layer token architecture |
| [`delivery-router-service.md`](./delivery-router-service.md) | Design for the Delivery Router Service — internal contract, dispatch model, shared delivery mechanics, and adapter integration points |
| [`learncard-profile-resolver.md`](./learncard-profile-resolver.md) | Design for the LearnCard Profile Resolver — standalone Python Lambda for learner profile resolution before issuance or delivery |
| [`learncard-issuer-adapter.md`](./learncard-issuer-adapter.md) | Design for the LearnCard Issuer Adapter — Node/TypeScript SDK boundary for issuance |
| [`learncard-wallet-adapter.md`](./learncard-wallet-adapter.md) | Design for the LearnCard Wallet Adapter — Python API boundary for wallet delivery |
| [`architecture/`](./architecture/) | Architecture diagrams (below) |

[`poc-component-boundaries.md`](./poc-component-boundaries.md) is the current top-level design reference for the POC component model. It is the place to align terminology such as **Orchestrator**, **LMS Resource APIs**, **Admin UI**, and the specialized LLM decision services before writing more detailed per-component design docs.

The stakeholder baseline in [`../2_requirements/poc-requirements.md`](../2_requirements/poc-requirements.md) is intentionally preserved. Current design docs should align to [`../2_requirements/target-poc-requirements.md`](../2_requirements/target-poc-requirements.md) and the ADRs rather than assuming the stakeholder baseline must be rewritten.

Component-specific design docs currently cover the **Orchestrator**, the **Mock LMS**, the **Context Builder**, the **Delivery Router Service**, the **LearnCard Profile Resolver**, the **LearnCard Issuer Adapter**, and the **LearnCard Wallet Adapter**. Follow-up component docs should stay consistent with the boundary matrix as they are added. The Mock LMS *requirements* are split across three docs in [`../2_requirements/`](../2_requirements/) (event-producer / apis / ui); design is kept as one document because the parts interact closely.

### `architecture/`

| File | What it shows |
|---|---|
| `target-poc-architecture.md` | Canonical wrapper for the current target architecture: links, notes, the primary target-architecture PNG, and a simplified overview Mermaid |
| `whiteboard-target-poc-architecture.png` | Current primary visual for the target POC architecture, reflecting the latest component layout and major flows |
| `whiteboard-phase1-component-overview.png` | Current whiteboard sketch of the intended **Phase 1** component slice |
| `whiteboard-phase1-workflow.png` | Current whiteboard sketch of the intended **Phase 1** workflow / execution path |
| `enablement-layer-data-mapping-flow.png` | Earlier source flow sketch (source event → delivery target, by stage). Useful historical context, but the current target architecture is now captured in `target-poc-architecture.md` and [`poc-component-boundaries.md`](./poc-component-boundaries.md). |
| `aws-poc-architecture.jpg` | Early AWS-oriented architecture sketch. Useful for rough infrastructure shape, but it predates ADR-0011 and the current Orchestrator-centered boundary model. |

The canonical references for the current target POC architecture are [`poc-component-boundaries.md`](./poc-component-boundaries.md) and [`architecture/target-poc-architecture.md`](./architecture/target-poc-architecture.md). Within that architecture doc, `whiteboard-target-poc-architecture.png` is the primary visual reference. The phase 1 PNGs are current planning assets, but they do not replace a dedicated phase 1 requirements/design doc if one is later added.

## Conventions

- **Naming:** design docs match their requirements counterparts in `../2_requirements/` and stay cross-linked.
- **Boundary source of truth:** use [`poc-component-boundaries.md`](./poc-component-boundaries.md) for current component names, ownership boundaries, and logical store definitions.
- **Canonical visual reference:** use [`architecture/target-poc-architecture.md`](./architecture/target-poc-architecture.md) as the current architecture entry point; within it, `whiteboard-target-poc-architecture.png` is the primary visual.
- Diagrams live in `architecture/` with descriptive filenames (originals were clipboard exports — see git history for original names).

## Workflows

- **Archiving:** set `Status: Superseded` and move retired design docs to `3_design/archive/`; supersede outdated diagrams by replacing them and noting the change in this README.
