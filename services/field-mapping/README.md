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
- **bedrock** — live Amazon Bedrock via the Converse API (ADR-0010): a thin provider
  adapter, schema-constrained structured output via forced tool use, temperature 0.
  Source payloads are screened for prompt injection first (FR-FM-27b). Set
  `FIELD_MAPPING_MODE=bedrock`; credentials come from the normal AWS SDK chain.

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

## Live Bedrock testing

The service defaults to replay mode. To invoke a real Bedrock model, set `FIELD_MAPPING_MODE=bedrock` in `.env` (or as a process env var) and authenticate with AWS.

### One-time AWS SSO setup

```bash
aws configure sso
# SSO start URL: https://<your-org>.awsapps.com/start
# SSO region:    us-east-1  (or the region your SSO portal runs in)
# Scopes:        sso:account:access
# Default output: json
```

Follow the prompts to name the profile (e.g. `skills`).

### Re-authenticate when your session expires

```bash
aws sso login --profile skills
```

### Set the profile before launching the service

`AWS_PROFILE` is **not** `FIELD_MAPPING_`-prefixed, so pydantic-settings does not
read it from `.env`. Set it as a real process environment variable:

```bash
export AWS_PROFILE=skills
```

Then start (or restart) the service. The service must be restarted after changing
`FIELD_MAPPING_MODE`, `AWS_PROFILE`, or any other `.env` variable — pydantic-settings
caches the config at startup.

### Supplying source_payloads from the Context Builder

The Context Builder (port 8100) produces the `source_payloads` object the Field
Mapping service expects. It fetches from the Mock LMS, so start both (Mock LMS on
`:8000`, Context Builder on `:8100` with `CONTEXT_BUILDER_LMS_BASE_URL=http://127.0.0.1:8000`),
then run the three-step recipe:

```bash
# 1. Emit an event from the Mock LMS. scope=one limits it to a single learner.
curl -s localhost:8000/demo/courses/ACCY-111/actions \
  -H 'content-type: application/json' \
  -d '{"action_id": "ACCY-111-grade-m1", "scope": "one"}' \
  | jq '.emitted[0]' > /tmp/envelope.json

# 2. Build context from that envelope (execution_id is any correlation string).
curl -s localhost:8100/build-context \
  -H 'content-type: application/json' \
  -d "$(jq -n --slurpfile e /tmp/envelope.json '{execution_id: "smoke-1", event: $e[0]}')" \
  | jq '.source_data' > /tmp/source_payloads.json

# 3. Pass source_data straight through as source_payloads to /map (:8120).
curl -s localhost:8120/map \
  -H 'content-type: application/json' \
  -d "$(jq -n --slurpfile s /tmp/source_payloads.json '{
        execution_id: "smoke-1",
        event_id: "evt-1",
        transformation_type: "issuer_payload",
        source_system: "mock_lms",
        fetch_profile_id: "skill_mastered.v1",
        delivery_target: "learncard_issuer",
        synthesis_allowed: false,
        source_payloads: $s[0]
      }')"
```

`profile_resolution` can be skipped for a basic smoke test — the Context Builder
doesn't produce it, and omitting it just shows up as lower confidence on the
DID-dependent fields, which is expected. Alternatively, the orchestrator's
execution trace stores the `source_payloads` it passes to Field Mapping in each
step's output — check `artifact-output/orchestrator/` for captured runs.

### Confirming a live call was made

After a successful `/map` request in bedrock mode, the invocation log is written
to `artifact-output/field-mapping/llmcall/<key>/<NNNN>.json`. Open the file and
verify:

- `"provider": "bedrock"` (not `"replay"`)
- `input_tokens` and `output_tokens` are non-null integers
- `latency_ms` is a non-null float

A replay call shows `"provider": "replay"` and `null` for all three fields.

## Build-order status (design §16)

Done: contracts, artifacts + store, catalogs, catalog/payload loading, validation,
replay adapter + service + API (items 1–6), and the Bedrock provider adapter +
prompts + injection screen (item 7). **Deferred:** orchestrator wiring (item 8,
PR #33) and live evaluation + DeepEval Layer B (item 9). `credential_template` /
`smart_resume` catalogs are also deferred (out of the Phase-1 path).
