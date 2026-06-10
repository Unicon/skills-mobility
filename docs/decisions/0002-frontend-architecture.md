# ADR-0002: Frontend Architecture

Status: Accepted  
Date: 2026-06-10

## Context

The original Skills Mobility Infrastructure POC did not explicitly include a frontend. During planning, the team determined that frontend applications would materially improve the ability to demonstrate and operate the system.

Two distinct frontend use cases emerged:

1. Mock LMS frontend
   - Provides a demonstration-oriented LMS experience.
   - Allows an instructor-type user to perform actions such as grading a learner's last assignment.
   - Those actions trigger downstream events, such as a learner mastering a skill or completing a course.
   - The resulting event can then drive the skills mobility workflow, such as issuing a badge or updating a wallet or other downstream destination.
   - Displays the course context, assignments, and submission data so that the viewer of the demonstration can compare these artifacts to the badge generated in the wallet to confirm for themselves the quality of the AI output.

2. Admin frontend
   - Provides an operational and observability interface for the system.
   - Displays workflow execution details, decision logs, and AI-agent reasoning.
   - Should present information on a per-event or per-workflow basis rather than as an undifferentiated global stream.
   - May also host selected system configuration capabilities.

The team also discussed deployment and authentication concerns. For the POC, the frontend should be lightweight to build and operate, and should avoid unnecessary complexity.

## Decision

The project will include two separate React single-page applications. These applications will live in the monorepo under apps/.

The frontends will be implemented as SPAs and deployed as static assets using S3 + CloudFront.

For the POC, frontend authentication will be handled at the CloudFront layer rather than by introducing Cognito.

For the POC, users will log in directly as the role-specific instructor/admin user needed for the application they are accessing. A separate user masquerading capability may be added later if longer-term needs justify it.

## Rationale

### Why include frontend applications

A frontend materially improves the value of the POC by making the system demonstrable and understandable. The Mock LMS app provides a concrete way to trigger workflows from an instructor-facing interface so that the viewer can compare the contextual input and AI generated badging output, while the Admin app provides visibility into AI reasoning and how those workflows were processed.

Without these frontends, the POC would rely more heavily on backend-only demonstrations, logs, or API calls, which would reduce clarity for demos and stakeholder review.

### Why use two separate apps

The team chose to keep the Mock LMS and Admin applications separate because they serve different purposes and may evolve differently.

The Mock LMS frontend is primarily a simulation and demo surface. It will likely be replaced with real LMSs for future demonstrations, though it may continue existing as a useful testing harness.

The Admin frontend is intended to expose system behavior, workflow details, and AI-agent decisioning. It is more operational in nature and likely to remain useful even if the Mock LMS frontend changes significantly.

Keeping the applications separate also avoids forcing unrelated user flows into a single UI and makes it easier to evolve, replace, or retire one application independently of the other.

### Why use React

React was selected as the likely frontend technology because it is well understood, widely supported, and appropriate for building SPA-style applications within a monorepo.

### Why use SPA deployment on S3 + CloudFront

For the POC, static SPA deployment via S3 and CloudFront provides a simple and low-overhead hosting model. It reduces infrastructure complexity while still supporting the required user interfaces.

This deployment model is sufficient for the current expected frontend needs and aligns with the goal of keeping the POC lightweight.

### Why use CloudFront-layer authentication instead of Cognito for the POC

The team discussed authentication options, including Cognito, and chose not to introduce Cognito for the POC.

For the POC, the team prefers a simpler approach that can be implemented safely and with low effort at the CloudFront layer. The goal is to avoid introducing more authentication complexity than is necessary for demonstration purposes.

This keeps the frontend architecture aligned with the lightweight hosting model and avoids taking on user-pool, identity-flow, and authorization design work that is not necessary to validate the POC.

### Why use direct instructor/admin login for now

The team discussed user and account modeling, including whether users should log in and then select a persona to masquerade as, or whether they should log in directly as an instructor or admin user.

The direct-login model was selected for the POC because it is simpler to explain, simpler to implement, and matches the immediate demonstration needs of the two applications.

Masquerading may still become useful later, especially if the system evolves toward a more realistic multi-user operational model. That capability is intentionally deferred until there is evidence that the added complexity is warranted.

## Consequences

### Positive

- The POC gains a concrete, demo-friendly interface for triggering workflows.
- The system gains an operational interface for observing workflow execution and AI-agent reasoning.
- The two applications can evolve independently.
- The Mock LMS application can be treated as replaceable without affecting the Admin application.
- Static SPA hosting keeps frontend deployment simple for the POC.
- CloudFront-layer authentication avoids introducing Cognito complexity during the POC phase.
- Direct instructor/admin login keeps the user model simple and aligned with demo workflows.
- The monorepo can cleanly support both applications under apps/.

### Negative

- Two separate applications introduce additional frontend setup, build, and deployment overhead.
- Shared frontend concerns such as UI components, API clients, and types may require supporting shared packages.
- CloudFront-layer authentication may need to be replaced or expanded if the project requires a more robust long-term identity model.
- Direct instructor/admin login does not provide a more realistic user-delegation or masquerading model out of the box.
- Future consolidation may be needed if the application boundaries prove unnecessary.

## Alternatives Considered

### Single combined frontend application

A single application containing both Mock LMS and Admin functionality was considered.

This was not selected because the two interfaces serve different purposes and have different likely lifecycles. Combining them would risk mixing demo workflows and operational workflows into one application prematurely.

### No frontend

A backend-only POC was implicitly the original plan.

This was not selected because it would make the system harder to demonstrate and would reduce visibility into workflow behavior and AI-agent reasoning.

### More fully featured frontend hosting or framework architecture

More opinionated frontend hosting or framework choices were not selected for the POC because they would introduce additional complexity without a clear near-term benefit.

### Cognito-based authentication for the POC

Using Cognito for frontend authentication was considered.

This was not selected because it would add identity and authorization complexity that is not necessary for the current POC goals. A lighter CloudFront-layer approach is sufficient for the current scope.

### Generic user login with masquerading

A model in which a user logs in and then masquerades as an instructor or admin persona was considered.

This was not selected for the POC because it adds conceptual and implementation complexity without clear immediate value. The team may revisit this later if a longer-term operating model requires it.
