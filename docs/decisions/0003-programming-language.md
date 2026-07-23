# ADR-0003: Primary Programming Language Selection

Status: Accepted (infrastructure-as-code revised 2026-07-20: AWS CDK → CloudFormation — see [Revision History](#revision-history))  
Date: 2026-06-10

## Context

The Skills Mobility Infrastructure Proof of Concept (POC) is intended to validate an orchestration-centric architecture for AI-assisted credential transformation and delivery. The POC includes:

- event ingestion and processing,
- context aggregation from LMS and credential sources,
- LLM-based routing and transformation decisions,
- deterministic policy validation,
- MCP-based access to tools and resources,
- credential issuance and delivery,
- integration with LearnCloud/LearnCard and SmartResume, and
- audit logging and traceability.

Several implementation language options were considered, including Python and TypeScript.

The team also discussed:

- use of AWS Lambda, Step Functions, EventBridge, and Bedrock,
- implementation of MCP clients and servers,
- creation of mock LMS APIs and event producers,
- integration with LearnCloud/LearnCard for credential issuance and delivery,
- performance characteristics of Python versus TypeScript, and
- long-term maintainability of the resulting architecture.

## Decision

The POC will use Python as the primary implementation language.

TypeScript will be used only where required by external platform dependencies or where it provides clear implementation advantages.

Specifically:

| Component | Language |
|------------|------------|
| Event ingestion | Python |
| Context Builder | Python |
| Mock LMS APIs | Python |
| MCP services | Python |
| LLM Decision Service | Python |
| Policy Validation Service | Python |
| Delivery Routing Service | Python |
| Audit Logging Services | Python |
| LearnCloud/LearnCard Adapter | TypeScript |
| AWS infrastructure (IaC) | CloudFormation (YAML) — revised 2026-07-20, was AWS CDK/TypeScript |
| Demo UI | React/TypeScript |

## Rationale

### AI and LLM Ecosystem

The primary objective of the POC is to evaluate AI-assisted orchestration, routing, transformation, and decision making.

Python provides the strongest ecosystem for:

- LLM integration
- prompt engineering
- structured output validation
- JSON transformation
- schema validation
- test fixture generation
- MCP implementation

The majority of examples, libraries, and community support for AI-centric development currently target Python first.

Because the POC is focused on validating AI and orchestration assumptions rather than maximizing transaction throughput, development velocity is prioritized over raw runtime performance.

### FastAPI and Pydantic

FastAPI and Pydantic provide:

- strong type validation,
- OpenAPI generation,
- concise API implementation,
- straightforward schema modeling, and
- excellent support for JSON-heavy workloads.

These characteristics align well with the needs of mock LMS APIs, MCP services, orchestration components, and transformation services.

### AWS Compatibility

Python is a first-class runtime for:

- AWS Lambda,
- Step Functions,
- EventBridge,
- Bedrock, and
- DynamoDB integrations.

The anticipated workload is event-driven and I/O-bound rather than CPU-bound.

The expected bottlenecks are:

- external API calls,
- LLM inference,
- credential issuance,
- credential delivery, and
- network latency.

These factors dominate execution time and substantially outweigh language-level performance differences.

### Performance Considerations

TypeScript running on Node.js generally offers higher raw execution performance than Python.

However, the POC workload is not expected to be performance constrained by language runtime efficiency.

Most orchestration steps involve:

- reading events,
- retrieving context,
- invoking external services,
- invoking LLMs,
- transforming JSON payloads, and
- delivering credentials.

The latency of these external operations is expected to be orders of magnitude greater than any performance differences between Python and TypeScript.

The team concluded that development speed, clarity, and ecosystem support are more important than runtime throughput for this phase of work.

If future performance requirements justify it, individual services may be reimplemented in a different language without changing the overall architecture.

### LearnCloud/LearnCard Integration

During architecture evaluation, the team determined that portions of the desired LearnCloud/LearnCard issuance workflow depend on functionality exposed through the LearnCard TypeScript SDK.

As a result, a TypeScript-based adapter will be implemented for LearnCloud/LearnCard integration.

The remainder of the platform remains language-agnostic and continues to use Python.

### Why a Python LearnCard SDK Will Not Be Developed

The team considered creating a Python wrapper around LearnCloud/LearnCard functionality.

If the required issuance capabilities were exposed through stable public APIs, the POC could invoke those APIs directly from Python and no custom SDK would be necessary.

The primary reason for using the LearnCard TypeScript SDK is that it exposes functionality required by the desired issuance workflow that is not available through a sufficiently documented or supported language-neutral API surface. The LearnCard docs position their credential issuance tutorial around Node.js and provide TypeScript/JavaScript examples for initialization, issueCredential, and sendCredential.   Recreating equivalent Python behavior would likely require reproducing parts of:
* DID/key handling
* local signing behavior
* network/profile mechanics
* transport semantics
* possibly plugin-style architecture used in their JS ecosystem
This goes beyond the scope of building a wrapper.

Additionally, we have the architectural goal of wallet neutrality, but a Python SDK that wraps LearnCard too deeply pushes toward vendor-coupled abstractions.

#### Recommended Structure

Python core
* build OBv3 payload
* validate business rules
* route to wallet adapters.

Thin LearnCard adapter that is a small Node Lambda/service that calls the LearnCard SDK as LearnCard does not expose sufficient API endpoints for direct HTTP calls.

#### Benefits
1. Lower maintenance risk
    A homegrown Python SDK becomes your responsibility whenever LearnCard changes package APIs, auth flows, profile mechanics, or signing behavior.
2. Cleaner abstraction boundary
    A narrow issuer interface such as:
    * `sign_credential(unsigned_vc)`
    * `deliver_to_wallet(provider, credential, recipient)`
    * `get_delivery_status(id)`
3. Better portability
    If later you add another wallet/provider, you swap or add adapters rather than unraveling a Python package that mirrors LearnCard internals.

### Architectural Separation

The architecture will isolate LearnCloud/LearnCard-specific implementation details behind an adapter boundary.

Core orchestration services must not depend on LearnCard SDK types or workflows.

This allows future support for:

- DCC Issuer,
- Other Open Badges / CLR issuers,
- SmartResume,
- Trusted Career Profile workflows, and
- additional credential platforms.

## Consequences

### Positive

- Faster AI-focused development.
- Strong ecosystem support for MCP and LLM experimentation.
- Simplified implementation of mock services and transformations.
- Reduced complexity in orchestration services.
- Vendor-supported LearnCloud integration.
- Clear separation between orchestration logic and credential platform implementations.

### Negative

- Multiple implementation languages will exist within the repository.
- Additional build and deployment tooling is required for TypeScript components.
- Developers must be familiar with both Python and TypeScript.
- Some integration logic cannot be reused directly across languages.

### Mitigations

- Limit TypeScript usage to vendor-specific adapters and UI.
- Maintain language-neutral interfaces between services.
- Keep LearnCloud-specific logic isolated behind a dedicated adapter boundary.
- Avoid introducing additional TypeScript services unless a clear requirement emerges.

## Revision History

### 2026-07-20 — Infrastructure-as-code: CloudFormation instead of AWS CDK

**Change.** The infrastructure-as-code tool is **CloudFormation (YAML)**, not AWS CDK (TypeScript); the language table above is updated accordingly. This reverses the original CDK choice. Per [ADR-0019](./0019-adr-governance-and-lifecycle.md), the superseded option and its rationale are kept visible here rather than deleted.

**Unchanged — compute is AWS Lambda.** This revision concerns only the IaC authoring tool. The serverless compute model remains AWS **Lambda + SQS + EventBridge**, decided in [ADR-0015](./0015-orchestrator-execution-model.md) and reaffirmed here — we are **not** adopting a long-running ECS/Fargate model (the CloudFormation reference we are borrowing from happens to be ECS-based; we take its CloudFormation + CI patterns, not its compute model).

**Why CloudFormation over CDK for this POC.**

- **Ownership / hand-off.** The Ops team maintains our AWS environment and already has a working CloudFormation reference (per-service templates + a declarative, ordered deploy) we can adapt; they are most fluent in CloudFormation. For a hand-off-oriented POC, matching the tooling Ops will own outweighs CDK's authoring ergonomics.
- **Scale and timeline.** CDK's advantages — less code via constructs, loops, refactoring — compound on large, long-lived, evolving infrastructure. This POC is small (~14 small services), single-environment, and approaching a code freeze, so those advantages are muted while CDK's costs land now: a `cdk bootstrap` dependency and a CLI/synth step in the Ops account, a heavy fast-moving `aws-cdk-lib` dependency, a net-new build vs. adapting Ops's proven templates, and a synthesized-CloudFormation debugging indirection for whoever owns it after hand-off.
- **Language fit.** CDK's best-supported language is TypeScript, which cuts against this ADR's own goal of minimizing TypeScript. (Python-CDK exists but is the rougher, less-polished path.) Dropping CDK removes a TypeScript surface, leaving TS confined to the LearnCard adapter and the UI — reinforcing the "limit TypeScript" mitigation above.

**Superseded option — AWS CDK.** CDK (ideally its Python bindings, to preserve language consistency) remains a reasonable choice if this system becomes long-lived and Python-team-owned; it was set aside for the reasons above, not because it is unsuitable.