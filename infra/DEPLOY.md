# AWS demo deploy — runbook

Turnkey deploy of the demo slice to Lambda (Function URLs). Once the Ops
prerequisites are in place, the backend is **one command**.

## Status / prerequisites

| | State |
|---|---|
| Foundation stack (DynamoDB `pk` table + 6 ECR repos + UI bucket) | ✅ deployed (`skills-mobility-dev-foundation`) |
| 6 service images in ECR (`mock-lms, event-consumer, context-builder, delivery-targets, workflow-actions, orchestrator`) @ `f8d284d` | ✅ pushed (arm64, single-manifest) |
| **Lambda execution role** `skills-mobility-dev-lambda-exec` | ⛔ Ops (`infra/iam/README.md`) |
| **Deploy role** `skills-mobility-dev-deploy` (PowerUser + `iam:PassRole`) | ⛔ Ops (`OPS-TICKET-aws-demo.md`) |
| Fresh SSO login | `aws sso login --profile skills` (token expires ~8h) |

The two roles are the only blockers. The deployer needs `iam:PassRole` on the exec
role — hence the deploy role — because PowerUserAccess can't pass roles.

## One-time: a profile that assumes the deploy role

```ini
# ~/.aws/config
[profile smi-deploy]
role_arn = arn:aws:iam::584569945336:role/skills-mobility-dev-deploy
source_profile = skills
region = us-east-1
```

## Deploy the backend (one command)

```bash
aws sso login --profile skills          # refresh SSO
AWS_PROFILE=smi-deploy ./infra/deploy.sh
```

`deploy.sh` is idempotent and does the whole thing:
1. **preflight** — verifies identity, that all 6 images exist, and the exec role exists;
2. **pass 1** — creates every Lambda + Function URL (orchestrator gets the DynamoDB
   table; delivery-targets/workflow-actions get `LlmMode=bedrock`);
3. collects the Function URLs;
4. **pass 2** — feeds the URLs back in to wire the (circular) chain
   mock-lms→event-consumer→orchestrator→context-builder→mock-lms;
5. **smoke test** — hits `/demo/courses`, fires an `ACCY-111` event, polls the
   orchestrator until the execution is `completed`.

It prints the orchestrator + mock-lms Function URLs at the end.

> **Scope:** the 6-service decision+audit slice (gate → targets → plan, live Bedrock;
> delivery + transformation stubbed in the orchestrator). To extend to the full
> transformation chain proven locally (`demo/e2e-aligned`), add Lambda packaging +
> images for `field-mapping`, `field-synthesis`, `transformation-executor`, then append
> them to `SERVICES` in `deploy.sh` (+ their `ORCHESTRATOR_*_URL` env in pass 2).

## Admin UI

**Option A — local UI against the AWS backend (recommended for an internal demo).**
Simplest, nothing to host. Point the Vite dev proxy at the orchestrator Function URL:

```bash
# apps/admin/vite.config.ts → set BACKEND to the orchestrator Function URL from deploy.sh
npm run dev -w apps/admin      # http://localhost:5174, reading the AWS orchestrator
```

**Option B — static hosting on CloudFront** (`infra/cloudformation/admin-ui.yml`).
Two origins so the SPA's relative `/executions` calls work unchanged (S3 for the SPA,
the orchestrator Function URL for `/executions*` + `/healthz`):

```bash
ORCH_DOMAIN=<orchestrator-function-url-host>   # e.g. abc123.lambda-url.us-east-1.on.aws
npm run build -w apps/admin
aws s3 sync apps/admin/dist "s3://skills-mobility-dev-admin-ui-584569945336/" --profile smi-deploy
aws cloudformation deploy --template-file infra/cloudformation/admin-ui.yml \
  --stack-name skills-mobility-dev-admin-ui \
  --parameter-overrides UiBucketName=skills-mobility-dev-admin-ui-584569945336 \
                        OrchestratorDomain="$ORCH_DOMAIN" \
  --profile smi-deploy
# then invalidate on re-uploads:
aws cloudfront create-invalidation --distribution-id <id> --paths '/*' --profile smi-deploy
```

> `admin-ui.yml` is written but **not yet AWS-validated** (SSO token expired at authoring
> time) and can't be exercised until the backend is deployed. Validate on next login:
> `aws cloudformation validate-template --template-body file://infra/cloudformation/admin-ui.yml`.

## Teardown

```bash
for s in mock-lms event-consumer context-builder delivery-targets workflow-actions orchestrator admin-ui; do
  aws cloudformation delete-stack --stack-name "skills-mobility-dev-$s" --profile smi-deploy
done
# foundation stack + ECR images left in place for redeploys
```
