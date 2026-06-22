# Context Builder Requirements

Status: Draft
Date: 2026-06-19
Related: [Target POC Requirements](./target-poc-requirements.md) · [POC Component Boundary Matrix](../3_design/poc-component-boundaries.md) · [Design](../3_design/context-builder.md) · [Mock LMS — LMS Resource APIs](./mock-lms-apis.md) · [Mock LMS — Event Producer](./mock-lms-event-producer.md) · [ADR-0012](../decisions/0012-mcp-client-layer-deferred.md)

## 1. Purpose

The **Context Builder** deterministically gathers the source-system data that the Orchestrator and downstream decision steps need.

For the current POC, the Context Builder receives an event from the Orchestrator, determines which fetch profile applies to that event type, calls the required Mock LMS Resource APIs in the required order, and returns a single JSON context bundle containing the collected source data.

## 2. Responsibilities

- **FR-CB1** The Context Builder SHALL accept a request from the Orchestrator that includes the source event envelope and the `execution_id` needed for traceability.
- **FR-CB2** The Context Builder SHALL determine the event type by reading `metadata.event_name` from the event envelope and select a deterministic **fetch profile** or **context recipe** for that event type from the versioned **Source Fetch Rules Store**. The Source Fetch Rules Store mapping SHALL resolve both the internal event type label (e.g. `skill_mastered`) and the underlying platform event name (e.g. `learning_outcome_result_created`) to the correct profile.
- **FR-CB3** The Context Builder SHALL extract the identifiers needed for source fetches from the event envelope.
- **FR-CB4** The Context Builder SHALL support **chained fetches**, where an earlier LMS API response provides identifiers needed for later LMS API calls.
- **FR-CB5** The Context Builder SHALL call only the source APIs allowed by the selected fetch profile. Endpoint selection SHALL remain deterministic and SHALL NOT be delegated to an LLM.
- **FR-CB6** After completing the required source fetches, the Context Builder SHALL package the collected LMS API responses into a single JSON context bundle and return it to the Orchestrator.
- **FR-CB7** The Context Builder SHALL preserve enough metadata in the returned bundle for downstream auditability, including at least the `execution_id`, event type, event id, correlation id, and selected fetch profile identifier or version.

## 3. Event-Type Fetch Requirements

The current target POC event model includes three source event types. The Context Builder SHALL support deterministic fetch profiles for each.

| Event type | Required event identifiers | Required LMS API calls | Notes on id tracing |
| --- | --- | --- | --- |
| `skill_mastered` | `metadata.root_account_id`, `body.result_context_type`, `body.result_context_id`, `body.learning_outcome_id`, `body.associated_asset_type`, `body.associated_asset_id`, `body.user_uuid` | outcome by id; assignment by course and id; rubric by `assignment.rubric_id` if present; course modules; page by id for each Page item in the matched module (`module_pages`); account users by Canvas user UUID; assignment submission by course, assignment, and user | Derive `course_id` from `result_context_id` when `result_context_type` is `Course`. Derive `assignment_id` from `associated_asset_id` when `associated_asset_type` is `Assignment`. The `module_context` is the module object whose `items` array contains an item of type `Assignment` with an `id` matching `assignment_id`. For each item in `module_context.items` with `type: Page`, fetch the page by its id and collect results as `module_pages`. Use `root_account_id` plus `user_uuid` to resolve the Canvas `user_id`, then use that `user_id` to fetch the submission. |
| `course_completed` | `metadata.user_id`, `body.course.id` | course by id; learner profile; enrollment with `current_grade` and `current_points`; course modules; course pages; course assignments; course rubrics; learner submissions for the course | Derive `user_id` from `metadata.user_id` and `course_id` from `body.course.id`. Prefer the course-level student submissions endpoint to fetch the learner's submissions in one call; looping over assignment ids to fetch submissions one by one is an acceptable fallback. |
| `badge_awarded` | `body.badge_id`, `body.user_id` | badge by id; user profile | Fetch badge by `body.badge_id`. Always fetch user profile using `body.user_id` for downstream learner/account matching. |

Endpoint shapes are defined in [Mock LMS — LMS Resource APIs](./mock-lms-apis.md).

For clarity, some logical identifiers are carried in Canvas-style envelope fields rather than in a body field with the same name. For example, `course_id` may come from `metadata.context_id`, `body.result_context_id`, or `body.course.id` depending on the event shape. In the `skill_mastered` profile, `user_id` is present in `metadata.user_id`; the profile additionally resolves it from `metadata.root_account_id` plus `body.user_uuid` to exercise the account-user lookup chain (the resolved id should equal `metadata.user_id`, making it a free consistency check) because the Canvas `user_id` is not carried directly in the event at all and must be resolved from `metadata.root_account_id` plus `body.user_uuid`. In the `course_completed` profile, the Canvas `user_id` can be taken directly from `metadata.user_id`.

When a fetch profile includes conditional assumptions about event field values (for example, that `result_context_type` is `Course` in the `skill_mastered` profile), the Context Builder SHALL skip fetches that depend on the unresolvable identifier rather than guessing a value. If the violated assumption renders all profile fetches unattemptable, the Context Builder SHALL treat this as a missing required identifier and return a failure response (FR-CB11) rather than an empty bundle.

## 4. Determinism and Versioning

- **FR-CB8** Fetch profiles SHALL be versionable and reviewable configuration in the **Source Fetch Rules Store** rather than hidden prompt behavior.
- **FR-CB9** Given the same event, the same fetch profile version, and the same source data, the Context Builder SHALL produce the same context bundle.
- **FR-CB10** The Context Builder SHALL identify which fetch profile version was used for a given bundle so runs can be reproduced and explained later.

## 5. Error Handling and Traceability

- **FR-CB11** If the Context Builder cannot begin executing the fetch profile — because the event type is unrecognized, the fetch profile cannot be loaded, or a required identifier is missing from the event — it SHALL return a machine-readable failure response to the Orchestrator. This failure response is a distinct shape with no `source_data` field; it is not a context bundle.
- **FR-CB12** If one or more LMS API calls fail during profile execution, the Context Builder SHALL still return a context bundle to the Orchestrator. Each failed fetch SHALL be represented as a structured error object under its normal output key (per FR-CB13) in place of the expected source payload. The Orchestrator SHALL always receive a bundle; absence of error objects in `source_data` signals that all fetches succeeded.
- **FR-CB13** When an LMS API call returns an error, the final context bundle SHALL record a structured error object under the logical output key for that API call in place of the expected response data.
- **FR-CB14** The structured error object in the context bundle SHALL preserve the error details that help explain the failed fetch, such as the source API called, the status code when available, and the returned error body or message.
- **FR-CB15** The Context Builder SHALL emit structured logs or trace records for fetch profile selection, each LMS API call attempted, and the final success/failure outcome.

## 6. Non-Goals

The Context Builder does **not** own:

- workflow planning,
- policy validation,
- delivery-target selection,
- transformation mapping generation,
- payload delivery,
- source data mutation,
- or a standalone MCP client layer in the initial POC.

It is a deterministic source-data assembly component, not a decision-making component.
