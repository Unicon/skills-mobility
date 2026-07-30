# Delivery Targets LLM Decision Service

Selects which downstream systems should receive transformed data for a learner/credential event.
See the [design](../../docs/3_design/delivery-targets-llm-decision-service.md) and
[requirements](../../docs/2_requirements/delivery-targets-llm-decision-service.md).

## Pipeline (design §4 / §9)

`load catalog → screen context → one adapter selection → §9 validation → store artifacts → §3 response`

The LLM sits behind an adapter boundary (`llm_adapter.LLMAdapter`). Two implementations:

- **replay** (`replay_adapter.ReplayAdapter`, default) — returns committed canonical
  fixtures keyed by **course subject** (`accy.json` / `finc.json`, with `default.json`
  as the Phase-1 fallback), so tests and local runs need **no Bedrock / AWS access**
  (ADR-0013). The subject comes from the first `course_id` found in `learner_context`
  (nested is fine — the Orchestrator passes the Context Builder bundle).
- **bedrock** — live Amazon Bedrock via the Converse API (ADR-0010): schema-constrained
  structured output via forced tool use, temperature 0. Learner free-text is screened
  for prompt injection first (FR-DT-24). Set `DELIVERY_TARGETS_MODE=bedrock`;
  credentials come from the normal AWS SDK chain.

Validation (`validators.validate_selection`) is a set of **hard Layer-A gates**
(ADR-0013): a structurally valid model response is never a success on its own. Invalid
selections are stored as **failed artifacts** with their errors, never as successful
selections.

## Routing model (design §5)

The LearnCard issuer (`learncard_issuer`) is the **only issuer**, so it is selected
for every event; the course subject decides only the final delivery step:

- **Accounting (`ACCY-*`)** → `learncard_issuer` + `learncard_wallet`
  (Pretend Association of Accountants / LearnCard partnership)
- **Finance (`FINC-*`)** → `learncard_issuer` + `smart_resume`
  (Pretend Association of Finance / SmartResume partnership)

## API

```
POST /select-delivery-targets   # SelectionRequest (§6) -> SelectionResponse (§3 four-key envelope)
GET  /healthz
```

Swagger at `http://127.0.0.1:8130/docs` — the `SelectionRequest` schema carries a
ready-to-send example in the "Try it out" panel. Or from the shell:

```bash
curl -s localhost:8130/select-delivery-targets \
  -H 'content-type: application/json' \
  -d '{
        "execution_id": "smoke-1",
        "event_id": "evt-1",
        "event_type": "skill_mastered",
        "source_system": "mock_lms",
        "learner_context": {
          "learner_id": "learner_42",
          "course_id": "ACCY-111",
          "recipient_profile_id": "smi-demo-learner"
        }
      }'
# -> {"status":"succeeded","selected_targets":[{"delivery_target":"learncard_issuer",
#      "confidence":0.95,"rationale":"..."}, {"delivery_target":"learncard_wallet",...}],...}
# Swap course_id to FINC-106 and the selection becomes issuer + smart_resume.
```

## Catalog

The available-delivery-targets catalog lives at
`src/delivery_targets/catalogs/available_delivery_targets.json` (committed; see design §5).
Resolution is service-internal — the Orchestrator supplies no target ids in the request.
Entries are authored in the institution-admin voice (FR-DT-5a); don't polish them.

## Run / test

```bash
uv sync --all-packages                       # install workspace members (run once)
uv run delivery-targets                      # serve on :8130 (replay mode); Swagger at http://127.0.0.1:8130/docs
uv run pytest services/delivery-targets      # unit + API tests (no AWS needed)
```

Configuration is env-driven (`DELIVERY_TARGETS_` prefix); see `.env.example`.
Port via `DELIVERY_TARGETS_PORT` (default 8130).

## Live Bedrock testing

The service defaults to replay mode. To invoke a real Bedrock model, set
`DELIVERY_TARGETS_MODE=bedrock` in `.env` (or as a process env var) and
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

`AWS_PROFILE` is **not** `DELIVERY_TARGETS_`-prefixed, so pydantic-settings does not
read it from `.env`. Set it as a real process environment variable:

```bash
export AWS_PROFILE=skills
```

Then start (or restart) the service. The service must be restarted after changing
`DELIVERY_TARGETS_MODE`, `AWS_PROFILE`, or any other `.env` variable —
pydantic-settings caches the config at startup.

### Supplying learner_context from the Context Builder

In the real chain the Orchestrator passes the Context Builder bundle as
`learner_context`. To reproduce that by hand, start the Mock LMS (`:8000`) and the
Context Builder (`:8100` with `CONTEXT_BUILDER_LMS_BASE_URL=http://127.0.0.1:8000`),
then:

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
  > /tmp/bundle.json

# 3. Pass the bundle straight through as learner_context (:8130).
curl -s localhost:8130/select-delivery-targets \
  -H 'content-type: application/json' \
  -d "$(jq -n --slurpfile b /tmp/bundle.json '{
        execution_id: "smoke-1",
        event_id: "evt-1",
        event_type: "skill_mastered",
        source_system: "mock_lms",
        learner_context: $b[0]
      }')"
```

### Confirming a live call was made

After a successful request in bedrock mode, the invocation log is written to
`artifact-output/delivery-targets/llmcall/<execution_id>.json`. Open the file and
verify:

- `"provider": "bedrock"` (not `"replay"`)
- `input_tokens` and `output_tokens` are non-null integers
- `latency_ms` is a non-null float

A replay call shows `"provider": "replay"` and `null` for all three fields.
