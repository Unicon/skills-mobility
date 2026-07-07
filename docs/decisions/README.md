# Decisions (ADRs)

**Intent:** Record architecture decisions that cut across phases and components — the choice, its context, rationale, and consequences. ADRs are referenced from requirements and design docs rather than duplicated there.

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](./0001-repo-structure.md) | Repository Structure — Conventional Monorepo vs. Polylith | Accepted |
| [0002](./0002-frontend-architecture.md) | Frontend Architecture (two React SPAs, S3+CloudFront, CloudFront-layer auth) | Accepted |
| [0003](./0003-programming-language.md) | Primary Programming Language Selection (Python-first) | Accepted |
| [0004](./0004-lif-usage.md) | LIF Component Usage in the Initial POC | Accepted |
| [0005](./0005-schema-mapping-langauge.md) | Schema Mapping Language (JSONata) | Accepted |
| [0006](./0006-other-open-source-usage.md) | Other Open Source Usage | Accepted |
| [0007](./0007-llm-decision-service-decomposition.md) | LLM Decision Service Decomposition (delivery targets / transformation mappings / workflow actions) | Accepted |
| [0008](./0008-transformation-mapping-service-decomposition.md) | Transformation Mapping Service Decomposition | Accepted |
| [0009](./0009-workflow-actions-orchestration-model.md) | Workflow Actions Orchestration Model: Two-Stage Hierarchical Planning | Accepted |
| [0010](./0010-llm-model-access-strategy.md) | LLM Model Access Strategy | Accepted |
| [0011](./0011-orchestration-runtime-technology.md) | Orchestration Runtime Technology | Accepted |
| [0012](./0012-mcp-client-layer-deferred.md) | MCP Client Layer Deferred from Initial POC Scope | Accepted |
| [0013](./0013-llm-decision-service-testing-approach.md) | LLM Decision Service Testing Approach | Proposed |
| [0014](./0014-poc-storage-strategy.md) | POC Storage Strategy | Accepted |
| [0015](./0015-orchestrator-execution-model.md) | Event Consumer and Orchestrator Worker Execution Model (Lambda + SQS) | Accepted |
| [0016](./0016-delivery-routing-topology.md) | Delivery Routing Topology and Adapter Boundaries | Proposed |
| [0018](./0018-admin-ui-frontend-stack.md) | Admin UI Frontend Stack and Design-Token Architecture (Radix + Open Props + Radix Colors + Motion; no Tailwind/shadcn) | Accepted |
| [0019](./0019-adr-governance-and-lifecycle.md) | ADR Governance and Lifecycle: Living Documents with Visible Reversals | Proposed |
| [0020](./0020-js-ts-workspace-tooling.md) | JS/TS Workspace Tooling and Token Publishing (npm workspaces, single root lockfile, no build step) | Accepted |

## Conventions

- Filename: `NNNN-short-title.md`, numbered sequentially.
- ADRs are **living documents** maintained in place during the POC ([ADR-0019](./0019-adr-governance-and-lifecycle.md)). Clarifications/corrections: edit freely. **Reversing an accepted decision:** edit in place but keep it visible — update `Status`, add a `Supersedes: <date> — <what changed>` header line, and keep the prior option under *Options Considered*. Every ADR carries `Status` + `Date`.
