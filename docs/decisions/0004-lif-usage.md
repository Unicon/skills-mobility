# 0004. LIF Component Usage in the Initial POC

- Status: Accepted
- Date: 2026-06-10

## Context

This project is a proof of concept for AI-assisted credential orchestration, transformation, and delivery using LLMs and Model Context Protocol (MCP).

For the initial POC, the working assumption is that the system is primarily responsible for compiling context, transforming data, and transporting outputs in response to a single event for a single learner.

The current scope is not centered on:

- storing learner records as a system of record,
- serving compiled learner data through a shared query API,
- exposing this project's data to other systems through an MCP server, or
- building learner-facing or advisor-facing user experiences.

LIF provides a set of reusable microservices for learner data integration, querying, transformation, metadata management, orchestration, and AI-assisted access. This ADR captures which of those components we should incorporate into this project now, which ones we should defer as potential future options, and which ones are not relevant to the initial POC.

## Decision Drivers

- Keep the initial POC small and tightly aligned to compilation, transformation, and transport
- Reuse existing LIF capabilities where they directly accelerate project goals
- Support reuse across a variety of possible inputs and outputs
- Preserve auditability and traceability around orchestration and transformation decisions
- Avoid taking on learner-record serving and storage responsibilities that are outside current scope
- Leave room to expand into more of the LIF platform later if the project proves out

## Decision

For the initial POC, we will use LIF selectively rather than adopting the full LIF platform.

We will:

- defer the LIF Translator and LIF MDR, potentially reimplementing their functionality directly within this project,
- defer components that may become useful once identity resolution, orchestration, or MCP exposure are better defined, and
- not use LIF components whose main purpose is serving learner records, caching learner data, or providing advisor-style user experiences.

Decision categories used below:

- `Adopt now`: incorporate the LIF component into the initial POC
- `Defer`: do not include it in the initial POC, but keep it as a potential future option
- `Do not use`: not relevant to the current POC scope

## Component Decisions

| LIF component | Initial decision | Rationale | Revisit when |
| --- | --- | --- | --- |
| GraphQL API | `Do not use` | The project is currently about data compilation and transport, not storing learner data or serving it through a shared query layer. A GraphQL API is therefore outside the current scope. | The project expands into serving compiled learner or credential data to other systems or clients. |
| Translator | `Defer` | The LIF Translator is a strong conceptual fit for the project's reusable translation needs, but it is more expedient to reimplement this functionality directly within the project rather than integrate an external dependency. A direct reimplementation can also be tailored to the AI-assisted workflow of this project. | The project's translation complexity grows to the point where the LIF Translator offers clear advantages over an internal reimplementation, or LIF Translator maturity improves significantly. |
| Identity Mapper | `Defer` | Identity mapping may become important quickly, especially for connecting learner identities between the LMS and downstream wallets. It may also influence routing decisions. However, the current LIF Identity Mapper is incomplete, so adopting it likely means contributing to LIF or building substantial missing pieces. | LMS-to-wallet or multi-system identity resolution becomes a concrete implemented requirement. |
| MDR Service | `Defer` | The MDR has an active bug preventing import of new data schemas, blocking integration of the LMS schema needed for this POC. It is more expedient to reimplement MDR functionality directly within the project, and doing so creates an opportunity to redesign and re-architect aspects of the MDR to better suit this project's needs. | The MDR bug is resolved and its capabilities clearly exceed what a project-internal reimplementation provides. |
| MDR UI | `Defer` | The UI is not required for the core pipeline, but it may become useful for importing data models, reviewing AI-generated mappings, and demonstrating the work. Its value increases if model import and MDR-centered workflows become part of the demo or operator experience. | We need a human-facing workflow for model import, mapping review, or demo presentation around MDR content. |
| Advisor API & UI | `Do not use` | Conversational learner advising is not part of the current scope. | The project adds a natural-language advising or assistant use case over learner data. |
| Semantic Search MCP Server | `Defer` | MCP is in scope for the broader project, but it is still unclear how MCP should be used here. A more likely near-term direction is consuming MCP from external systems than exposing this project's data through a LIF MCP server. | We decide this project should expose semantically searchable data or workflow context through MCP. |
| Query Cache | `Do not use` | The LIF Query Cache is aimed at storing learner data fragments and merged learner records. That is outside this POC's current scope. We may still need caching for badge templates, translation instructions, or AI artifacts, but that is a different problem. | The project starts caching or serving learner records rather than only compiling and transporting them. |
| Query Planner | `Do not use` | This appears conceptually close to the proposed Context Builder for this project. However, it is tightly tied to the LIF Query Cache, which is pretty far outside this project's scope, so it would be best to build the Context Builder specifically for our purposes. | The project starts caching or serving learner records rather than only compiling and transporting them. |
| Orchestrator API | `Defer` | The orchestration technology decision is still open. A LIF-style abstraction layer may be useful, but only if we actually need portability across orchestration backends or want to align tightly with the rest of the LIF workflow model. | We commit to an external orchestrator and decide that backend abstraction is worth the added complexity. |

## Translation Notes

- The initially proposed architecture did not explicitly include a Translator service. However, if the LLM Decision Service is going to be proposing data mappings for data that needs to be translated, then those mappings need to be executed somewhere.
- The Translator and MDR should be treated as a paired decision, not independent ones.
- ADR 0005 makes JSONata the proposed primary mapping language for this work, which aligns with the LIF approach and can guide the design of any internal reimplementation.
- If AI-generated translation instructions become part of the design, an internal reimplementation of MDR-style storage is the natural place to manage them.
- If that happens, translation generation may deserve its own dedicated AI-assisted service instead of being bundled into one general-purpose LLM decision service.

## Orchestration Notes

The orchestration choice is still open. Based on current official documentation and the current POC scope, the tradeoffs look like this:

- `AWS Step Functions` looks strongest for AWS-native, event-driven orchestration. AWS describes it as a state-machine workflow service for distributed applications, process automation, microservice orchestration, and data or ML pipelines. Standard workflows emphasize auditability and execution history, and Step Functions also supports JSONata-based data transformation.
    - However, its JSONata support is workflow-embedded, not MDR-backed:
        - Step Functions evaluates expressions against workflow input, result, error output, and context data, rather than dynamically loading translation instructions from a metadata repository during expression evaluation.
        - Step Functions can orchestrate calls out to APIs or Lambda, so it could be used to fetch mappings before later states run, but that is not the same as using a dedicated translator that natively resolves configurable mappings from MDR.
        - AWS also documents JSONata-specific operational limits, including a 1-second expression evaluation timeout and memory limits, plus a 256 KiB limit on task, state, and execution input or output. If HTTP Task were used to call MDR or similar external services directly, AWS also documents a 60-second HTTP Task duration limit. 
    - Inference: this makes Step Functions a strong fit for orchestration, but not a clean substitute for the LIF Translator plus MDR if we want translation rules externalized and reusable.
- `Dagster` is described as a data orchestrator for data engineers, with integrated lineage, observability, declarative programming, and strong testability. Its sensor model is designed to react to internal or external events. Inference: this makes it attractive if the project grows into a broader data orchestration and observability platform rather than a narrow event-transport workflow.
- `Airflow` is a workflow platform built around DAGs, tasks, a scheduler, a webserver, and a metadata database. It is flexible and mature, but its architecture introduces more standing components to operate. Inference: it is more compelling if the project needs a fuller workflow platform with recurring DAG-style operations than if it remains a narrow event-driven POC.
- A LIF-style orchestrator abstraction should be deferred unless there is a real requirement to support more than one backend or keep the project portable across orchestrators.

## Consequences

- The initial POC stays focused on translation and transport instead of expanding into a learner-data serving platform.
- Deferring the LIF Translator and MDR avoids external dependency risks and creates an opportunity to design the translation layer specifically for this project's AI-assisted workflow.
- The project remains committed to a JSONata-based translation approach, now potentially expressed through an internal reimplementation rather than direct LIF adoption.
- Identity resolution, query planning, MCP exposure, and orchestration abstraction remain open design areas rather than settled architecture.

## Open Questions

- Should the project's canonical learner and credential model be LIF-native, LIF-compatible, or only LIF-inspired?
- Should routing, translation generation, and destination selection be handled by one LLM decision service or by multiple specialized AI-assisted services?
- Does the proposed Context Builder overlap enough with the LIF Query Planner that they should be unified?
- Is AWS Step Functions the best initial orchestrator, or do Dagster or Airflow offer enough strategic upside to justify their additional platform shape?
- If an external orchestrator is chosen, do we want a stable abstraction layer in front of it from the start?

## References

- [LIF Microservices Overview](https://github.com/LIF-Initiative/lif-core/blob/main/docs/overview/services-overview.md)
- [AWS Step Functions: What is Step Functions?](https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html)
- [Transforming data with JSONata in Step Functions](https://docs.aws.amazon.com/step-functions/latest/dg/transforming-data.html)
- [Discover service integration patterns in Step Functions](https://docs.aws.amazon.com/step-functions/latest/dg/connect-to-resource.html)
- [Step Functions service quotas](https://docs.aws.amazon.com/step-functions/latest/dg/service-quotas.html)
- [Dagster Docs Overview](https://docs.dagster.io/)
- [Dagster Sensors](https://docs.dagster.io/guides/automate/sensors)
- [Airflow Architecture Overview](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/overview.html)
