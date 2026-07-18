# Decision Service Eval Harness

Deterministic [DeepEval](https://github.com/confident-ai/deepeval)-based
evaluation harness for the two LLM Decision Services (ADR-0013/0021).

## Quick start

```bash
# From the repo root (no workspace changes — runs standalone via uv --with)
uv run --with deepeval --with httpx python evals/run_evals.py

# Flags
uv run --with deepeval --with httpx python evals/run_evals.py --gate-only
uv run --with deepeval --with httpx python evals/run_evals.py --dt-only
uv run --with deepeval --with httpx python evals/run_evals.py \
    --dt-url http://localhost:8130 \
    --wa-url http://localhost:8140
```

Both services must be running (Docker stack up with Bedrock credentials).
The script writes a `evals/last-scorecard.md` after each run and exits
non-zero if any scenario fails.

## Demo — Part 1: one live decision

`run_evals.py` is the *aggregate accuracy* half of the demo. For the
*per-run explainability* half (the view the admin UI, #82, renders), use:

```bash
evals/demo_pipeline.sh                     # ACCY-111 / grade-m1 / WU1125875 (defaults)
evals/demo_pipeline.sh ACCY-111 ACCY-111-grade-final WU1125875
```

It emits one Canvas-style event from the Mock LMS and runs it through the
pipeline (synchronous `/run-workflow` with a fresh `execution_id`, so it's
repeatable despite the event-consumer's re-emit idempotency), printing the live
gate decision + confidence + rationale and the Delivery Targets selection.
The demo learner `WU1125875` is enrolled only in `ACCY-111`. See
[`docs/3_design/evaluating-llm-decisions.md`](../docs/3_design/evaluating-llm-decisions.md).

## Corpora

### `corpus/workflow_actions_gate.json`

Seven hand-labeled scenarios for the Workflow Actions Gate service
(`POST /pre-target-gate`). Each scenario carries:

- `corpus_scenario_id` — stable identifier (never reuse for a different case)
- `event_type` — `skill_mastered`, `course_completed`, or `badge_awarded`
- `event` — raw event body (metadata + body) sent to the service
- `context_bundle` — currently empty `{}` for all POC scenarios
- `expected_decision` — the ground-truth label:
  `continue_to_delivery_targets` or a `terminate_*` string

### `corpus/delivery_targets.json`

Six hand-labeled scenarios for the Delivery Targets service
(`POST /select-delivery-targets`). Each scenario carries:

- `corpus_scenario_id`
- `event_type`, `source_system`, `learner_context`
- `expected_targets` — list of target strings (e.g. `["learncard_issuer", "learncard_wallet"]`)
- `label_status`: `"provisional"` for all current entries

**IMPORTANT: delivery_targets labels are PROVISIONAL.** The
LearnCard-vs-SmartResume routing use case is an open question (spec review #75).
These labels encode the *intended* bifurcation:

- `kind: "digital_credential"` courses → `["learncard_issuer", "learncard_wallet"]`
- `kind: "standard"` courses → `["smart_resume"]`

Do not treat these as a settled contract until #75 is resolved.

## Metric rationale (ADR-0013/0021)

Per ADR-0013 and ADR-0021, LLM Decision Services are scored with
**deterministic metrics against a frozen hand-labeled corpus** — never with
an LLM judge. This keeps evaluation costs near-zero, makes failures
unambiguous, and avoids circular reasoning (using an LLM to grade an LLM).

Two custom `deepeval.metrics.BaseMetric` subclasses:

| Metric | Service | Logic |
|---|---|---|
| `ExactMatchMetric` | Workflow Actions Gate | `actual.strip() == expected` |
| `SetMatchMetric` | Delivery Targets | `set(actual) == set(expected)` |

DeepEval telemetry is disabled (`DEEPEVAL_TELEMETRY_OPT_OUT=YES`).
No Confident AI account or API key is needed or used.
