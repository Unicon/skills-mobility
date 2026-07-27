# Workflow Actions LLM Decision Service

The top-level planner of the orchestration architecture (ADR-0009). Two stages,
one deployable service:

| Stage | Endpoint | Question |
|---|---|---|
| Pre-target gate | `POST /pre-target-gate` | Terminate early, or continue to delivery-target selection? |
| Delivery-phase plan | `POST /delivery-phase-plan` | What ordered steps reach the selected targets? |

Design: `docs/3_design/workflow-actions-llm-decision-service.md`

## Running locally

```bash
uv sync --all-packages                  # install workspace members (run once)

# Replay mode (no AWS required — default)
uv run workflow-actions

# Bedrock mode — requires AWS credentials (see "Live Bedrock testing" below)
WORKFLOW_ACTIONS_MODE=bedrock uv run workflow-actions
```

Service starts on **port 8140** (override: `WORKFLOW_ACTIONS_PORT`). Docs at
`http://localhost:8140/docs` — both request schemas carry ready-to-send examples
in Swagger's "Try it out" panel. Or from the shell:

```bash
# Stage 1 — pre-target gate
curl -s localhost:8140/pre-target-gate \
  -H 'content-type: application/json' \
  -d '{
        "execution_id": "smoke-1", "event_id": "evt-1", "event_type": "skill_mastered",
        "event": {"metadata": {"event_name": "learning_outcome_result_created"},
                  "body": {"learning_outcome_id": "ACCY-111-OUT-1", "title": "1.0.0 Mastery"}},
        "context_bundle": {"source_data": {"outcome": {"display_name": "1.0.0 Core accounting competency"}}}
      }'
# -> {"status":"succeeded","decision":"continue","confidence":...,"rationale":"..."}

# Stage 2 — delivery-phase plan (an ordered plan for the selected targets)
curl -s localhost:8140/delivery-phase-plan \
  -H 'content-type: application/json' \
  -d '{
        "execution_id": "smoke-1", "event_id": "evt-1", "event_type": "skill_mastered",
        "source_system": "mock_lms",
        "event": {"metadata": {"event_name": "learning_outcome_result_created"}},
        "context_bundle": {"source_data": {}},
        "selected_targets": ["learncard_issuer", "smart_resume"]
      }'
# -> an 11-step plan: credential-template phase, issuer phase, issuance, then the
#    SmartResume branch (swap selected_targets to see the wallet / dual variants).
```

## Configuration

Copy `.env.example` to `.env` and set `WORKFLOW_ACTIONS_MODE=bedrock` to use live
Bedrock inference. All other fields have working defaults for local dev.

| Env var | Default | Description |
|---|---|---|
| `WORKFLOW_ACTIONS_PORT` | `8140` | Local HTTP port |
| `WORKFLOW_ACTIONS_MODE` | `replay` | `replay` or `bedrock` |
| `WORKFLOW_ACTIONS_MODEL_ID` | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Bedrock inference-profile model id |
| `WORKFLOW_ACTIONS_AWS_REGION` | `us-east-1` | AWS region |
| `WORKFLOW_ACTIONS_MAX_TOKENS` | `2048` | Max tokens for generation |
| `WORKFLOW_ACTIONS_ARTIFACT_DIR` | `artifact-output/workflow-actions` | Where plan + log artifacts are stored |
| `WORKFLOW_ACTIONS_LOG_LEVEL` | `INFO` | Log level |

## Tests

```bash
uv run pytest services/workflow-actions
```

## Live Bedrock testing

The service defaults to replay mode. To invoke a real Bedrock model, set
`WORKFLOW_ACTIONS_MODE=bedrock` in `.env` (or as a process env var) and
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

`AWS_PROFILE` is **not** `WORKFLOW_ACTIONS_`-prefixed, so pydantic-settings does
not read it from `.env`. Set it as a real process environment variable:

```bash
export AWS_PROFILE=skills
```

Then start (or restart) the service. The service must be restarted after changing
`WORKFLOW_ACTIONS_MODE`, `AWS_PROFILE`, or any other `.env` variable —
pydantic-settings caches the config at startup.

### Worked example

Use either curl from **Running locally** above — both are complete inline
requests, so they work identically in bedrock mode (the gate decision and the
plan ordering become real model output).

### Confirming a live call was made

After a successful request in bedrock mode, the invocation log is written to
`artifact-output/workflow-actions/llmcall/gate-<execution_id>.json` (stage 1) or
`llmcall/plan-<execution_id>.json` (stage 2). Open the file and verify:

- `"provider": "bedrock"` (not `"replay"`)
- `input_tokens` and `output_tokens` are non-null integers
- `latency_ms` is a non-null float

A replay call shows `"provider": "replay"` and `null` for all three fields.
