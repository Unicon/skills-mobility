# ADR-0006: Other Open Source Usage

Status: Accepted
Date: 2026-06-12

## Context

The Skills Mobility Infrastructure POC requires transforming LMS data into Open Badges 3.0 credentials, and potentially other formats in the future. Three open source tools were evaluated for potential use in this workflow: the DCC Credential Co-Writer (CCW), EDUcore, and the Learner Information Framework (LIF).

## Decision

None of the three evaluated tools will be used in this POC. Transformation functionality will be implemented within the project's own Transformation Mappings LLM Decision Service. The DCC CCW and LIF MDR and Translator may be mocked or partially reimplemented within the project if the timeline allows. Any of the three tools may also be reconsidered for future iterations.

## Rationale

Each tool has limitations that make adoption impractical within the POC timeline:

- **DCC CCW** is not publicly available on GitHub, so it cannot be analyzed or integrated.
- **EDUcore** cannot be run locally from its public repositories, does not support adding new data model schemas, and its MCP tool delegates transformation reasoning to an LLM — something the project can do directly without the added dependency.
- **LIF** has an active bug preventing import of new data schemas, making it challenging to add the LMS schema required for the POC and the LIF components are themselves in a rough POC state.

In all three cases, the required transformation logic can be achieved within the project's own LLM Decision Service without incurring additional external dependencies on a short timeline.

## Consequences

### Positive

- No external open source dependencies to manage or integrate.
- Full team control over transformation logic and architecture.
- Opportunity to design transformation components purposefully rather than adapting to existing tool constraints.

### Negative

- Additional implementation effort to build or mock transformation functionality these tools might have provided.
- LIF and DCC CCW concepts may be revisited in future iterations, requiring later familiarity with those tools.

## Alternatives Considered

### DCC Credential Co-Writer (CCW)

A tool that takes text input (e.g., a PDF syllabus) and generates an Open Badges 3.0 template. It is not currently available on GitHub, making usability analysis and integration impossible. Not used in this POC; may be mocked.

### EDUcore

A knowledge graph holding over a dozen education standard data models and cross-standard mappings, with an MCP interface for querying the model. It cannot be run locally from public repositories, does not support adding new data model schemas, and its MCP-based translation output is effectively AI-generated — something the project can do independently. Not used in this POC; unlikely to be relevant in future iterations unless new-schema support and machine-readable translation instructions are added.

### Learner Information Framework (LIF)

A set of tools built around a learner-centric data model, most notably a Metadata Repository (MDR) and Translator that store field-level mappings between education standards and convert learner records between schemas. The MDR has an active bug preventing import of new schemas, blocking integration of the LMS schema needed for the POC. Additionally, the mapping approach (field-by-field rather than payload-level) may not suit an AI-assisted transformation workflow, and LIF itself is in a rough POC state. Not used in this POC; may be mocked or partially reimplemented.