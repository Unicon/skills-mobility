# Transformation Executor Requirements

Status: Draft
Date: 2026-07-18
Related: [Design](../3_design/transformation-executor.md) · [POC Component Boundary Matrix](../3_design/poc-component-boundaries.md) · [Orchestrator Design](../3_design/orchestrator.md) · [Field Mapping LLM Decision Service Requirements](./field-mapping-llm-decision-service.md) · [ADR-0005](../decisions/0005-schema-mapping-language.md) · [ADR-0017](../decisions/0017-three-transformation-phases.md)

## 1. Purpose

The **Transformation Executor** is the deterministic execution boundary inside the transformation pipeline. Its job is to run a JSONata mapping against the merged transformation context — source payloads plus synthesized field values — and return the resulting target payload.

The service carries no AI reasoning, no field classification, and no delivery logic. It answers one operational question: given a JSONata mapping and an execution context, produce the target JSON object.

This service is the component that makes the Field Mapping LLM Decision Service's output useful: Field Mapping decides *how* to map; the Transformation Executor *does* the mapping.

## 2. Responsibilities

The Transformation Executor is responsible for:

- accepting an execution request carrying the JSONata mapping string, source payloads, synthesized field values, target schema, and transformation type,
- binding the source payloads and synthesized values into a single evaluation context,
- executing the JSONata mapping against that context using the `jsonata-python` library,
- performing a well-formedness check on the resulting output (it must be a JSON object) and validating the output against the supplied target schema,
- returning the transformed target payload on success,
- and returning a clean structured failure response on parse, evaluation, or validation error.

The service is not responsible for:

- LLM reasoning, field classification, or natural-language generation,
- fetching source payloads from LMS APIs or any other external system,
- selecting delivery targets,
- storing or loading mapping artifacts from a mapping store (inputs arrive inline for the POC),
- issuing or delivering credentials,
- or business and institutional policy validation of the output (that is the Policy Rules Service's job).

## 3. Transformation Phases

Per [ADR-0017](../decisions/0017-three-transformation-phases.md), the default expected POC transformation path has three distinct phases, each with its own source artifact set and target schema:

| `transformation_type` | Primary sources | Target |
| --- | --- | --- |
| `credential_template` | LMS learning-context artifacts | Credential-template schema |
| `issuer_payload` | Learner-specific LMS artifacts plus stored credential template | Issuer target schema / unsigned OBv3 payload |
| `wallet_payload` | Issued badge artifact plus wallet-delivery-specific context | Wallet target schema / wallet delivery payload |

The Transformation Executor is **phase-agnostic**: the same service and the same execution path handle all three phases. The difference between phases is which mapping and source payloads the Orchestrator supplies, not a branching code path inside the executor.

## 4. Inputs and Outputs

### Request inputs

The request carries all execution inputs inline. The POC does not use a lookup-by-reference pattern because each service owns its own artifact store and the inline handoff pattern is already established by Field Mapping.

| Input | Purpose |
| --- | --- |
| `execution_id` and correlated identifiers | Tie the request to one workflow execution and its logs |
| `transformation_type` | Identifies which ADR-0017 phase this execution serves; used for logging and context |
| `delivery_target` | Optional; identifies the downstream delivery target for `issuer_payload` and `wallet_payload` requests; absent for `credential_template` |
| `mapping` | The JSONata mapping string produced by the Field Mapping LLM Decision Service |
| `target_schema` | The target catalog JSON schema Field Mapping uses to constrain generation; supplied inline so the executor can validate structural conformance of its output |
| `source_payloads` | Named source artifact dict; keys are stable payload aliases (e.g. `learner_context`, `credential_template`); values are the transient JSON objects |
| `synthesized` | Dict of synthesized field values keyed by `placeholder_id`; empty dict when no synthesis was needed |

### Outputs

| Output | Purpose |
| --- | --- |
| `status` | `"succeeded"` or `"failed"` |
| `transformation_type` | Echo of the input; allows callers to correlate the response without inspecting the payload |
| `result` | The transformed target payload as a JSON object; present only on `succeeded` |
| `error` | Structured error detail; present only on `failed` |

## 5. Functional Requirements

- **FR-TE-1** The service SHALL accept exactly one transformation request per invocation. Each request maps to one phase from ADR-0017.
- **FR-TE-2** The request SHALL identify `transformation_type` explicitly as one of `credential_template`, `issuer_payload`, or `wallet_payload`.
- **FR-TE-3** The request SHALL carry the JSONata mapping string, source payloads, and synthesized values inline. The service SHALL NOT load mapping artifacts or source payloads from external stores.
- **FR-TE-4** The service SHALL bind the request inputs into a single evaluation context of the shape `{ "source_payloads": {...}, "synthesized": {...} }` before executing the mapping. Direct mapping expressions reference `source_payloads.<alias>.<path>`; synthesis-backed fields reference `synthesized.<placeholder_id>`. This context shape SHALL be consistent with how Field Mapping generates JSONata.
- **FR-TE-5** The service SHALL execute the JSONata mapping using the `jsonata-python` library's evaluate path (`jsonata.Jsonata(mapping).evaluate(context)`). This service is the first in the project to use the library's evaluate path; Field Mapping uses only the parse path (constructing `jsonata.Jsonata(mapping)`, which raises on a syntax error).
- **FR-TE-6** The service SHALL perform two Layer-A checks on the evaluation result: (1) a well-formedness check — the result MUST be a JSON object (dict); and (2) structural schema validation — the result MUST conform to the `target_schema` supplied in the request. A non-object result or a schema validation failure SHALL both be treated as `malformed_output` failures.
- **FR-TE-7** The service SHALL treat the following as failures and return a structured failure response rather than an unhandled exception or HTTP 500: a JSONata parse error, a JSONata evaluation error, and a non-object evaluation result. A missing source path referenced in the mapping resolves to undefined/null in JSONata and is not an independent failure category; it only becomes a failure if the overall evaluation result is a non-object (surfacing as `malformed_output`, not a distinct error type).
- **FR-TE-8** A failure response SHALL include a `status` of `"failed"` and a structured `error` with at minimum an `error_type` (e.g. `"parse_error"`, `"eval_error"`, `"malformed_output"`) and a human-readable `message`.
- **FR-TE-9** The service SHALL validate the transformed output against the target schema supplied in the request (structural conformance: required fields present, no unexpected shape). Business and institutional policy validation remains the responsibility of the Policy Rules Service.
- **FR-TE-10** The service SHALL NOT invoke any LLM, generate any synthesized text, or make any delivery calls.
- **FR-TE-11** The service SHALL be phase-agnostic: the same execution path handles `credential_template`, `issuer_payload`, and `wallet_payload` requests without branching on phase.
- **FR-TE-12** The service SHALL produce only structured JSON output (the transformed target payload). It SHALL NOT produce HTML-escaped output. JSONata raw-string operators SHALL be used in generated mappings if HTML-entity escaping is a concern; the executor enforces consistent evaluation behavior with how Field Mapping parse-checks its output.
- **FR-TE-13** The service SHALL emit an invocation log for each request. The log SHALL include at minimum: `execution_id`, `event_id`, `correlation_id`, `transformation_type`, `delivery_target` when present, status, and error type when failed.
- **FR-TE-14** The service SHALL be callable by the Orchestrator as the implementation of the `execute_translation` plan step, replacing the in-process stub in `orchestrator/actions.py`. The Orchestrator MAY fall back to the in-process stub when the executor is unconfigured or unavailable so the workflow still runs in degraded mode.

## 6. Validation and Audit

- **FR-TE-15** The service SHALL log each invocation at `INFO` level with the correlation identifiers, transformation type, and final status before returning.
- **FR-TE-16** The invocation log SHALL be structured (JSON-compatible) so it can be correlated with Orchestrator execution records.
- **FR-TE-17** Successful invocations SHALL return the full transformed payload inline. The executor is stateless and does not store results; the Orchestrator persists the step output as its own artifact.

## 7. Local vs AWS Requirements

- **FR-TE-19** The service SHALL be runnable locally without any external infrastructure dependency (no cloud storage, no database, no live LMS). All inputs arrive inline; the service is effectively stateless.
- **FR-TE-20** The local service SHALL be startable via `uv run` (package `transformation_executor`). The port SHALL be configurable via `TRANSFORMATION_EXECUTOR_PORT` with a default of `8160`.
- **FR-TE-21** The service SHALL support an in-process test mode where the FastAPI `TestClient` is used without a live HTTP server, consistent with the testing pattern of sibling services.
- **FR-TE-22** For the AWS-shaped deployment target, the service SHALL be invocable through the same logical boundary from the Orchestrator whether hosted as a standalone Lambda-sized service or as a handler in a shared runtime.

## 8. Out of Scope

The Transformation Executor does not need to provide:

- LLM reasoning, field classification, or prompt assembly,
- mapping artifact generation or storage,
- source payload retrieval from LMS APIs or artifact stores,
- business and institutional policy validation of the output,
- delivery routing or credential issuance,
- multi-turn or stateful execution,
- repair-retry loops (the mapping either runs or it fails cleanly),
- or human-in-the-loop review flows.

