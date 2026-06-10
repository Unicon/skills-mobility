# 0004. LIF Component Usage in the Initial POC

- Status: Proposed
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

- adopt the LIF Translator and LIF MDR together as the primary candidate translation layer,
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
| Translator | `Adopt now` | This is one of the strongest fits with project goals. The project needs reusable translation across varied source and destination models, and the current event-driven, single-learner workflow avoids the batch and cohort concerns that have been raised about more traditional ETL use cases. | Integration cost, mapping expressiveness, or event-driven execution constraints prove to be blocking in practice. |
| Identity Mapper | `Defer` | Identity mapping may become important quickly, especially for connecting learner identities between the LMS and downstream wallets. It may also influence routing decisions. However, the current LIF Identity Mapper is incomplete, so adopting it likely means contributing to LIF or building substantial missing pieces. | LMS-to-wallet or multi-system identity resolution becomes a concrete implemented requirement. |
| MDR Service | `Adopt now` | If we use the LIF Translator, we should also use the MDR because the Translator depends on it for translation instructions. The MDR is also a natural place to store AI-generated mapping and translation instructions for reuse. This likely accelerates work if we continue with LIF's current JSONata-based approach. | The MDR's current limitations, including broken model import, make adoption too costly relative to the value it provides. |
| MDR UI | `Defer` | The UI is not required for the core pipeline, but it may become useful for importing data models, reviewing AI-generated mappings, and demonstrating the work. Its value increases if model import and MDR-centered workflows become part of the demo or operator experience. | We need a human-facing workflow for model import, mapping review, or demo presentation around MDR content. |
| Advisor API & UI | `Do not use` | Conversational learner advising is not part of the current scope. | The project adds a natural-language advising or assistant use case over learner data. |
| Semantic Search MCP Server | `Defer` | MCP is in scope for the broader project, but it is still unclear how MCP should be used here. A more likely near-term direction is consuming MCP from external systems than exposing this project's data through a LIF MCP server. | We decide this project should expose semantically searchable data or workflow context through MCP. |
| Query Cache | `Do not use` | The LIF Query Cache is aimed at storing learner data fragments and merged learner records. That is outside this POC's current scope. We may still need caching for badge templates, translation instructions, or AI artifacts, but that is a different problem. | The project starts caching or serving learner records rather than only compiling and transporting them. |
| Query Planner | `Defer` | This appears conceptually close to the proposed Context Builder for this project. It deserves a closer comparison before deciding whether to adopt the LIF Query Planner, build an equivalent locally, or combine ideas from both. | The Context Builder design is clarified and we can directly compare it against the LIF Query Planner responsibilities. |
| Orchestrator API | `Defer` | The orchestration technology decision is still open. A LIF-style abstraction layer may be useful, but only if we actually need portability across orchestration backends or want to align tightly with the rest of the LIF workflow model. | We commit to an external orchestrator and decide that backend abstraction is worth the added complexity. |

## Translation Notes

- The initially proposed architecture did not explicitly include a Translator service. However, if the LLM Decision Service is going to be proposing data mappings for data that needs to be translated, this those mappings need to be executed somewhere.
- The Translator and MDR should be treated as a paired decision, not independent ones.
- If JSONata translation instructions make the most sense for this project, then the LIF Translator and MDR can act as an existing solution to store and execute those instructions.
- If AI-generated translation instructions become part of the design, the MDR is the most natural place to store and manage them.
- If that happens, translation generation may deserve its own dedicated AI-assisted service instead of being bundled into one general-purpose LLM decision service.
- The current broken MDR model-import path is a known adoption risk and may need to be fixed early.

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
- Direct adoption of Translator plus MDR could accelerate reusable mappings across many source and destination combinations.
- Adopting Translator plus MDR also likely commits us, at least initially, to MDR-backed mapping storage and probably JSONata-based transformation instructions.
- We may need to fix MDR import behavior before the adoption path is practical.
- Identity resolution, query planning, MCP exposure, and orchestration abstraction remain open design areas rather than settled architecture.

## Open Questions

- Should the project's canonical learner and credential model be LIF-native, LIF-compatible, or only LIF-inspired?
- Should routing, translation generation, and destination selection be handled by one LLM decision service or by multiple specialized AI-assisted services?
- If we adopt the Translator and MDR, do we also want to standardize on JSONata for transformation instructions?
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
