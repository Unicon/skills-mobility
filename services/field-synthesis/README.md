# Field Synthesis LLM Decision Service

Generates the human-facing text values for credential fields the Field Mapping service
marked for synthesis (achievement descriptions, alignment rationale, assignment summaries).
See the [design](../../docs/3_design/field-synthesis-llm-decision-service.md) and
[requirements](../../docs/2_requirements/field-synthesis-llm-decision-service.md).

## Pipeline (design §3 / §10)

`resolve briefs → screen source content → one adapter generation → §10 validation → store artifacts → §9 response`

Input is Field Mapping's **synthesis-request artifact** (one brief per placeholder, each
carrying its own source-data snapshot + instruction), supplied inline or by ref. Output is a
flat `{placeholder_id: text}` map, stored as a synthesis-result artifact; the Transformation
Executor merges it under the `synthesized.*` namespace before running the stored JSONata.

The LLM sits behind an adapter boundary (`llm_adapter.LLMAdapter`). Two implementations:

- **replay** (`replay_adapter.ReplayAdapter`, default) — deterministic, no Bedrock/AWS
  (ADR-0013). Fixtures are keyed by `transformation_type`; any requested placeholder the
  fixture doesn't cover gets a deterministic stand-in, so the coverage gate always holds.
- **bedrock** — live Amazon Bedrock (ADR-0010) via the Converse API, forced structured
  output via tool use, at a low non-zero temperature (generative text, not routing).

Validation (`validators.validate_generation`) is a set of **hard Layer-A gates** (ADR-0013):
coverage (a value for every requested `placeholder_id`, no extras) plus presence of
`confidence`/`rationale`. Grounding/faithfulness (FR-FS-6) is a semantic property evaluated at
**Layer B** with a DeepEval G-Eval metric (ADR-0021), not enforced here. Invalid generations
are stored as **failed artifacts**, never as successful results.

## API

```
POST /synthesize-fields   # SynthesisRequest (§4) -> SynthesisResponse (§9 compact envelope)
GET  /healthz
```

Swagger at `http://127.0.0.1:8150/docs` — the `SynthesisRequest` schema carries a
ready-to-send example in the "Try it out" panel. Or from the shell:

```bash
curl -s localhost:8150/synthesize-fields \
  -H 'content-type: application/json' \
  -d '{
        "execution_id": "smoke-1",
        "event_id": "evt-1",
        "transformation_type": "issuer_payload",
        "synthesis_request": {
          "synthesis_request_schema_version": "v1",
          "transformation_type": "issuer_payload",
          "requests": [
            {
              "placeholder_id": "badge_description",
              "target_path": "badge.description",
              "source_payload_paths": ["source_payloads.learner_context.course.description"],
              "source_payloads": {
                "learner_context": {"course": {"description": "Core accounting skills course."}}
              },
              "instruction": "Write a concise badge description."
            }
          ]
        }
      }'
# -> {"status":"succeeded","values":{"badge_description":"..."},"confidence":...}
```

In the normal flow the request instead carries `synthesis_request_ref` — the ref
Field Mapping returned for its stored synthesis-request artifact.

## Run / test

```bash
uv sync --all-packages                       # install workspace members (run once)
uv run field-synthesis                       # serve on :8150 (replay mode); Swagger at http://127.0.0.1:8150/docs
uv run pytest services/field-synthesis       # unit + API tests (no AWS needed)
```

Configuration is env-driven (`FIELD_SYNTHESIS_` prefix); see `.env.example`.
Port via `FIELD_SYNTHESIS_PORT` (default 8150).

## Live Bedrock testing

The service defaults to replay mode. To invoke a real Bedrock model, set
`FIELD_SYNTHESIS_MODE=bedrock` in `.env` (or as a process env var) and
authenticate with AWS.

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

`AWS_PROFILE` is **not** `FIELD_SYNTHESIS_`-prefixed, so pydantic-settings does not
read it from `.env`. Set it as a real process environment variable:

```bash
export AWS_PROFILE=skills
```

Then start (or restart) the service. The service must be restarted after changing
`FIELD_SYNTHESIS_MODE`, `AWS_PROFILE`, or any other `.env` variable —
pydantic-settings caches the config at startup.

### Worked example

Use the curl from the **API** section above — it's a complete inline request, so it
works identically in bedrock mode (the generated `badge_description` will be real
model output grounded in the supplied course description).

### Confirming a live call was made

After a successful request in bedrock mode, the invocation log is written to
`artifact-output/field-synthesis/llmcall/<key>.json` (key = Field Mapping's
`stable_key`, or the `execution_id` for inline requests). Open the file and verify:

- `"provider": "bedrock"` (not `"replay"`)
- `input_tokens` and `output_tokens` are non-null integers
- `latency_ms` is a non-null float

A replay call shows `"provider": "replay"` and `null` for all three fields.
