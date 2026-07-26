# Skills Mobility — Infrastructure

CloudFormation + GitHub Actions CI/CD starter for the skills-mobility POC.

**Status: skeleton — not yet deployed against a live AWS account.** See [Not done yet](#not-done-yet--next-steps) below.

---

## Architecture overview

| Concern | Choice | Notes |
|---|---|---|
| IaC | CloudFormation (YAML) | ADR-0003 (revised). No CDK. |
| Compute | AWS Lambda, container images | ADR-0015. Services are already Dockerised. |
| HTTP services | Lambda + Function URL (AuthType NONE) | Orchestrator calls other services over HTTP — same seams as local dev. |
| Event ingress | Lambda triggered by EventBridge rule | event-consumer service. |
| Orchestrator worker | Lambda triggered by SQS EventSourceMapping | See [gap note](#orchestrator-sqs-gap) below. |
| State | DynamoDB (`PAY_PER_REQUEST`) | Replaces local SQLite. ADR-0014. |
| LLM | Bedrock (IAM, no VPC) | Claude Haiku via `us.` cross-region inference profile. ADR-0010. |
| Networking | **No VPC, no subnets, no NAT** | Bedrock + DynamoDB are AWS-API calls over the internet. Deliberate POC simplification. |
| Container registry | ECR, one repo per service | |

### No ECS / Fargate

ADR-0015 explicitly rejected ECS/Fargate for the POC. Lambda scales to zero between events, fits the expected POC volume, and avoids cluster/service/task-definition complexity.

---

## How `skills-mobility.aws` + `deploy.sh` work

`infra/skills-mobility.aws` is a bash env file (sourced, not executed) that declares:

- Core settings: `PROJECT`, `AWS_REGION`, `TEMPLATE_BUCKET`, `SSO_PROFILE`, `ENV`.
- `STACKS` — an associative array mapping stack-name-suffix → template basename.
  - Foundation uses `foundation.yml`; all services share the single parameterised `lambda-service.yml`.
- `STACK_ORDER` — an ordered array controlling deploy sequence. `foundation` is always first because service stacks import its Outputs via `Fn::ImportValue`.

`infra/deploy.sh`:
1. Sources `skills-mobility.aws`.
2. Syncs all templates in `infra/cloudformation/` to S3 (`TEMPLATE_BUCKET`).
3. Iterates `STACK_ORDER` (or just `--only <suffix>`), running `aws cloudformation deploy` for each stack using `infra/params/${ENV}/<suffix>.json` as the parameter file.

Changeset deploys are idempotent — `--no-fail-on-empty-changeset` means a re-run with no template/parameter change is a no-op.

---

## Adding a new service

1. **Lambda handler** — add a Mangum wrapper in the service's FastAPI entrypoint:

   ```python
   from mangum import Mangum
   handler = Mangum(app)
   ```

   Add `mangum` to the service's `pyproject.toml` dependencies.

2. **Dockerfile** — ensure `services/<name>/Dockerfile` produces an image whose `CMD` points at `handler` (the Mangum object). Use AWS's Lambda Python base image:

   ```dockerfile
   FROM public.ecr.aws/lambda/python:3.12
   COPY . ${LAMBDA_TASK_ROOT}
   RUN pip install -r requirements.txt
   CMD ["your_module.handler"]
   ```

3. **ECR repository** — the `deploy.yml` CI workflow creates the repo automatically on first push.

4. **Parameter file** — create `infra/params/dev/<service-name>.json` following the existing examples. Set `EventSourceType` to `url` (HTTP), `eventbridge`, or `sqs` depending on the trigger shape.

5. **Register the stack** — add the service to `STACKS` and `STACK_ORDER` in `infra/skills-mobility.aws`.

6. **Deploy** — `infra/deploy.sh --only <service-name>` (or let the CI push-to-main workflow handle it).

---

## Orchestrator SQS gap

ADR-0015 specifies that the Orchestrator workers (planner + executor) should be SQS-triggered Lambda functions. The current orchestrator implementation is a **synchronous FastAPI service** — it has no SQS consumer loop.

The `orchestrator.json` parameter file currently sets `EventSourceType=url` (Function URL) so the existing FastAPI service deploys without modification. When the orchestrator is refactored to an SQS-driven worker model, change `EventSourceType` to `sqs` and add the Mangum handler entry point.

---

## Not done yet / next steps

Before this skeleton can be deployed against a live AWS account:

1. **AWS account setup** — fill in `REPLACE_WITH_ACCOUNT_ID` in `.github/workflows/deploy.yml` and `TEMPLATE_BUCKET` in `infra/skills-mobility.aws`.

2. **Template bucket** — create the S3 bucket that holds uploaded CFN templates:
   ```bash
   aws s3 mb s3://<YOUR-CFN-TEMPLATE-BUCKET> --region us-east-1 --profile skills
   ```

3. **GitHub OIDC provider** — deploy the foundation stack first (with `CreateOidcProvider=true`). If the account already has a GitHub OIDC provider, set `CreateOidcProvider=false` in `infra/params/dev/foundation.json`.

4. **Mangum handlers** — every FastAPI service needs `mangum` in its dependencies and a `handler = Mangum(app)` line (see [Adding a new service](#adding-a-new-service) above). Without this the Lambda invocation will fail at cold-start.

5. **Lambda-compatible Dockerfiles** — current Dockerfiles target local/Docker Compose use. Each needs to be updated (or a separate `Dockerfile.lambda` added) to use the AWS Lambda base image and expose the `handler` symbol.

6. **Parameter files for remaining services** — `infra/params/dev/` has examples for `event-consumer`, `orchestrator`, and `field-mapping`. Add a `<service>.json` for every other service before deploying it.

7. **Orchestrator SQS refactor** — see [Orchestrator SQS gap](#orchestrator-sqs-gap) above.

8. **Staging / prod environments** — add `infra/params/staging/` and `infra/params/prod/` trees; set `ENV` accordingly in the deploy workflow or CLI invocation.
