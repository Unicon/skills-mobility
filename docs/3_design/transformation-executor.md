# Transformation Executor Design

Status: Draft
Date: 2026-07-18
Related: [Requirements](../2_requirements/transformation-executor.md) · [POC Component Boundary Matrix](./poc-component-boundaries.md) · [Orchestrator Design](./orchestrator.md) · [Field Mapping LLM Decision Service Design](./field-mapping-llm-decision-service.md) · [ADR-0005](../decisions/0005-schema-mapping-language.md) · [ADR-0017](../decisions/0017-three-transformation-phases.md)

## 1. Overview

The **Transformation Executor** is the deterministic JSONata execution boundary in the transformation pipeline. It has one job: bind the source payloads and synthesized values from a workflow execution step into a JSONata evaluation context, run the mapping, and return the resulting target payload.

This service is intentionally narrow. It performs no AI reasoning, no field classification, and no delivery logic. The decision about *what* mapping to run belongs to the Field Mapping LLM Decision Service. The decision about *whether* the output is policy-valid belongs to the Policy Rules Service. The Transformation Executor answers only: does this mapping, applied to this context, produce a well-formed output?

Per [ADR-0017](../decisions/0017-three-transformation-phases.md), the default POC transformation path has three phases:

| `transformation_type` | Source artifacts | Target |
| --- | --- | --- |
| `credential_template` | LMS learning-context artifacts | Credential-template schema |
| `issuer_payload` | Learner-specific LMS artifacts plus credential template | Issuer target schema / unsigned OBv3 payload |
| `wallet_payload` | Issued badge artifact plus wallet-delivery-specific context | Wallet target schema / wallet delivery payload |

The same executor serves all three phases. The phase label is metadata used for logging; execution logic does not branch on it.

Per [Orchestrator Design §6](./orchestrator.md), the `execute_translation` plan step — currently satisfied by in-process stubs (`_execute_issuer_payload_translation`, `_execute_wallet_payload_translation` in `orchestrator/actions.py`) — is the primary consumer of this service. Wiring the Orchestrator to call the live executor instead of the stubs is the companion implementation issue (#98).

## 2. What the Service Produces

For each invocation the service produces one of two outcomes:

**Succeeded:** the transformed target payload as a JSON object. For `credential_template` requests this is the achievement content; for `issuer_payload` requests this is the unsigned OBv3 issuer payload; for `wallet_payload` requests this is the wallet delivery payload.

**Failed:** a structured failure envelope with an `error_type` and message. No unhandled exception or HTTP 500 is returned.

The service is stateless. It does not store results. The Orchestrator persists the step output as part of its own execution record.

## 3. Runtime Shape

The execution path for one request is:

```text
Orchestrator
  -> POST /execute
      -> parse + validate request (Pydantic)
      -> build evaluation context: { "source_payloads": {...}, "synthesized": {...} }
      -> jsonata.Jsonata(mapping)          # parse (constructor raises on a syntax error)
      -> .evaluate(context)               # run the mapping
      -> well-formedness check (result must be a dict)
      -> emit invocation log
      -> return ExecutionResponse
```

The JSONata parse step re-uses the same `jsonata.Jsonata(expr)` surface that Field Mapping uses for parse-checking. The evaluate step is the new capability this service introduces to the project (see Section 6).

If any step in this path raises or produces a non-dict result, the service returns a `status: "failed"` response rather than propagating an exception.

## 4. Request Contract

The request carries all execution inputs inline:

```json
{
  "execution_id": "exec_123",
  "event_id": "evt_123",
  "correlation_id": "corr_123",
  "transformation_type": "issuer_payload",
  "delivery_target": "learncard_issuer",
  "mapping": "{ \"@context\": source_payloads.learner_context.context, \"credentialSubject\": { \"id\": source_payloads.learner_context.did, \"achievement\": { \"name\": source_payloads.credential_template.name, \"description\": synthesized.achievement_description } } }",
  "source_payloads": {
    "learner_context": {
      "did": "did:example:abc123",
      "context": ["https://www.w3.org/2018/credentials/v1"]
    },
    "credential_template": {
      "name": "JavaScript Fundamentals"
    }
  },
  "synthesized": {
    "achievement_description": "Demonstrated mastery of core JavaScript concepts."
  }
}
```

`delivery_target` is absent (not `null`) for `credential_template` requests, consistent with how Field Mapping handles that phase (see [Field Mapping Design §4](./field-mapping-llm-decision-service.md)).

`synthesized` is an empty dict `{}` when the mapping required no synthesis. The evaluation context always includes the `synthesized` key so JSONata expressions that reference `synthesized.*` paths are consistent whether or not synthesis ran.

The mapping string is the same JSONata artifact that Field Mapping generates and parse-checks. The executor executes it without re-generating or re-interpreting it.

## 5. Response Contract

**Succeeded:**

```json
{
  "status": "succeeded",
  "transformation_type": "issuer_payload",
  "result": {
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "credentialSubject": {
      "id": "did:example:abc123",
      "achievement": {
        "name": "JavaScript Fundamentals",
        "description": "Demonstrated mastery of core JavaScript concepts."
      }
    }
  }
}
```

**Failed:**

```json
{
  "status": "failed",
  "transformation_type": "issuer_payload",
  "error": {
    "error_type": "eval_error",
    "message": "JSONata evaluation error: path 'source_payloads.learner_context.missing_field' resolved to undefined"
  }
}
```

Both responses are HTTP 200. The `status` field is the semantic outcome indicator. HTTP error codes (4xx, 5xx) are reserved for transport-level problems (malformed JSON body → 422, service crash → 500).

The `result` key is absent on failure; the `error` key is absent on success.

## 6. JSONata Execution Engine

### Library

**`jsonata-python>=0.5`** is the execution engine. This is the same library used by the Field Mapping LLM Decision Service for parse-checking. The Transformation Executor is the first service in the project to call the library's evaluate path.

Field Mapping parse-checks by constructing the expression — the constructor raises
`JException` on a syntax error and it never evaluates:

```python
try:
    jsonata.Jsonata(mapping)   # parse-only; raises on a syntax error
except Exception as ex:        # JException at compile time
    ...                        # record a parse error
```

The Transformation Executor extends this to the evaluate path:

```python
expr = jsonata.Jsonata(mapping)   # parse (raises on a syntax error → parse_error)
result = expr.evaluate(context)   # new capability introduced here
```

The engine is an integrated dependency, not an external service. No separate evaluation-platform vetting is needed (per #97).

### Evaluation context shape

The context passed to `.evaluate()` is always:

```python
context = {
    "source_payloads": source_payloads,  # dict of named payload dicts
    "synthesized": synthesized,           # dict of placeholder_id -> value, or {}
}
```

This shape is the canonical contract shared between Field Mapping (which generates JSONata referencing `source_payloads.<alias>.<path>` and `synthesized.<placeholder_id>`) and the Transformation Executor (which binds those references at evaluation time). The shape is documented explicitly here so that Field Mapping and the executor remain consistent as they evolve independently.

Direct mapping example in JSONata:

```
source_payloads.learner_context.course.name
```

Synthesis-backed field example in JSONata:

```
synthesized.achievement_description
```

Both reference paths live under the same root context object and are resolved by the same JSONata evaluation call.

### Raw operators and HTML entities

The executor returns the raw result of JSONata evaluation with no post-processing. Field Mapping is expected to generate JSONata that uses raw-string operators (`$string(x, true)`) where needed to prevent JSONata's default HTML-entity escaping of string values. The executor enforces no additional escaping or unescaping.

### Well-formedness check

After evaluation, the executor confirms that the result is a Python dict (JSON object). A non-dict result — a scalar, a list, or null — is treated as a `"malformed_output"` failure. Deep schema validation (confirming required fields, field types, target-schema conformance) is explicitly outside scope; that is the Policy Rules Service's job.

## 7. Error Handling

All failure modes return HTTP 200 with `status: "failed"` and a structured error:

| Scenario | `error_type` | Handling |
| --- | --- | --- |
| JSONata parse error (malformed mapping string) | `"parse_error"` | `jsonata.Jsonata(mapping)` constructor raises; fail before evaluate |
| JSONata evaluation error (runtime exception) | `"eval_error"` | Catch exception from `.evaluate()`; include message |
| Missing path in source_payloads (JSONata resolves to undefined/null) | `"eval_error"` | JSONata returns undefined for missing paths; if this causes a non-dict result it surfaces as `malformed_output` |
| Evaluation result is not a dict | `"malformed_output"` | `isinstance(result, dict)` check; fail with the actual result type in the message |
| Pydantic request validation failure | (HTTP 422 from FastAPI) | Standard FastAPI validation error response |

The service does not implement repair-retry. If the mapping is invalid, the failure is returned directly. Retry logic, if ever needed, belongs in the calling Orchestrator — not silently inside the executor.

## 8. Observability and Audit

Each invocation emits a structured log record at `INFO` level before returning. The record includes:

| Field | Source |
| --- | --- |
| `execution_id` | request |
| `event_id` | request |
| `correlation_id` | request |
| `transformation_type` | request |
| `delivery_target` | request (absent for `credential_template`) |
| `status` | outcome |
| `error_type` | outcome (absent on success) |
| `mapping_digest` | first 64 characters of the mapping string (sufficient to identify which mapping ran without storing the full text) |
| `output_size_bytes` | `len(json.dumps(result))` on success; absent on failure |

This is the minimum needed to correlate an executor invocation with the Orchestrator's step record and the Field Mapping invocation log that produced the mapping. No separate audit store is required; the Orchestrator owns the correlated execution trail.

## 9. Suggested Module Layout

```text
services/transformation-executor/
  pyproject.toml
  README.md
  .env.example
  src/
    transformation_executor/
      app.py          # FastAPI app factory, /execute endpoint, /healthz
      config.py       # Settings (TRANSFORMATION_EXECUTOR_PORT=8160, log level)
      contracts.py    # Pydantic request/response schemas
      executor.py     # build_context(), run_mapping(), well-formedness check
  tests/
    test_executor.py  # unit tests for executor.py (parse errors, eval errors, success)
    test_api.py       # HTTP-layer tests via TestClient (happy path, 422, failed status)
```

Responsibilities:

- `app.py`: create the FastAPI instance, register `/execute` (POST) and `/healthz` (GET), configure `logging.basicConfig` in `run()` per the pre-PR checklist.
- `config.py`: `Settings` model — `TRANSFORMATION_EXECUTOR_PORT` (default `8160`), `TRANSFORMATION_EXECUTOR_LOG_LEVEL` (default `INFO`).
- `contracts.py`: `ExecutionRequest` (Pydantic model for request body), `ExecutionResponse` (Pydantic model for response), `ExecutionError` (structured error), `TransformationTypeEnum` (Literal / StrEnum for the three phases).
- `executor.py`: `build_context(source_payloads, synthesized)`, `run_mapping(mapping, context)` — all JSONata interaction lives here; app.py delegates entirely to this module.

`executor.py` is pure logic with no HTTP or FastAPI imports, making it testable without a running server.

## 10. Build Order

1. Define `ExecutionRequest`, `ExecutionResponse`, and `ExecutionError` in `contracts.py`. Confirm the context shape `{ "source_payloads": {...}, "synthesized": {...} }` matches Field Mapping's JSONata generation assumptions.
2. Implement `executor.py`: `build_context`, parse-check via the `jsonata.Jsonata(mapping)` constructor (catch the raise), evaluate via `.evaluate()`, well-formedness check. Write unit tests for each failure path before wiring to FastAPI.
3. Implement `app.py`: `POST /execute` calling `executor.py`, `GET /healthz`, `logging.basicConfig` in `run()`.
4. Write `test_api.py` HTTP-layer tests: happy path, request validation (422), failed execution (parse error), failed execution (eval error).
5. Wire the Orchestrator's `execute_translation` step to call this service (companion issue #98). Update the Orchestrator's action registry to use an HTTP client that calls `/execute` when configured, falling back to the in-process stub when the executor URL is not set.

This order keeps the service measurable from the start: `executor.py` is tested before any HTTP surface exists.

## 11. Implementation Decisions

Decisions made during pre-development design review that are not captured in existing ADRs.

### Service form vs. in-process library

**Decision:** standalone deterministic service (`services/transformation-executor`, FastAPI, `POST /execute`).

**Alternative considered:** an in-process Python library imported directly by the Orchestrator. This would be simpler for the first integration point, avoiding an HTTP hop.

**Rationale for service form:** Every other component in the transformation pipeline — Field Mapping, Field Synthesis, Delivery Router, Context Builder — is a standalone service. The [POC Component Boundary Matrix](./poc-component-boundaries.md) treats the Transformation Executor as a top-level component with its own boundary row, framed as a stand-in for an external mock LIF Translator. Keeping it as a service preserves that boundary (which will matter when the real LIF Translator is evaluated), makes it independently deployable and testable, and is consistent with the Orchestrator's seam pattern. The extra HTTP hop is negligible for the POC.

A library approach would also force the Orchestrator to take a direct dependency on `jsonata-python`, pulling JSONata execution into the Orchestrator's process without a clean boundary for later replacement.

### Inline inputs vs. mapping store reference

**Decision:** all inputs arrive inline — the mapping string, source payloads, and synthesized values are carried in the request body.

**Alternative considered:** the request carries a `mapping_artifact_ref` and the executor dereferences it against the Mapping Template Storage (Mock LIF MDR), as described in the long-term boundary doc row ("Lookup identifier(s) to the stored/generated mapping specification").

**Rationale for inline:** The boundary doc describes the long-term architecture. For the POC, each service owns its own artifact store, and there is no shared store the executor and the Orchestrator both have access to. The inline-handoff pattern is already established: Field Mapping returns its synthesis request inline rather than requiring the Orchestrator to look it up separately. Carrying the mapping inline follows the same pattern and avoids introducing an artifact-store lookup dependency during the POC. This makes **Field Mapping returning its generated mapping inline a companion requirement**: the Orchestrator must extract the mapping from the Field Mapping response and pass it to the executor rather than only passing a ref.

When a real Mapping Template Storage is introduced later, the executor's request contract can add an optional `mapping_artifact_ref` field as a fallback; the inline `mapping` field takes precedence when both are present.

### jsonata-python reuse

**Decision:** reuse `jsonata-python` (already a project dependency via Field Mapping) for both parse-checking and evaluation. No additional library is introduced.

**Rationale:** `jsonata-python` is already selected and integrated ([Field Mapping Design §17](./field-mapping-llm-decision-service.md)). It provides both the parse surface Field Mapping uses (constructing `jsonata.Jsonata(mapping)`, which raises on a syntax error) and the `.evaluate()` execution surface the Transformation Executor needs. Introducing a separate library (e.g. a Node.js subprocess with the reference JSONata engine) adds a runtime dependency, a process boundary, and a dialect divergence risk. The integrated library avoids all of that. Per #97, the engine requires no separate vetting.
