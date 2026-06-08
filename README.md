# Skills Mobility Infrastructure

Proof of concept for AI-assisted credential orchestration, transformation, and delivery using LLMs and Model Context Protocol (MCP).

## Purpose

This project is intended to validate whether an orchestration-centric architecture can:

- interpret learner and credential events,
- assemble the context needed for decisions,
- use LLMs for routing and transformation reasoning,
- use MCP as a standard interface for tools and data access, and
- deliver transformed credential data to downstream systems.

## Initial POC Scope

The current scope is intentionally narrow and focused on validating technical assumptions. It includes:

- mock learner and credential event generation,
- mock learner and skills data APIs,
- an orchestration workflow engine,
- context aggregation for decision-making,
- an LLM decision service for routing and transformation,
- deterministic policy validation,
- MCP-based access to supporting tools and resources,
- delivery to LearnCloud/LearnCard and SmartResume, and
- audit logging, confidence scoring, and traceability.

## Out of Scope

This POC is not intended to be production-ready. It does not currently target production Open edX eventing, full policy/governance workflows, multi-tenant concerns, human review flows, or complex exception handling.

## Success Criteria

The POC will be considered successful if it demonstrates reliable end-to-end orchestration, consistent and explainable LLM outputs, successful downstream delivery, and complete audit logging of execution decisions and outcomes.
