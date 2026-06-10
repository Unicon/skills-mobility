# 0005. Schema Mapping Language

- Status: Accepted
- Date: 2026-06-10

## Context

This decision logically comes before the decision about whether to use the LIF Translator and MDR. If the project chose a different primary mapping-language approach, then the LIF Translator and MDR would be much less relevant or potentially not relevant at all.

For that reason, the schema-mapping-language decision should be treated as an input to ADR 0004, not as a sub-decision underneath it.

This project is expected to translate JSON-like data across multiple source and destination models in an event-driven workflow. The team is also considering whether AI-assisted services should generate mapping instructions that can be stored, reviewed, and re-executed later.

Because of that, the mapping-language choice affects more than syntax. It influences:

- whether mappings can be stored outside workflow code,
- whether mappings are reusable across sources and destinations,
- whether generated mappings are reviewable by humans,
- how much logic stays declarative instead of moving into custom code, and
- how naturally the project fits the LIF Translator plus MDR model.

## Decision Drivers

- Keep translation instructions reusable across many inputs and outputs
- Prefer mappings that can be stored and managed as data
- Support human review of AI-generated mappings
- Preserve a practical debugging and testing workflow
- Align with the LIF Translator plus MDR if that path remains viable
- Maintain an escape hatch for transformations that do not fit a declarative DSL cleanly

## Decision

For the initial POC, the project will use `JSONata` as the primary schema-mapping language.

This decision is being made up front rather than deferred behind a pre-decision experiment. The purpose of the POC is partly to pressure test architectural choices in practice, and JSONata is currently the best fit based on project needs and prior LIF experience.

This means:

- translation instructions should be represented primarily as JSONata expressions,
- downstream translation architecture should assume JSONata compatibility,
- the LIF Translator and MDR remain attractive specifically because they already align with that choice, and
- the POC itself will validate whether this was the right architectural decision.

## Options Considered

| Option | What it is | Strengths for this project | Main concerns |
| --- | --- | --- | --- |
| `JSONata` | A lightweight query and transformation language for JSON data that can format results into arbitrary JSON structures and can be extended with user-defined functions. | Best alignment with the current LIF path. Good fit for declarative field-level and record-level mappings. Likely easier than custom code to store in MDR and potentially easier for AI to generate and humans to review. Also overlaps with Step Functions JSONata support, even though Step Functions is not a Translator replacement. | Adds a DSL that the team must learn and govern. Complex mappings may become hard to read or debug. Runtime support and implementation maturity must be checked for the languages and services we actually use. |
| `JMESPath` | A query language for JSON that supports extraction, projections, filtering, functions, and creation of JSON elements through multiselect lists and hashes. | Good for selecting, reshaping, and projecting JSON data with a relatively clear expression model. Worth considering if the main need is extraction plus light restructuring. | Primarily positioned as a query language. It appears less purpose-built than JSONata for richer transformation workflows and externalized mapping specifications. |
| `JOLT` | A Java JSON-to-JSON transformation library whose transform specification is itself JSON. It focuses mainly on structural transformation and allows chained transforms. | Attractive if the main need is structural remapping driven by JSON specs rather than code. The spec-as-JSON approach may be interesting for stored mappings. | It is Java-centered, while this project is primarily Python-oriented. The JOLT maintainers explicitly describe it as focusing on structure rather than manipulating specific values, with custom code needed for data manipulation. That is a weaker fit if we expect rich value-level mappings. |
| `JsonLogic` | A small, safe JSON-serialized rules language designed to express one deterministic decision without side effects. | Could complement this project for policy or routing logic because it is easy to store and share as data. | It is not a full transformation language and is better suited to decisions than record translation. It should be treated as a policy or rules alternative, not a primary mapping-language alternative. |
| `Custom Python code` | Imperative translation logic written directly in project services, potentially with helper libraries such as Pydantic models and internal mapping utilities. | Maximum flexibility, best debugging ergonomics, and easiest escape hatch when transformations need custom logic, external calls, or strong typing. | Weakest option for reusable externalized mappings. Harder to store in MDR as portable instructions. Likely less suitable for AI-generated mappings that need human review and re-execution. |

## Why JSONata

JSONata is the right proposed choice for this project because all or most of the following are true:

- most transformations are pure JSON-in to JSON-out mappings,
- mappings should be stored outside workflow code,
- mappings should be reusable across many sources and destinations,
- AI-generated mappings are part of the design,
- reviewers need to inspect mapping instructions as data rather than code, and
- alignment with the LIF Translator plus MDR is important.

Cons:

- JSONata would not work well if some transformations require imperative logic, external lookups, or side effects,
- mappings may become hard to understand once they grow beyond straightforward field and object transformations,
- some people may prefer stronger typing and ordinary language debugging over declarative portability,
- runtime implementation gaps or operational constraints may become more significant than expected.

## Consequences

- If JSONata works well, it strengthens the case for using the LIF Translator plus MDR directly.
- This decision will influence how AI-generated mappings are represented, reviewed, stored, and executed.

## Open Questions

- How readable will non-trivial JSONata mappings remain once they include conditionals, array reshaping, and destination-specific output structure?
- Will AI-generated mappings be reliable and reviewable enough in JSONata for ongoing use?
- Do we need one mapping language across the whole project, or should we intentionally allow a hybrid model for exceptional cases?

## References

- [LIF Microservices Overview](https://github.com/LIF-Initiative/lif-core/blob/main/docs/overview/services-overview.md)
- [JSONata Overview](https://docs.jsonata.org/overview.html)
- [JMESPath Tutorial](https://jmespath.org/tutorial.html)
- [JOLT README](https://github.com/bazaarvoice/jolt/blob/master/README.md)
- [JsonLogic](https://jsonlogic.com/)
