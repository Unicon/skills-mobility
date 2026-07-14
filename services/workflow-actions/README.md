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
# Replay mode (no AWS required — default)
uv run workflow-actions

# Bedrock mode — requires AWS credentials
WORKFLOW_ACTIONS_MODE=bedrock uv run workflow-actions
```

Service starts on **port 8140**. Docs at `http://localhost:8140/docs`.

## Configuration

Copy `.env.example` to `.env` and set `WORKFLOW_ACTIONS_MODE=bedrock` to use live
Bedrock inference. All other fields have working defaults for local dev.

| Env var | Default | Description |
|---|---|---|
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
