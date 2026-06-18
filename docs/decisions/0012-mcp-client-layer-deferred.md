# ADR-0012: MCP Client Layer Deferred from Initial POC Scope

- Status: Accepted
- Date: 2026-06-18
- Supersedes (in part): [POC Requirements §2 — Core POC Objectives](../2_requirements/poc-requirements.md)
- Related: [ADR-0004](./0004-lif-usage.md) · [ADR-0006](./0006-other-open-source-usage.md)

## Context

The POC Requirements document lists "Utilize MCP as a standardized interface layer for data access and tooling" as an explicit core POC objective. The requirements also describe a dedicated **MCP Client Layer** component responsible for discovering MCP resources, invoking MCP tools, and exploring prompt construction strategies using MCP metadata.

After two rounds of evaluation (ADR-0004 deferring the LIF Semantic Search MCP Server; ADR-0006 finding no external MCP-based tool ready to integrate), MCP integration has not yet materialized into a concrete, bounded use case for this project. Neither inbound nor outbound MCP usage has a clear implementation path within the current scope.

A quick external scan performed on 2026-06-18 also checked whether plausible badge-enrichment or skills-data sources already expose MCP interfaces that would justify a dedicated MCP client layer in the POC. The strongest candidates found were conventional API or standards-based integrations rather than MCP-native ones:

- [O*NET Web Services](https://services.onetcenter.org/), which exposes a REST API with an OpenAPI description for the O*NET database.
- [Credential Engine / Credential Registry APIs](https://credentialengine.org/develop-solutions/apis/), which support publishing and consuming CTDL data, plus the [Credential Registry Badge Publisher Tool](https://credentialengine.org/badge-publisher-tool/) for mapping Open Badges into CTDL and aligning them to competencies and occupations.
- [1EdTech CASE](https://www.1edtech.org/standards/case), which defines a standard REST API exchange format for academic standards, competencies, and learning outcomes, with an accompanying [CASE REST/OpenAPI specification](https://www.imsglobal.org/sites/default/files/spec/case/v1p1/rest_binding/caseservicev1p1_restbindv1p0.html).
- [ESCO Services API](https://esco.ec.europa.eu/en/use-esco/use-esco-services-api), which exposes skills, competences, qualifications, and occupations through conventional APIs.

This quick scan did not identify an official MCP server for these sources. That is a time-bounded research finding, not a claim that no such MCP adapter could exist elsewhere.

The POC Component Boundary Matrix treats the MCP Client Layer as deferred from the initial POC scope. Because this directly supersedes a stated core objective from the requirements, the decision warrants an explicit ADR rather than a design-doc footnote.

## Decision

The **MCP Client Layer** will **not** be implemented as a first-class component in the initial POC. It is deferred, not abandoned.

If a concrete MCP use case is identified — for example, a supporting system that exposes an MCP interface the Context Builder needs to call — MCP can be reintroduced as a support dependency of the Context Builder rather than as a top-level planned component.

## Rationale

- **Time constraints matter for this POC.** The initial POC already has enough core architecture to prove without adding a new integration abstraction. Even the most promising external data sources currently appear to require direct API work or a custom MCP wrapper before they could be consumed through an MCP client layer.
- **No concrete use case yet.** MCP's value in this architecture depends on external systems exposing MCP interfaces. The current POC targets two specific delivery adapters (LearnCloud/LearnCard and SmartResume); neither currently has a defined MCP interface relevant to this workflow.
- **Evaluation found no ready integration point.** ADR-0004 deferred the LIF Semantic Search MCP Server; ADR-0006 ruled out EDUcore's MCP interface; and the 2026-06-18 external scan found useful upstream APIs and standards, but no official MCP-ready source that could be adopted directly for this POC.
- **Promising external data sources exist, but they do not justify the layer yet.** Credential Engine is the strongest current badge-enrichment candidate because CTDL and the Credential Registry are explicitly designed for credentials, competencies, pathways, and workforce data, and the Badge Publisher already maps Open Badges into that ecosystem. O*NET and ESCO are strong workforce-taxonomy sources, and CASE is a viable competencies/standards source. Those findings support revisiting data enrichment later, but they do not by themselves justify building a dedicated MCP client layer now.
- **Adding MCP infrastructure without a use case increases scope without validating the objective.** The original PRD objective was to evaluate MCP as a standardized interface layer. That evaluation is better served by reintroducing MCP when a real integration point exists than by building speculative infrastructure.
- **Context Builder is the natural integration point.** If MCP is later needed to fetch supporting data or invoke external tools, the Context Builder's deterministic source-fetch design is where MCP calls belong — not a standalone layer.

## Consequences

- The initial POC does not implement or evaluate the MCP Client Layer.
- This explicitly supersedes the "Utilize MCP as a standardized interface layer" objective from the POC Requirements for this iteration.
- The MCP objective remains valid for future iterations. It should be revisited when a concrete inbound or outbound MCP integration point is identified, or when the team decides that wrapping a specific external API behind MCP would create enough value to justify the added scope.
- If MCP is adopted in a future iteration, an updated ADR should document the specific integration point, the chosen MCP role (client, server, or both), and how it fits into the then-current component boundaries.
