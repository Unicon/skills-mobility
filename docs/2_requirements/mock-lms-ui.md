# Mock LMS — Demo UI Requirements

Status: Draft
Date: 2026-06-12
Related: [Mock LMS overview](./README.md) · [Event Producer](./mock-lms-event-producer.md) · [LMS APIs](./mock-lms-apis.md) · [Design](../3_design/mock-lms.md) · [ADR-0002](../decisions/0002-frontend-architecture.md)

## 1. Purpose

A presenter-facing console (`apps/mock-lms`) that makes the downstream AI orchestration **legible and repeatable** for a stakeholder demo. The operator browses a course as it would appear in a real LMS, triggers an Action, and watches the resulting events stream in real time — then compares the issued badge against the source data.

## 2. Course-centric model

The UI SHALL present a **course**, not an abstract list of trigger buttons — so viewers understand the tool hooks into their LMS.

- **FR-UI1** The operator SHALL pick a **course**, then see its **modules** (and the course's outcomes/skills, assignments, learners, submissions) sourced from the [LMS Resource APIs](./mock-lms-apis.md) — the same endpoints the Context Builder reads.
- **FR-UI2** **Action triggers SHALL be placed in course context:** a *Submit skill mastery* Action at the bottom of the module that corresponds to that skill; *Submit final grade* / *Award badge* Actions at the course level (bottom of the course / last module). The Actions shown depend on the [course kind](./mock-lms-event-producer.md) (standard vs digital-credential-supported).
- **FR-UI3** Each Action SHALL be runnable for **one learner** or **all learners**. For a one-learner Action, the operator can view that learner's submission/outcome data first.

## 3. Inspect · Trigger · Observe

- **FR-UI4 (Inspect):** The UI SHALL let the operator browse the course's source data — modules, outcomes, assignments, learners, submissions, rubrics — via the LMS Resource APIs.
- **FR-UI5 (Trigger):** Triggering an Action SHALL call the emission control API and emit the corresponding event(s).
- **FR-UI6 (Live feed):** The UI SHALL show a live, append-as-it-happens log/timeline of emissions (event type, timestamp, correlation id, target), with the most recent highlighted — suitable to present to an audience.
- **FR-UI7 (Raw payload):** The UI SHALL display the exact emitted envelope (raw JSON) for any emission.
- **FR-UI8 (Copyable ids):** Correlation ids SHALL be copyable so the presenter can pivot to the Admin app and follow the same workflow downstream.
- **FR-UI9 (Replay / reset):** The operator SHALL be able to replay an Action and reset emission state between runs.

## 4. User & auth

- **FR-UI10** A single **demo user** signs in and has full capability (inspect, trigger, watch the live feed, replay). There is **no separate instructor vs administrator role** — for the POC the distinction adds no functionality.
- Auth is **CloudFront-layer** per ADR-0002 (decided — Cognito was considered and not chosen); no secrets in the repo. The design keeps auth behind a single boundary so the issuer could change cheaply if that ever changes.

## 5. Non-functional

- **NFR-UI1 (Lightweight):** React SPA on S3 + CloudFront (ADR-0002).
- **NFR-UI2 (Low-latency):** the live feed SHOULD reflect an emission within ~1s of the trigger.
- **NFR-UI3 (Legible):** every emission is inspectable as raw JSON and tied to a copyable correlation id.

## 6. Out of scope

- Editing courses/Actions or seed data from the UI (authored in-repo only).
- Mutating LMS data on trigger (Actions are triggers, not writes).
- The Admin app's cross-system workflow visualization (separate component).
