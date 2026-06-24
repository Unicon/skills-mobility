# Context Builder Design

Status: Draft
Date: 2026-06-19
Related: [Requirements](../2_requirements/context-builder.md) · [POC Component Boundary Matrix](./poc-component-boundaries.md) · [Mock LMS — LMS Resource APIs](../2_requirements/mock-lms-apis.md) · [Mock LMS — Event Producer](../2_requirements/mock-lms-event-producer.md) · [ADR-0003](../decisions/0003-programming-language.md) · [ADR-0011](../decisions/0011-orchestration-runtime-technology.md) · [ADR-0012](../decisions/0012-mcp-client-layer-deferred.md)

## 1. Overview

The Context Builder is a thin deterministic enrichment service between the Orchestrator and the source-system APIs.

Its job is:

1. receive an event-centered request from the Orchestrator,
2. choose the correct fetch profile for that event,
3. execute the required LMS API calls in a deterministic order,
4. follow any id-chaining rules needed for later calls,
5. and return a single JSON context bundle containing the collected source responses.

It should not become a second orchestrator and it should not contain LLM-driven endpoint selection.

## 2. Runtime Shape

The minimal runtime flow is:

1. The Orchestrator sends the Context Builder a request containing the event envelope and execution identifiers.
2. The Context Builder reads the event type and selects the matching fetch profile.
3. The Context Builder extracts the initial ids from the event envelope.
4. The Context Builder executes the configured LMS API calls in order.
5. When a later call depends on values returned by an earlier call, the Context Builder extracts those values from the earlier response and uses them in the next request.
6. The Context Builder packages the collected responses and trace metadata into one JSON bundle and returns it to the Orchestrator.

The logical boundary is:

```text
Orchestrator
  -> Context Builder
      -> fetch profile selection
      -> Mock LMS Resource APIs
      -> context bundle assembly
  <- context bundle
```

## 3. Request and Response Shape

Recommended endpoint:

```text
POST /build-context
```

The precise wire format can evolve, but the useful minimal request shape is:

```json
{
  "execution_id": "wf_123",
  "event": {
    "metadata": {
      "event_name": "learning_outcome_result_created",
      "event_id": "evt_123",
      "correlation_id": "corr_123",
      "root_account_id": "account_123"
    },
    "body": {
      "learning_outcome_id": "outcome_123",
      "result_context_type": "Course",
      "result_context_id": "course_123",
      "associated_asset_type": "Assignment",
      "associated_asset_id": "assignment_123",
      "user_uuid": "user_uuid_123"
    }
  }
}
```

The useful minimal response shape is:

```json
{
  "execution_id": "wf_123",
  "event_type": "skill_mastered",
  "fetch_profile_id": "skill_mastered.v1",
  "source_data": {
    "outcome": {},
    "assignment": {},
    "rubric": {},
    "module_context": {},
    "module_pages": [],
    "canvas_user": {},
    "submission": {}
  }
}
```

The key design point is that the Context Builder returns a **single context bundle** containing the named source responses, not a partially transformed delivery payload.

When an LMS API call fails, the same output key holds a structured error object in place of the expected source payload. The bundle is still returned to the Orchestrator with whatever data was successfully fetched. The absence of error objects across all keys in `source_data` signals that the bundle is complete; there is no separate top-level status field. For example, a bundle with a failed submission fetch:

```json
{
  "execution_id": "wf_123",
  "event_type": "skill_mastered",
  "fetch_profile_id": "skill_mastered.v1",
  "source_data": {
    "outcome": {},
    "submission": {
      "error": {
        "source_api": "GET /api/v1/courses/course_123/assignments/assignment_123/submissions/user_123?include[]=rubric_assessment",
        "status_code": 404,
        "message": "submission not found"
      }
    },
    "canvas_user": {}
  }
}
```

When the Context Builder itself cannot execute the fetch profile — for example because the event type is unrecognized or a required identifier is missing — it returns a distinct failure response with no `source_data`:

```json
{
  "execution_id": "wf_123",
  "context_builder_error": {
    "code": "missing_required_identifier",
    "message": "result_context_type 'Enrollment' is not 'Course'; cannot derive course_id"
  }
}
```

## 4. Internal Modules

The initial implementation can stay small. The useful logical modules are:

- **Request handler**: accepts the Orchestrator request and returns the final bundle or failure.
- **Event classifier / id extractor**: determines the event type and pulls the initial ids from the event envelope.
- **Fetch profile registry**: loads the deterministic recipe for the event type and, later, optional workflow-step variants from the repo-backed **Source Fetch Rules Store**.
- **LMS API client**: performs the actual HTTP calls to the Mock LMS Resource APIs.
- **Response collector / bundle builder**: stores each fetched response under a stable logical key and emits the final JSON blob.
- **Fetch error recorder**: converts LMS API failures into structured error objects stored under the same logical output keys the success payloads would have used.
- **Trace logger**: records which profile ran, which calls were attempted, and the final outcome.

These do not need to be separate deployable services.

## 5. Fetch Profiles / Context Recipes

The core design abstraction is a versioned set of **fetch profiles** keyed by event type and, where needed later, by workflow step.

In the initial POC, those profiles should live as repo-backed configuration entries in the **Source Fetch Rules Store** described by the boundary matrix.

Each profile should define:

- the event type it applies to,
- the ordered list of LMS API calls,
- which request parameters come from event ids,
- which request parameters come from prior API responses,
- the output key under which each response is stored in the final bundle,
- and any conditional assumptions about event field values, with the skip-or-fail behavior when those assumptions are violated.

### Profile schema

Profiles are YAML files bundled inside the service package at `services/context-builder/src/context_builder/fetch_profiles/`, one file per event type (e.g. `skill_mastered.yaml`), and loaded read-only at startup. (They live in the package — rather than a repo-root `config/` dir — so the profiles deploy as part of the service artifact with no extra packaging or path configuration; for a single-service POC that's simpler than an external config directory.) The `version` field is an integer starting at 1; increment it whenever the profile changes. Git history preserves prior versions. The bundle records `fetch_profile_id` as `{event_type}.v{version}`.

Top-level fields:

| Field | Description |
|---|---|
| `id` | `{event_type}.v{version}` — the identifier recorded in the bundle |
| `event_type` | Internal event type label this profile matches (e.g. `skill_mastered`) |
| `version` | Integer starting at 1; increment on every change |
| `steps` | Ordered list of fetch steps, executed in sequence |

Each step:

| Field | Required | Description |
|---|---|---|
| `output_key` | yes | Key under `source_data` where the API response or error is stored |
| `endpoint` | yes | URL template with `{param}` placeholders |
| `params` | yes | Map from placeholder name to its source |
| `condition` | no | If present, skip this step unless the condition holds |
| `select` | no | After fetching an array response, store one matching object rather than the full array |
| `for_each` | no | Execute once per matching item from a prior step's response; collect results as an array under `output_key` |

Param `source` forms:

```yaml
# From the event envelope
name: { source: event, path: body.learning_outcome_id }

# From a prior step's stored response
name: { source: response, step: assignment, path: rubric_id }

# From the current for_each item (only valid inside a for_each step)
name: { source: foreach_item, path: id }
```

A `condition` evaluates a field on a prior step's response:

```yaml
condition: { source: response, step: assignment, path: rubric_id, operator: present }
# operator values: present | absent
```

A `select` picks one object from a fetched array by match criteria (example from `skill_mastered`):

```yaml
select:
  where:
    contains_item:          # choose the array element whose nested items match all criteria
      in: items
      type: Assignment
      content_id: { source: event, path: body.associated_asset_id }   # Canvas module items reference the assignment by content_id, not id
```

A `for_each` iterates over items from a prior step's response, with optional filtering:

```yaml
for_each:
  source: response
  step: module_context      # output_key of the prior step
  path: items               # dot-path to the list within that response
  where: { type: Page }     # optional: keep only items matching this filter
```

`where` values may be static (as above) or source specs (`{ source: event|response, path: ... }`), resolved the same way as `select`'s `contains_item` criteria.

### `skill_mastered`

The initial recipe should gather the learning-outcome and assignment context tied to the Canvas `learning_outcome_result_created` event.

The recipe assumes:

- `result_context_type` is `Course`, so `result_context_id` is treated as `course_id`,
- and `associated_asset_type` is `Assignment`, so `associated_asset_id` is treated as `assignment_id`.

The fetch chain should be:

1. fetch outcome by `learning_outcome_id`,
2. fetch assignment by `course_id` plus `assignment_id`,
3. if `assignment.rubric_id` is present, fetch the rubric by `course_id` plus `rubric_id`; if the assignment embeds the rubric schema directly, skip this step — the rubric data is already in `assignment`,
4. fetch course modules; from the response array select the module object whose `items` contains an entry with `type: Assignment` and `id` matching `assignment_id`; store that module object as `module_context`,
5. for each item in `module_context.items` where `type` is `Page`, fetch the page by `course_id` and the item's `id`; collect results as `module_pages`; fetching the full course pages list and filtering by id is an acceptable fallback,
6. fetch the Canvas user record by `root_account_id` plus `user_uuid` to obtain the Canvas `user_id`,
7. fetch the user's assignment submission by `course_id`, `assignment_id`, and the resolved Canvas `user_id` (with `include[]=rubric_assessment`).

This is an intentionally chained profile:

- the event gives the Context Builder the outcome id, course context, assignment context, and Canvas user UUID,
- the assignment response determines whether a separate rubric fetch is needed (by presence or absence of `rubric_id`),
- the modules response identifies the relevant module object and its Page items,
- and the account-user lookup gives the Context Builder the Canvas `user_id` needed for the final submission fetch.

**Rubric consistency note:** The Mock LMS must implement rubric data in exactly one way — either always embedding the full rubric schema on the assignment object (no `rubric_id` field, step 3 always skipped) or always returning only a `rubric_id` on the assignment (step 3 always executes when a rubric is associated). The fetch profile step 3 must match whichever behavior the Mock LMS implements.

### `course_completed`

The initial recipe should gather course-completion context:

The recipe assumes:

- `user_id` comes from `metadata.user_id`,
- and `course_id` comes from `body.course.id`.

The fetch chain should be:

1. fetch course by `course_id`,
2. fetch learner profile by `user_id`,
3. fetch learner enrollment using `course_id` and `user_id`, including grade and points,
4. fetch course modules,
5. fetch course pages,
6. fetch course assignments,
7. fetch course rubrics,
8. fetch the learner's submissions for the course

If the course-level student-submissions endpoint turns out to be inconvenient for a particular mock or implementation slice, an acceptable fallback is:

- loop over the assignment ids returned by the assignments call,
- and fetch each assignment submission individually by `course_id`, `assignment_id`, and `user_id`.

The preferred default is the course-level submissions call because it keeps the recipe shorter and avoids one submission request per assignment.

### `badge_awarded`

The initial recipe should stay small:

1. fetch badge by `body.badge_id`,
2. fetch user profile by `body.user_id`.

## 6. Bundle Assembly

The Context Builder should keep the returned JSON bundle close to the source-system responses.

That bundle should usually include:

- request trace metadata such as `execution_id`, `event_type`, `event_id`, `correlation_id`, and `fetch_profile_id`,
- the raw source event envelope or a stable reference to it,
- the fetched LMS API responses grouped under stable logical keys,
- structured error objects in place of response payloads for any LMS API calls that failed,
- and optional fetch diagnostics such as timestamps or request URIs when they help with debugging.

A bundle with no `error` sub-objects in any `source_data` key indicates a fully successful run. There is no separate top-level status or result field; the Orchestrator determines completeness by scanning `source_data` keys for error objects.

The Context Builder should avoid doing higher-level reasoning or schema transformation here. Its job is to assemble source context, not to interpret it for delivery.

## 7. Local vs AWS

The boundary behavior should stay the same in both environments, but the surrounding adapters will differ.

### Local development

For local development:

- the Context Builder can run either as a small local service with its own endpoint or as an in-process module loaded by a local Orchestrator runtime,
- the local Orchestrator can call the Context Builder over `localhost` HTTP or a direct Python boundary, depending on what is simplest for the slice being built,
- the LMS API client can call the local Mock LMS service over `localhost`,
- fetch profiles remain repo-backed configuration loaded directly from the repo,
- failed LMS API calls should still be reflected in the returned local bundle as structured error objects under the affected output keys,
- and developers should be able to inspect the returned context bundle directly in logs, saved JSON, or a local test harness.

The useful local goal is fast inspectability rather than infrastructure fidelity. A developer should be able to run the Mock LMS, trigger or capture an event, invoke the Context Builder locally, and immediately inspect the exact bundle returned to the Orchestrator.

### AWS-shaped target

For the AWS-shaped target:

- the Context Builder should be deployed as its own **Lambda function**,
- the Orchestrator should also be a separate **Lambda function**,
- the Orchestrator Lambda should invoke the Context Builder Lambda synchronously and wait for the returned context bundle,
- the Context Builder Lambda should execute the selected fetch profile during that invocation and return the completed bundle directly to the Orchestrator Lambda,
- the LMS API client in the Context Builder Lambda should call the deployed LMS Resource APIs,
- the same repo-defined fetch profiles should apply without changing the logical fetch rules,
- failed LMS API calls should still be represented in the returned bundle as structured error objects under the affected output keys,
- and logs and trace records from both Lambdas should be correlated by execution id, event id, and correlation id.

This keeps the boundary explicit: the Orchestrator owns workflow progression, while the Context Builder Lambda is a synchronous source-data assembly step called by that workflow.

## 8. How To Test It

### Unit and integration tests

The main automated test targets should be:

- fetch profile selection by event type,
- id extraction from the event envelope,
- chained parameter resolution from prior responses,
- correct LMS API call ordering per profile,
- and final bundle assembly.

Integration tests should run against stubbed or local Mock LMS API responses so the expected bundle for each supported event type is deterministic.

### Local manual test

Before a full Orchestrator flow exists, a developer should be able to:

1. run the Mock LMS locally,
2. trigger an event from the Mock LMS UI or capture an emitted event envelope,
3. submit that event envelope to the Context Builder through a small local harness or endpoint,
4. inspect the returned context bundle,
5. and confirm that the expected sections for that event type are present and populated.

The proof of success is not only that the API calls were made, but that the Context Builder returned one coherent JSON blob containing the expected source responses.

If a source API is intentionally made to fail, the expected proof changes slightly: the returned bundle should still include the failed fetch under its normal logical key, but that key should contain the structured error details rather than a source payload.

### AWS verification

In the AWS-shaped deployment, verification should include:

1. confirm the Orchestrator Lambda invoked the Context Builder Lambda for the relevant workflow step,
2. confirm the Context Builder Lambda selected the expected fetch profile,
3. confirm the Context Builder Lambda called the expected LMS APIs,
4. confirm the returned bundle reached the Orchestrator Lambda,
5. and, when a source API fails, confirm the returned bundle contains the structured error object under the affected key.

## 9. Boundary Rules

- Do not let an LLM choose which LMS endpoints to call.
- Do not mutate LMS source data here.
- Do not generate workflow plans here.
- Do not enforce business policy here.
- Do not reshape the context bundle into a delivery payload here.
- Do keep fetch rules explicit, deterministic, and versionable.
