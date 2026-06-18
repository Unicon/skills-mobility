# 4 — Operations

**Intent:** Capture *how the system is run* — deployment, environment/config, runbooks, observability, and demo-day operating procedures.

## Contents

_None yet._ Candidate docs as the POC matures:

- `deployment.md` — building and deploying the services and SPAs (S3 + CloudFront per ADR-0002; Lambda/CDK per ADR-0003).
- `demo-runbook.md` — step-by-step for driving a live stakeholder demo (sign in, pick a course, trigger an Action, follow the trace) — see the [Mock LMS design](../3_design/mock-lms.md).
- `observability.md` — logs, traces, and audit output (CloudWatch / X-Ray / audit log), and where execution traces land.

## Workflows

- **Archiving:** set `Status: Superseded` and move retired operations docs to `4_operations/archive/`.
