"""Orchestrator — executes the validated workflow plan. In Phase 1 the plan is a
fixed deterministic sequence (no LLM planning): build context → resolve profile
→ prepare + issue an OBv3 credential → deliver to wallet → record the outcome.
The offloaded LLM Decision Services and Policy Rules are bypassed; the unbuilt
downstream services are reached through injectable client seams.
See docs/2_requirements/phase-1-poc-slice.md and docs/3_design/event-consumer.md.
"""
