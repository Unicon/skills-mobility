# Evaluating the LLM Decisions

How we confirm the four LLM Decision Services (ADR-0007) are *working* — and why "it produced a plausible answer in the demo" is not the same as "the decision is correct." Grounds the approach in [ADR-0013](../decisions/0013-llm-decision-service-testing-approach.md) (testing framework) and [ADR-0021](../decisions/0021-llm-testing-tooling-extensions.md) (DeepEval).

## Two surfaces, two questions

Confirming the decisions work takes **two** complementary views:

| | Question | Surface | Scope |
| --- | --- | --- | --- |
| **Per-run explainability** | *What did the LLM decide for this event, and why?* | Admin UI decision pipeline (#82): each service is a node showing decision + `ConfidenceMeter` + rationale + the ADR-0010 §60 invocation log ("View raw": model, prompt, tokens, latency) | one execution |
| **Aggregate accuracy** | *Across many labelled scenarios, how often is the decision right?* | The DeepEval harness in [`evals/`](../../evals/README.md) → a scorecard | a frozen corpus |

The Admin UI makes a single run legible; the harness makes the pattern measurable. **You need both** — a single legible run tells you the machinery ran, not that the decision was correct.

## The oracle is a labelled corpus — *not* the deterministic stub

The tempting shortcut is "compare the LLM output to the deterministic value." That is right only if "the deterministic value" means a **hand-labelled frozen corpus** (a human-curated expected decision per scenario). It is *wrong* if it means the orchestrator's **deterministic runtime fallback** (the hardcoded plan/targets used when a service is down): comparing LLM → fallback only asks "did the LLM reproduce our hardcoded default?", which is circular and would make the LLM's own reasoning worthless. This is the same "validation must not *grade* the LLM" line from the #75 spec review.

So: **compare to a frozen, hand-labelled corpus; the comparison *method* is deterministic for the classification-like services, but the ground truth is human-authored, never the stub.**

## Method per service (ADR-0013 scorecard)

| Service | Output | How "success" is measured |
| --- | --- | --- |
| **Delivery Targets** | a *set* of target ids | ✅ deterministic **set-correctness** vs the canonical expected set |
| **Workflow Actions – gate** | a decision enum | ✅ deterministic **exact match** vs the canonical terminal outcome |
| **Workflow Actions – plan** | an ordered action DAG | structural conformance (re-bindable/executable, [ADR-0022](../decisions/0022-orchestrator-binding-ownership.md)) + required/forbidden major steps |
| **Field Mapping** | JSONata | Layer-A hard gates (parses, source paths resolve, target-required fields present) + hybrid deterministic-execution / human review |
| **Field Synthesis** | human-facing prose | ❌ not comparable to a string — **G-Eval / LLM-as-judge** for *groundedness*, with the ADR-0013 §7 rule that the judge is **evidence, never the verdict** |

Deterministic comparison is the authoritative check for the first two (and the structural half of the plan and Field Mapping); it is the *wrong* tool for Field Synthesis, which has no single correct string.

## What exists today

A minimal DeepEval harness ([`evals/`](../../evals/README.md)) covers the two clean-comparison services, scoring a hand-labelled corpus against the **live Bedrock** services (uncached, per ADR-0013). A representative live run:

- **Workflow Actions gate — 7/7 (100%)**: all four outcome classes correctly distinguished (continue, sub-competency, failing grade, badge-not-accepted), confidence 0.92–0.99.
- **Delivery Targets — 5/6 (83%, provisional labels)**: routed credential-enabled courses → LearnCard and standard courses → SmartResume as intended; one sparse-context standard course misrouted to LearnCard.

(Live LLM output is non-deterministic, so exact numbers vary run to run — the harness is run uncached on demand, not as a pinned assertion.)

## Findings this surfaces

- **The gate is reliable** on the labelled scenarios — a strong, demoable result.
- **Delivery Targets' accuracy depends on the routing signal being present.** With an explicit credential-enablement signal in `learner_context`, DT discriminates correctly; on real Mock LMS events (which don't yet carry that signal) it routes almost everything to SmartResume. DT's corpus labels are therefore marked **provisional** until that use case is settled.

## Next steps

1. Expand the corpus (breadth is ADR-0021's own noted risk — a small corpus can make the POC look more viable than realistic data variety would).
2. Add the **Field Synthesis** G-Eval groundedness metric (same harness, judge metric attached — DeepEval makes this a metric swap, not new infra).
3. Add the **Workflow Actions plan** structural + step-presence eval (test-harness layer, not a runtime gate — per #75).
4. Resolve **Delivery Targets ground truth** with the routing use case (#75) so its labels stop being provisional.

## Running it

```bash
# stack up with fresh Bedrock creds (see docker/README.md)
uv run --with deepeval --with httpx python evals/run_evals.py            # both services
uv run --with deepeval --with httpx python evals/run_evals.py --gate-only
```
Prints a per-scenario table + aggregate pass rate per service, and writes `evals/last-scorecard.md`.
