"""Event Consumer — the workflow ingress boundary. Validates an incoming event
envelope, enforces event-level idempotency, creates the initial workflow
execution record, and hands the run to the Orchestrator (capture-mode until the
Orchestrator exists). See docs/3_design/event-consumer.md."""
