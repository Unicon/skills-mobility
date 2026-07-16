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

## Run / test

```bash
uv run field-synthesis                       # serve on :8150 (replay mode)
uv run pytest services/field-synthesis       # unit + API tests (no AWS needed)
```

Configuration is env-driven (`FIELD_SYNTHESIS_` prefix); see `.env.example`.
