# Delivery Targets LLM Decision Service

Selects which downstream systems should receive transformed data for a learner/credential event.
See the [design](../../docs/3_design/delivery-targets-llm-decision-service.md) and
[requirements](../../docs/2_requirements/delivery-targets-llm-decision-service.md).

## Pipeline (design §4 / §9)

`load catalog → screen context → one adapter selection → §9 validation → store artifacts → §3 response`

The LLM sits behind an adapter boundary (`llm_adapter.LLMAdapter`). Two implementations:

- **replay** (`replay_adapter.ReplayAdapter`, default) — returns committed canonical
  fixtures keyed by event_type, so tests and local runs need **no Bedrock / AWS access** (ADR-0013).
- **bedrock** — live Amazon Bedrock (ADR-0010) via the Converse API.

Validation (`validators.validate_selection`) is a set of **hard Layer-A gates**
(ADR-0013): a structurally valid model response is never a success on its own. Invalid
selections are stored as **failed artifacts** with their errors, never as successful
selections.

## API

```
POST /select-delivery-targets   # SelectionRequest (§6) -> SelectionResponse (§3 four-key envelope)
GET  /healthz
```

## Catalog

The available-delivery-targets catalog lives at
`src/delivery_targets/catalogs/available_delivery_targets.json` (committed; see design §5).
Resolution is service-internal — the Orchestrator supplies no target ids in the request.

## Run / test

```bash
uv run delivery-targets                      # serve on :8130 (replay mode)
uv run pytest services/delivery-targets      # unit + API tests (no AWS needed)
```

Configuration is env-driven (`DELIVERY_TARGETS_` prefix); see `.env.example`.
