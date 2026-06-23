# ADR-0016: Delivery Routing Topology and Adapter Boundaries

- Status: Proposed
- Date: 2026-06-22
- Related: [ADR-0003](./0003-programming-language.md) · [ADR-0008](./0008-transformation-mapping-service-decomposition.md) · [ADR-0009](./0009-workflow-actions-orchestration-model.md) · [ADR-0011](./0011-orchestration-runtime-technology.md)

## Context

The current architecture already assumes a **Delivery Router / Target Adapters** boundary, but it does not yet settle exactly where the line falls between the orchestration runtime, the router, and individual delivery adapters.

That ambiguity now matters because the full POC is expected to include at least three delivery adapters:

- a **LearnCard Issuer Adapter** that must call the LearnCard TypeScript SDK,
- a **LearnCard Wallet Adapter** that is expected to call a LearnCard API directly from Python, and
- a **SmartResume Wallet Adapter**.

Post-POC, the architecture may need to support many more downstream targets.

The full POC is also expected to include the **Field Mapping LLM Decision Service**, **Field Synthesis LLM Decision Service**, and deterministic **Transformation Executor** described in ADR-0008. Those components are expected to perform the vast majority of target-payload shaping before the delivery layer is invoked.

ADR-0003 already established two important constraints:

- LearnCard-specific implementation details must remain behind an adapter boundary.
- The LearnCard issuer integration should be implemented as a thin Node/TypeScript adapter rather than as a Python wrapper around the SDK.

ADR-0009 and ADR-0011 established two more:

- the **Workflow Actions LLM Decision Service** is the top-level planner,
- and the **Orchestration Service** is the deterministic executor of the validated plan.

That means the delivery layer must not become a second planner. It can execute approved delivery steps, but it must not decide which delivery steps belong in the workflow, whether delivery should happen at all, or what business path should be taken.

The open questions are:

1. Should the Orchestration Service call delivery adapters directly?
2. If a separate **Delivery Router Service** exists, should it also reshape target-specific payloads, or should that remain adapter-owned?

## Decision Drivers

- Preserve the planning boundary chosen in ADR-0009
- Keep the Orchestration Service focused on executing validated plans rather than accumulating delivery-integration details
- Support multiple adapters across multiple runtimes and languages
- Provide a stable internal delivery interface even as adapter count grows
- Centralize shared delivery-side concerns such as config lookup, retries, timeouts, correlation, and normalized result handling
- Keep semantic payload shaping in the transformation pipeline and limit adapters to final-mile protocol binding
- Build Phase 1 in a way that still fits the expected full-POC and post-POC adapter growth

## Decision

We will keep a **separate Delivery Router Service** between the Orchestration Service and downstream delivery adapters.

The boundary will be defined as follows:

- The **Workflow Actions LLM Decision Service** decides which delivery-related steps appear in the workflow plan.
- The **Orchestration Service** executes those validated steps in order and remains the owner of the unified workflow execution record.
- The **Delivery Router Service** is a thin delivery execution facade. It dispatches already-approved delivery actions to the correct adapter and applies shared delivery mechanics.
- Each **delivery adapter** owns only the minimal target-specific conversion still required to turn an already-shaped payload into vendor-specific SDK or API calls.

For the POC, the architecture should treat each delivery adapter as its own component boundary behind a language-neutral invocation contract. The initial expected adapters are:

- **LearnCard Issuer Adapter** in Node/TypeScript
- **LearnCard Wallet Adapter** in Python
- **SmartResume Wallet Adapter** in Python

This ADR defines a component boundary, not a mandatory deployment shape. Separate Lambda-sized services are a valid implementation, but the more important constraint is that the Orchestration Service must not import or depend directly on vendor SDK/runtime details.

### Delivery Router Responsibilities

The Delivery Router Service owns:

- dispatching a requested delivery action to the configured adapter,
- adapter endpoint or binding lookup,
- delivery-side configuration lookup,
- applying shared timeout and retry policy,
- attaching correlation and execution identifiers,
- normalizing adapter responses into a common result envelope,
- recording standardized delivery-attempt and delivery-result records, and
- returning delivery results to the Orchestration Service.

### Adapter Responsibilities

Each delivery adapter owns:

- validating its router-facing payload contract,
- applying any final protocol, envelope, or SDK parameter adjustments still required after upstream transformation,
- handling vendor-specific auth/session/bootstrap details,
- making the actual vendor SDK or API calls,
- interpreting vendor-specific responses and errors, and
- returning a normalized adapter result to the router.

### Explicit Non-Responsibilities of the Delivery Router

The Delivery Router Service does **not** own:

- choosing whether delivery should happen,
- choosing which targets are eligible,
- selecting workflow order or branching,
- fetching source context,
- generating transformation mappings,
- generating synthesized field values,
- performing substantive field-level or schema-level payload reshaping that belongs in the transformation pipeline,
- applying business-policy decisions beyond configured mechanical retry/timeout behavior, or
- reshaping payloads in a target-specific way that duplicates adapter logic.

## Recommended Contract Shape

The router-facing API should be a stable envelope plus **versioned action-specific payload schemas**, not one universal delivery payload.

For example, the delivery layer may expose actions such as:

- `issue_learncard_badge`
- `deliver_to_learncard_wallet`
- `deliver_to_smartresume`

Each action should have its own documented input and output schema. Those payloads should already be substantially shaped for the target by the upstream transformation pipeline. The Delivery Router validates the envelope and dispatch metadata. The adapter performs only the final target-specific conversion still needed by the vendor API or SDK.

This means the router can expose a stable invocation model without pretending that all downstream delivery actions accept the same payload.

## Options Considered

| Option | Description | Main concern |
| --- | --- | --- |
| Orchestration Service calls adapters directly | The Orchestration Service invokes each adapter component itself and owns adapter selection, config lookup, retries, and result handling | Orchestration accumulates delivery-integration concerns and must know too much about each adapter's endpoint, policy, and result shape |
| Orchestration Service -> Delivery Router Service -> adapters (chosen) | A separate delivery facade dispatches approved actions to adapters and owns shared delivery mechanics while adapters own vendor-specific behavior | Adds an extra component and network hop that must justify itself by actually carrying shared behavior |
| Orchestration Service -> Delivery Router Service -> adapters, with router-owned target-specific payload reshaping | Router dispatches and also performs target-specific request shaping before calling adapters | Router becomes a hidden transformation layer and starts collapsing into adapter logic or a second orchestrator |

## Why This Is Worth It Here

If the architecture expected only one delivery adapter, or two very similar adapters in the same runtime, direct calls from the Orchestration Service would likely be simpler.

That is not the shape of this system.

The expected full POC already includes:

- multiple adapters,
- mixed implementation runtimes,
- at least one SDK-backed adapter that cannot live naturally inside the Python orchestration layer, and
- a likely path to additional adapters later.

Without a separate router, the Orchestration Service would need to know, per adapter:

- where it is,
- how to call it,
- what timeout and retry behavior is appropriate,
- where delivery configuration lives,
- how to interpret success and failure responses, and
- how to emit normalized delivery records for audit and UI use.

Those are delivery-execution concerns, not workflow-planning concerns. Keeping them in a router preserves a cleaner orchestration boundary and gives future adapters one place to plug in.

## Boundary Clarifications

### The router is not a second orchestrator

The Delivery Router Service may choose **how to dispatch** an already-approved action to the correct adapter implementation. That is dispatch, not planning.

It must not:

- add new workflow steps,
- skip approved workflow steps for business reasons,
- choose targets on its own, or
- reinterpret upstream delivery intent.

### The transformation pipeline owns payload shaping; adapters own only final-mile binding

The full POC should expect the Field Mapping, Field Synthesis, and Transformation Executor steps to produce payloads that are already close to the target system's required structure.

If a payload still needs minor adjustment to match LearnCard SDK method calls, LearnCard API parameters, request envelopes, or SmartResume API details, that final-mile work is adapter work.

The router may validate that the action envelope and versioned payload schema are correct, but it should not become the place where vendor-specific request construction lives.

If an adapter starts doing substantial field mapping or schema translation, that is usually a sign that transformation responsibilities are leaking downstream.

That rule keeps the router thin, keeps adapters thin, and prevents the system from splitting target-specific logic awkwardly across multiple components.

### The Orchestration Service still owns the correlated execution view

The router should emit standardized delivery attempt/result data, but the Orchestration Service remains the owner of the unified per-workflow execution view used for auditability and the future Admin UI.

## Consequences

### Positive

- The Orchestration Service gets one stable internal delivery interface rather than per-adapter call logic.
- The delivery layer has one place for shared dispatch, timeout, retry, correlation, and normalized result behavior.
- Vendor-specific SDK/API churn stays inside adapters.
- The delivery layer stays focused on execution mechanics instead of becoming a second transformation layer.
- Adding a new adapter does not require expanding orchestration code with another set of delivery integration mechanics.
- The boundary remains compatible with the existing architectural direction in ADR-0003, ADR-0009, and ADR-0011.

### Negative

- The Delivery Router Service is an additional component and extra hop in an already large architecture.
- The router must justify its existence by staying thin and carrying real shared behavior.
- The team must maintain clear contracts between orchestrator, router, and adapters.

## Revisit Triggers

Revisit this decision if any of the following become true:

- the architecture ends up with only one adapter and the router is doing little more than pass-through forwarding,
- adapters begin to accumulate substantial field mapping or schema reshaping that should live in the transformation pipeline,
- target-specific payload conversion starts leaking into the router,
- the router begins to accumulate business branching or delivery-eligibility logic, or
- adapter growth becomes large enough that the delivery contract catalog needs a more formal registry and lifecycle model.
