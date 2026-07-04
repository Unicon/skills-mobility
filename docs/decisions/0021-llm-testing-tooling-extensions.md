# 0021. LLM Testing Tooling Extensions to ADR-0013

- Status: Proposed
- Date: 2026-07-04

## Context

An internal AI-tooling knowledge-share meeting with the LearnVia project team (2026-07-01) surfaced several specific testing and eval tools this project had not evaluated: DeepEval, DSPy, Argilla, AWS Bedrock Guardrails vs. NVIDIA Nemotron Guardrails, prompt injection filtering, and an embeddings-plus-re-ranker hybrid approach to field mapping.

ADR-0013 (Status: Proposed) already established this project's testing framework: a frozen evaluation corpus, per-service scorecards, deterministic validation as the authoritative check for three of the four LLM Decision Services (Workflow Actions, Delivery Targets, Field Mapping), and LLM-as-judge or targeted human review reserved for the fourth (Field Synthesis, the one genuinely open-ended service). ADR-0013 left several open questions, including how a more automated LLM-as-judge component could be added "without creating too circular of outcomes."

Two constraints shape this decision more than any individual tool's maturity:

- **No LLM Decision Service is implemented in code yet.** `docs/3_design/orchestrator.md` describes Phase 1 using deterministic no-op stubs at the Field Mapping and Field Synthesis seams. Any tool that evaluates or optimizes real LLM output has nothing to attach to until that changes.
- **Roughly one month of POC runway remains.** Tooling that requires a mature baseline to be useful (see DSPy below), or whose payoff is offset by a competing cost this month (see Argilla below), is better named as a near-term priority than built immediately.

This ADR extends ADR-0013 rather than replacing it. It also keeps open a live question: whether the three services currently assumed to be deterministic (Workflow Actions, Delivery Targets, Field Mapping) might warrant judgment-based evaluation too. This ADR's DeepEval decision is written to keep that door open without conceding the point either way — see "Why This Approach" below.

## Decision Drivers

- Preserve ADR-0013's separation between deterministic capability checks and judgment-based evaluation, without foreclosing the option to test either method against any of the four services
- Avoid standing up new infrastructure to solve a problem this POC does not yet have (scale, optimization headroom, content moderation at a volume that matters)
- Prefer tools that directly close one of ADR-0013's own open questions over tools that are merely generically useful
- Match the remaining ~1 month runway and the current implementation state (no LLM Decision Service code exists yet)

## Decision

| Tool / practice | Verdict | One-line why |
| --- | --- | --- |
| DeepEval | **Adopt now**, as shared test infrastructure for all four services | Its metric abstraction lets the same test case be scored by a deterministic custom metric or an LLM-judge metric (G-Eval / DAGMetric) without restructuring the harness — directly answers ADR-0013's open question on adding LLM-as-judge without circularity, and keeps the deterministic-vs-judgment question testable rather than settled by tooling limitation |
| Prompt injection filtering | **Adopt now**, minimally, low priority | Cheap: a handful of adversarial fixtures in the frozen corpus plus one deterministic Layer-A check. Real gap ADR-0013 doesn't currently name, but not urgent for a pipeline with no chatbot surface |
| DSPy | **Defer** | Optimizes prompts against a stable eval harness that doesn't exist yet in this project; LearnVia's own more mature project still has it in early prototyping |
| Argilla | **Defer this month; top follow-on priority** | Would reduce a real false-positive risk — a small corpus can make the POC look more viable than it would against realistic data variety — but closing that risk needs matching canonical-answer authorship for at least some services, which competes with reaching a working end-to-end demo |
| Guardrails (AWS Bedrock or NVIDIA Nemotron) | **Neither, low priority** | Solves content moderation, not this project's actual safety mechanism (the deterministic Policy Rules Service, ADR-0007/ADR-0011); Nemotron would also add a second model provider outside ADR-0010's Bedrock-unified adapter |
| Embeddings + re-ranker hybrid for Field Mapping | **Defer implementation; record as a named Phase-2 alternative** | Complements ADR-0005/JSONata (a different layer — candidate-matching method vs. stored output format), doesn't conflict. Building it now would dilute the POC's actual research question: whether the LLM itself can do Field Mapping |

## Why This Approach

### DeepEval as shared infrastructure, not a Field-Synthesis-only tool

DeepEval's core abstraction decouples the test case (input, actual output, source context) from the metric that scores it. A metric can be pure deterministic code, a `DAGMetric` decision tree that mixes deterministic branching with LLM-judged nodes, or full LLM-as-judge (`G-Eval`) on open-ended criteria — all attachable to the same underlying test case. Field Synthesis, ADR-0013's one genuinely open-ended service, uses `G-Eval` from day one; that choice does not depend on and will not change if a deterministic service later gets a judgment-based metric added. That means adopting DeepEval as the harness for all four services does not require deciding right now whether Workflow Actions, Delivery Targets, and Field Mapping are "really" deterministic: ADR-0013's deterministic comparators remain the metric attached to those three services' test cases today; if the team later wants to test a judgment-based metric against the same scenarios instead, that is a metric swap on existing infrastructure, not a new evaluation system.

This directly answers ADR-0013's open question — "how could a more automated LLM-as-a-judge component be added to this without creating too circular of outcomes?" — with ADR-0013's own existing rule: DeepEval's judge output is triage/developer-convenience evidence, never the authoritative verdict for the "Viable / Promising / Not viable" call in ADR-0013 §7. That rule does not change; only the harness that runs it does.

*(Sources: [G-Eval](https://deepeval.com/docs/metrics-llm-evals), [GEval and Custom Metrics](https://deepwiki.com/confident-ai/deepeval/3.2-geval-and-custom-metrics), [How I Built Deterministic LLM Evaluation Metrics for DeepEval](https://www.confident-ai.com/blog/how-i-built-deterministic-llm-evaluation-metrics-for-deepeval).)*

### Why DSPy needs to wait for a baseline that doesn't exist yet

DSPy's GEPA optimization algorithm iterates a prompt against an eval score until improvement stalls — it requires a working, stable eval-score function to optimize against. ADR-0013's harness (now to be built on DeepEval) has to exist and produce trustworthy scores before there's anything for DSPy to climb. LearnVia's own team, more mature on this front, still describes DSPy as early prototyping, blocked on model selection. Betting a month-long POC on it is disproportionate to where this project actually is.

### Why Argilla is deferred, not dismissed

ADR-0013's corpus is small and hand-curated by choice, not settled consensus — a separate effort already improves Mock LMS data realism deterministically, but doesn't generate more scenarios. Because this POC's premise is AI performing jobs that could be done deterministically (ADR-0007), a small corpus risks concluding the LLM Decision Services are viable when they might not hold up against realistic data variety.

Argilla would help close that risk, but not evenly across services: some of the four need a new human-authored canonical answer for every new data pattern it generates, which competes with reaching a working end-to-end demo this month; others are less sensitive to data content and would gain more cheaply. LearnVia's own use of Argilla is limited to side projects, not production.

### Why guardrails are the wrong layer for this project's actual safety mechanism

This project's deterministic safety layer is the Policy Rules Service (ADR-0007, ADR-0011), which validates plans, routing decisions, and mappings against domain rules before any side effect occurs. Content-moderation guardrails (Bedrock or Nemotron) solve an adjacent but different problem: blocking inappropriate or off-topic generated text. The team's own anecdote about Bedrock guardrails — a "block religion" rule flagging the trigonometric term "sine" as "sin" — is direct evidence the keyword-based approach produces false positives severe enough to negate its value for a project with no chatbot-facing surface. Nemotron is more NLP-aware but is a second model/provider integration outside the Bedrock-unified adapter ADR-0010 already chose. Neither is worth the integration cost before the POC has established whether its actual research question (can the LLM Decision Services do their jobs) has a workable answer.

### Why the embeddings/re-ranker hybrid complements, not conflicts with, ADR-0005

ADR-0005 decided the **output representation** for a mapping: JSONata as the stored, reviewable instruction format. The embeddings/re-ranker idea is a candidate **decision method** for the classify/match step that ADR-0008 describes (deciding whether a target field is directly mappable), using deterministic nearest-neighbor vector matching plus a lightweight re-ranker for the top candidates — with the result still expressed as JSONata. Nothing about JSONata-as-output requires the matching decision itself to be LLM-only; these operate at different layers and compose cleanly. The reason to defer is schedule, not conflict: this project's core research question (ADR-0007) is explicitly whether the *LLM* can perform Field Mapping. Substituting a deterministic matching method before that question has an answer would dilute the POC's own evidence, not strengthen it.

## Consequences

### Positive

- DeepEval gives the project one shared test-running and regression-tracking surface for all four services, satisfying both the "these are deterministic" and "we should test judgment-based evaluation too" positions without re-architecture
- Prompt injection coverage closes a real gap in ADR-0013's corpus at negligible cost
- Deferred items are named explicitly with revisit triggers, rather than silently dropped, so they can be picked back up without re-litigating the reasoning

### Negative

- DeepEval integration is still net-new engineering effort layered on top of building the LLM Decision Services themselves, which don't exist in code yet
- Deferring Argilla and the embeddings/re-ranker hybrid means the team gives up early signal on two ideas with real long-term appeal, in favor of runway spent on the core services
- The Chief-Architect-vision question (see Open Questions) is left unresolved by this ADR; it is named, not settled

### Revisit Triggers

This decision should be revisited if:

- DSPy: the DeepEval-based harness is stable and produces trustworthy scores, and baseline prompts prove insufficient
- Argilla: ADR-0013's own review-burden revisit trigger fires (human review load for Field Synthesis or plan adjudication becomes too large), or the team needs a larger/more diverse corpus than hand-curation supports
- Guardrails: a real content-safety incident occurs, or the project gains a genuinely chatbot-like or free-text user-facing surface
- Embeddings/re-ranker hybrid: the pure-LLM Field Mapping baseline reaches a verdict under ADR-0013 and the team wants a head-to-head comparison experiment

## Open Questions

- Does the project's original vision anticipate any of the three currently-deterministic LLM Decision Services needing judgment-based evaluation as a matter of course, rather than as an optional DeepEval metric swap available if evidence calls for it? This ADR treats DeepEval-as-infrastructure as sufficient to keep that question open without resolving it — but the underlying disagreement about whether Workflow Actions, Delivery Targets, and Field Mapping are "really" deterministic is a project-direction question, not a tooling question, and should get an explicit answer.
- Where should DeepEval test suites live relative to the existing `libs/`/`services/` structure, and do they run in CI or only on demand given the cost of LLM-as-judge calls?

## References

- [ADR 0013: LLM Decision Service Testing Approach](0013-llm-decision-service-testing-approach.md)
- [ADR 0007: LLM Decision Service Decomposition](0007-llm-decision-service-decomposition.md)
- [ADR 0005: Schema Mapping Language](0005-schema-mapping-langauge.md)
- [ADR 0008: Transformation Mapping Service Decomposition](0008-transformation-mapping-service-decomposition.md)
- [ADR 0010: LLM Model Access Strategy](0010-llm-model-access-strategy.md)
- [DeepEval: G-Eval](https://deepeval.com/docs/metrics-llm-evals)
- [DeepEval: GEval and Custom Metrics](https://deepwiki.com/confident-ai/deepeval/3.2-geval-and-custom-metrics)
- [How I Built Deterministic LLM Evaluation Metrics for DeepEval](https://www.confident-ai.com/blog/how-i-built-deterministic-llm-evaluation-metrics-for-deepeval)
