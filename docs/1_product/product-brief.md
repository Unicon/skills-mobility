# Product Brief — Skills Mobility Infrastructure (POC)

Status: Draft
Date: 2026-06-12

## Problem

Learners demonstrate mastery of skills and complete courses inside an LMS, but turning those achievements into portable, verifiable digital credentials (badges, wallet entries) is manual, inconsistent, and hard to trust. Mapping messy source data into a correct, explainable credential is the bottleneck.

## What we're validating

That an **orchestration-centric architecture** can interpret learner/credential events, assemble the right context, use **LLMs** to decide **delivery targets, transformation mappings, and workflow actions** (the three decision services in ADR-0007), gate that reasoning with **deterministic policy validation**, and deliver verifiable credentials downstream (LearnCloud/LearnCard, SmartResume) — with **complete audit logging** so every decision is explainable.

## Audience

- **Stakeholders / prospective adopters** — who need to *see* the system turn real course data into a trustworthy badge, and compare the two side by side.
- **The delivery team** — validating the technical assumptions and risks before broader investment.

## Demo narrative

A presenter opens the **Mock LMS** (a stand-in for a real LMS), shows a course with its modules, skills, and a learner's graded work, and triggers an **Action** (e.g. "submit skill mastery"). The event flows through the orchestration pipeline; moments later the issued **badge** appears in the wallet. The presenter places the source data and the badge side by side — the match demonstrates the AI produced a correct, explainable credential. The demo is **repeatable** (same data every run) and **legible** (every step is inspectable).

## Success criteria

A summary of the fuller list in the PRD ([`poc-requirements.md`](../2_requirements/poc-requirements.md) §Success Criteria):

- Reliable end-to-end orchestration from event to delivered credential.
- Consistent, explainable LLM output, gated by deterministic policy validation.
- Successful downstream delivery and complete audit logging.
- A demo a non-technical stakeholder can follow and trust.

## In / out of scope

See [`../2_requirements/poc-requirements.md`](../2_requirements/poc-requirements.md). Out of scope for the POC: production Open edX eventing, full policy/governance workflows, multi-tenant concerns, human review flows, complex exception handling.
