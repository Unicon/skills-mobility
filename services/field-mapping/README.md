# Field Mapping LLM Decision Service

Generates ready-to-run **JSONata** transformation mappings (and synthesis requests
for placeholder-backed fields) for a given transformation phase + delivery target.
See the [design](../../docs/3_design/field-mapping-llm-decision-service.md) and
[requirements](../../docs/2_requirements/field-mapping-llm-decision-service.md).

## Pipeline (design §9 / §11)

`resolve catalogs → one adapter generation → §11 validation → store artifacts → §10 response`

The LLM sits behind an adapter boundary (`llm_adapter.LLMAdapter`). Two implementations:

- **replay** (`replay_adapter.ReplayAdapter`, default) — returns committed canonical
  fixtures, so tests and local runs need **no Bedrock / AWS access** (ADR-0013).
- **bedrock** — live Amazon Bedrock (ADR-0010) — **not implemented yet** (build-order
  item 7).

Validation (`validators.validate_generation`) is a set of **hard Layer-A gates**
(ADR-0013): a structurally valid model response is never a success on its own. The
JSONata is **parse-checked only** (`jsonata-python`), never executed. Invalid
generations are stored as **failed artifacts** with their errors, never as
successful mappings.

## API

```
POST /map      # MappingRequest (§4) -> MappingResponse (§10 five-key envelope)
GET  /healthz
```

## Catalogs

Source-resource, fetch-profile, and target schema catalogs live under
`src/field_mapping/catalogs/` (committed; see design §5). Resolution is
service-internal — the Orchestrator supplies no catalog ids.

## Run / test

```bash
uv sync --all-packages                    # create venv + install all workspace members
uv run field-mapping                      # serve on :8120 (replay mode)
uv run pytest services/field-mapping      # unit + API tests (no AWS needed)
```

Configuration is env-driven (`FIELD_MAPPING_` prefix); see `.env.example`.

## Build-order status (design §16)

Done: contracts, artifacts + store, catalogs, catalog/payload loading, validation,
replay adapter + service + API. **Deferred:** the Bedrock provider adapter +
prompts (item 7), orchestrator wiring (item 8, PR #33), and live evaluation +
DeepEval Layer B (item 9). `credential_template` / `smart_resume` catalogs are also
deferred (out of the Phase-1 path).
