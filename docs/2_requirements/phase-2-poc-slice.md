# Phase 2 POC Slice Requirements

Status: Draft
Date: 2026-07-20
Related: [Phase 1 POC Slice](./phase-1-poc-slice.md) · [POC Requirements](./poc-requirements.md) · [Target POC Requirements](./target-poc-requirements.md) · [POC Component Boundary Matrix](../3_design/poc-component-boundaries.md) · [Target POC Architecture](../3_design/architecture/target-poc-architecture.md) · [ADR-0007](../decisions/0007-llm-decision-service-decomposition.md) · [ADR-0008](../decisions/0008-transformation-mapping-service-decomposition.md) · [ADR-0009](../decisions/0009-workflow-actions-orchestration-model.md) · [ADR-0010](../decisions/0010-llm-model-access-strategy.md) · [ADR-0011](../decisions/0011-orchestration-runtime-technology.md) · [ADR-0013](../decisions/0013-llm-decision-service-testing-approach.md) · [ADR-0015](../decisions/0015-orchestrator-execution-model.md) · [ADR-0017](../decisions/0017-three-transformation-phases.md) · [ADR-0021](../decisions/0021-llm-testing-tooling-extensions.md)

## 1. Purpose

This document defines the **Phase 2 implementation slice**. Phase 1 ([Phase 1 POC Slice](./phase-1-poc-slice.md)) proved a fast deterministic end-to-end pipeline in which the Orchestrator prepared payloads directly and no AI ran on the happy path. **Phase 2 makes the AI-assisted pipeline actually operational**: the LLM Decision Services and the deterministic Transformation Executor run for real, and the project's core contract — **LLM reasoning is always paired with deterministic validation and complete audit logging** — is enforced end to end.

Phase 2 **supersedes the "out of scope" framing in Phase 1 §4** for the components listed there (the four LLM Decision Services, the Transformation Executor, SmartResume delivery, the Admin UI): those are now in scope. It does **not** supersede Phase 1's component boundaries — the same boundaries hold; Phase 2 fills in the components Phase 1 stubbed or bypassed.

There is deliberately no attempt here to reach the *full* target architecture. The Policy Rules Service, multi-tenancy, and the MCP Client Layer remain out of scope (see §4).

## 2. Primary Happy Paths

Phase 2 keeps the same two supported event types — `skill_mastered` and `course_completed` — but routes each through the full decision pipeline. For a supported event:

1. A demo operator triggers the event from the Mock LMS UI; the Event Producer publishes it and the Event Consumer accepts it (unchanged from Phase 1).
2. The Orchestrator starts a run and the Context Builder assembles source data deterministically (unchanged from Phase 1).
3. **Workflow Actions LLM — pre-target gate:** the Orchestrator asks whether to continue or terminate (`continue` / `terminate`), with confidence and rationale recorded.
4. **Delivery Targets LLM:** on continue, the Orchestrator asks which downstream targets should receive the credential (subset of `learncard_issuer` / `learncard_wallet` / `smart_resume`).
5. **Workflow Actions LLM — delivery-phase plan:** the Orchestrator obtains an ordered plan for the selected targets.
6. The Orchestrator executes the plan. The `credential_template` and `issuer_payload` phases run once to produce the credential to be issued; the final `wallet_payload`-equivalent phase then runs **once per selected delivery target**, keyed by target, each with its own Field Mapping / Field Synthesis pass producing a target-specific payload (this resolves ADR-0017's open question on multi-target topology — see §Delivery pathways). For each transformation phase (ADR-0017: `credential_template` → `issuer_payload` → `wallet_payload`): **Field Mapping LLM** produces a JSONata mapping (and an inline synthesis request for narrative fields); **Field Synthesis LLM** produces those narrative values when synthesis is required; the **Transformation Executor** runs the mapping against the merged source + synthesized context and validates the output against the target schema.
7. `issue_learncard_badge` (LearnCard Issuer Adapter, via the Delivery Router) signs the OBv3 credential — this runs for **every** delivery as a required intermediate step, since LearnCard is the only issuer, regardless of which final target(s) were selected.
8. Delivery to the selected targets via the Delivery Router: `deliver_to_learncard_wallet` and/or `deliver_to_smartresume`.
9. Every LLM invocation records per-invocation metadata (model, prompt, tokens, latency, confidence, rationale) per ADR-0010, stored in the audit trace per ADR-0011 §9 (Audit and Trace Model), so the run is fully inspectable; the Admin UI renders the decision pipeline over that trace.

### Delivery pathways

Three pathways follow from the Delivery Targets decision. In all three, LearnCard Issuer badge issuance (`issue_learncard_badge`) is a **required intermediate step** before final delivery — LearnCard is the only issuer — so it is not specific to any one target:

- **LearnCard Wallet only:** `credential_template` → `issuer_payload` → LearnCard Issuer badge → `wallet_payload` → LearnCard Wallet adapter.
- **SmartResume only:** `credential_template` → `issuer_payload` → LearnCard Issuer badge → `wallet_payload`-equivalent → SmartResume adapter.
- **Both:** the shared prefix runs once (`credential_template` → `issuer_payload` → LearnCard Issuer badge), then the `wallet_payload`-equivalent phase runs **once per selected target**, each producing a target-specific payload delivered to its respective adapter.

**Best-effort seams.** Each decision/transformation seam is best-effort: if the service is unconfigured or fails, the Orchestrator falls back to a deterministic gate/targets/plan/payload so the workflow always completes. LLM output never flows straight to delivery — it is validated (or replaced) deterministically first. A fallback is never silent (see FR-P2-11).

## 3. In Scope

- The **Workflow Actions LLM Decision Service** — pre-target gate + delivery-phase plan (ADR-0009).
- The **Delivery Targets LLM Decision Service**.
- The **Field Mapping LLM Decision Service** — JSONata mapping generation + inline synthesis requests.
- The **Field Synthesis LLM Decision Service** — narrative field values, evaluated with an LLM-as-judge metric.
- The **Transformation Executor** — deterministic JSONata execution + structural output validation against the target schema.
- The **three transformation phases** (ADR-0017): `credential_template`, `issuer_payload`, `wallet_payload`.
- **Multi-target delivery in one execution** — LearnCard issuer + wallet **and** SmartResume (SmartResume Adapter + Mock SmartResume).
- The `badge_awarded` **path preserved but not required end-to-end** (see §4).
- The **deterministic plan executor** (ADR-0011): the Orchestrator runs a validated plan; the LLM-authored plan is re-bound to executor bindings when it is executable, otherwise the deterministic plan runs (LLM output never flows unvalidated to delivery).
- **Per-invocation audit metadata** (ADR-0010, stored in the audit trace per ADR-0011 §9) and the **Admin UI** read model that visualizes the decision pipeline.
- The **evaluation harness** (ADR-0013 / ADR-0021): a frozen labelled corpus scored by deterministic comparators — Delivery Targets set-match; Workflow Actions **both** the pre-target gate decision-match **and** the delivery-phase plan against the canonical expected plan (terminal outcome plus required/forbidden major steps, per ADR-0013's comparator table), across the three delivery pathways — plus LLM-as-judge (Field Synthesis groundedness).
- **AWS delivery on Lambda, provisioned with CloudFormation** (ADR-0015; infra-as-code revised to CloudFormation — see the ADR-0003 revision).

## 4. Out of Scope for Phase 2

- The **Policy Rules Service** as a separate deterministic service. Each Decision Service and the Transformation Executor validate their **own structural output** as a Layer-A gate (schema/registry conformance, binding resolvability); institutional/business-policy validation as a standalone service is deferred.
- **The WA-authored plan always executing.** The Orchestrator re-binds and runs the LLM plan when it is executable, but the current live model frequently omits required steps, so it falls back to the deterministic plan; making the LLM plan reliably executable is follow-on work (tracked separately).
- The **`badge_awarded` event type as a required end-to-end flow** — the sample data to exercise it credibly is not yet in place; the digital-credential courses are hidden from the demo rather than wired through.
- **Multi-tenancy**, self-serve tenant auth (single demo tenant; CloudFront-layer auth per ADR-0002).
- The **MCP Client Layer** (deferred, ADR-0012).
- **Human-in-the-loop review**, rich policy/mapping/target configuration UIs, and production-scale observability.

## 5. Functional Requirements

- **FR-P2-1** For each supported event type, the Orchestrator SHALL invoke the Workflow Actions pre-target gate and terminate the run when the gate returns `terminate`.
- **FR-P2-2** On continue, the Orchestrator SHALL invoke the Delivery Targets service to select the delivery targets, and SHALL deliver only to targets in the returned set.
- **FR-P2-3** The Orchestrator SHALL obtain a delivery-phase plan from the Workflow Actions service and execute it through the deterministic plan executor.
- **FR-P2-4** For each transformation phase, the Orchestrator SHALL obtain a mapping from Field Mapping, resolve any required synthesized values from Field Synthesis, and produce the target payload via the Transformation Executor.
- **FR-P2-5** Every LLM Decision Service SHALL pair its output with deterministic validation of that output (Layer-A gate) and SHALL NOT let an unvalidated output flow to delivery.
- **FR-P2-6** Every LLM invocation SHALL record per-invocation metadata (ADR-0010) to the audit trace (ADR-0011 §9), retrievable for audit and rendered by the Admin UI.
- **FR-P2-7** The pipeline SHALL support delivery to LearnCard (issuer + wallet) and to SmartResume, including both targets in a single execution.
- **FR-P2-8** Each decision/transformation seam SHALL be best-effort: a service failure or absence SHALL fall back to a deterministic result and SHALL NOT fail the workflow.
- **FR-P2-9** The LLM Decision Services SHALL be evaluable against a frozen labelled corpus via the shared DeepEval harness (ADR-0013 / ADR-0021). For Workflow Actions this SHALL score **both** the pre-target gate decision **and** the delivery-phase plan against canonical expected plans (terminal outcome plus required/forbidden major steps, per ADR-0013), across the three delivery pathways — not the gate alone.
- **FR-P2-10** Cross-service artifact handoffs SHALL be inline (each service owns its own artifact store), not by reference into another service's store.
- **FR-P2-11** When any seam falls back to its deterministic result, the fallback SHALL be **distinctly visible** — flagged in the Admin UI, distinctly logged, and recorded in the stored execution trace as a fallback — visibly different from a successful LLM-driven decision, not merely inferable from the absence of LLM metadata.

## 6. Boundary Rules for Phase 2

- **The validation contract is non-negotiable.** Every LLM decision is paired with deterministic validation and complete audit logging; a structurally valid model response is never a success on its own.
- **Best-effort, never fatal.** A seam's failure degrades to the deterministic path; the demo always completes.
- **Deterministic ownership.** Binding correctness and payload execution are the Orchestrator's / Transformation Executor's job; the LLM owns *which* actions/targets/fields, not the executable wiring.
- **Inline handoffs.** Because each service owns its own artifact store, mapping / synthesis request / synthesized values / target schema flow inline through the request chain, not by cross-store reference.
- **Phase 1 boundaries still hold.** Phase 2 replaces the Orchestrator's temporary direct payload preparation (Phase 1 §6) with the real Field Mapping → Field Synthesis → Transformation Executor chain; it does not collapse or bypass the other boundaries.

## 7. Acceptance Criteria

Phase 2 is complete when the team can demonstrate all of the following:

- A `skill_mastered` and a `course_completed` event each run end to end through the full pipeline (gate → targets → plan → per-phase mapping/synthesis/translation → issue → deliver) against **live Bedrock**.
- **Each of the three delivery pathways is demonstrated individually** — LearnCard Wallet only, SmartResume only, and both in one execution — so a solo-target regression cannot slip through the combined case alone. LearnCard Issuer badge issuance is exercised as the required intermediate step in all three.
- Deterministic **fallback is proven** when a seam is unavailable, and the fallback is **distinctly visible** — flagged in the Admin UI, logged, and recorded in the stored trace as a fallback (FR-P2-11), not silent.
- Each LLM decision is visible with its confidence, rationale, and per-invocation metadata (ADR-0010) in the stored audit trace (ADR-0011 §9), via the Admin UI, and no unvalidated LLM output reaches delivery.
- The evaluation harness scores the decision services against the frozen corpus and produces a per-service scorecard — including the Workflow Actions **delivery-phase plan-match** across the three pathways, not the gate decision alone.
- The pipeline is deployable to AWS via the CloudFormation + Lambda infrastructure, or runnable locally via docker-compose with the same topology.
