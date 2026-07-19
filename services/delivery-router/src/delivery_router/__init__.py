"""Delivery Router — the thin delivery facade between the Orchestrator and the
target-specific adapters (ADR-0016).

It receives one already-approved delivery action, dispatches it to the correct
adapter over HTTP, applies shared delivery mechanics (timeout, config-driven
retry, correlation, standardized logging), and returns a normalized result. It
is NOT a second orchestrator and NOT a transformation layer — no target-specific
field mapping. See docs/3_design/delivery-router-service.md."""
