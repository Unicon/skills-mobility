# AWS demo deploy — runbook

Turnkey deploy of the demo slice to Lambda (Function URLs). Once the Ops
prerequisites are in place, the backend is **one command**.

## Status / prerequisites

| | State |
|---|---|
| Foundation stack (DynamoDB `pk` table + 9 ECR repos + UI bucket) | ✅ deployed (`skills-mobility-dev-foundation`) |
| 9 service images in ECR (the full chain incl. `field-mapping, field-synthesis, transformation-executor`) @ `ef5320b` (built from `demo/e2e-aligned` — includes all ten review-round fixes) | ✅ pushed (arm64, single-manifest) |
| **Lambda execution role** `skills-mobility-dev-lambda-exec` | ✅ created by Ops (now also codified in `iam-demo.yml`) |
| **Deploy permissions** | ✅ Ops granted the deployer **AdministratorAccess** (2026-07-28) — the planned deploy role is moot for this account; `iam-demo.yml` still carries it as the least-privilege alternative for open-source consumers |
| Fresh SSO login | `aws sso login --profile skills` (token expires ~8h) |
| **Anonymous Function URL invocation** | ✅ solved with Ops (2026-07-28): needs `lambda:InvokeFunction` (`lambda:InvokedViaFunctionUrl: true`) **in addition to** `lambda:InvokeFunctionUrl` — both codified in `lambda-service-demo.yml` |
| **Live end-to-end** | ✅ **VERIFIED 2026-07-28**: full chain on Lambda + live Bedrock — gate/targets/plan decisions from real Claude (incl. a correct sub-competency **terminate**), a **re-bound live LLM plan** executing 11/11, degraded-mode audit markers working. Known rough edges: transient FM 502s under cold-start load (guardrail falls back, recorded), event-consumer's internal client can time out while the workflow completes anyway, and the /tmp dedup DB is per-instance on Lambda |

All IAM for the project is now expressed as code in
`infra/cloudformation/iam-demo.yml` (deploy with `--capabilities CAPABILITY_NAMED_IAM`;
in THIS account the exec role already exists hand-made, so import or delete it first).
Identity Center assignments (the AdministratorAccess grant) live in the org management
account and can't be templated from here — documented in that file's header.

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
AWS_PROFILE=skills ./infra/deploy.sh    # deployer holds AdministratorAccess directly
```

`deploy.sh` is idempotent and does the whole thing:
1. **preflight** — verifies identity, that all 9 images exist, and the exec role exists;
2. **pass 1** — creates every Lambda + Function URL (orchestrator gets the DynamoDB
   table; the four Bedrock services — delivery-targets, workflow-actions,
   field-mapping, field-synthesis — get `LlmMode=bedrock`);
3. collects the Function URLs;
4. **pass 2** — feeds the URLs back in to wire the (circular) chain
   mock-lms→event-consumer→orchestrator→context-builder→mock-lms, plus the
   orchestrator's downstream seams (delivery-targets, workflow-actions,
   field-mapping, field-synthesis, transformation-executor);
5. **smoke test** — hits `/demo/courses`, fires an `ACCY-111` event, polls the
   orchestrator until the execution is `completed`.

It prints the orchestrator + mock-lms Function URLs at the end.

> **Scope:** the full 9-service transformation chain proven locally on
> `demo/e2e-aligned` (gate → targets → plan → mapping → synthesis → execute, live
> Bedrock). LearnCard delivery stays stubbed (profile-resolver / delivery-router
> URLs unset), matching the local e2e proof.

## Admin UI

**Option A — local UI against the AWS backend (recommended for an internal demo).**
Simplest, nothing to host. Point the Vite dev proxy at the orchestrator Function URL:

```bash
# apps/admin/vite.config.ts → set BACKEND to the orchestrator Function URL from deploy.sh
npm run dev -w apps/admin      # http://localhost:5174, reading the AWS orchestrator
```

**Option B — static hosting on CloudFront** (`infra/cloudformation/admin-ui.yml`)
— **DEPLOYED 2026-07-28**: `https://d20uchums0tbiw.cloudfront.net`, gated by a
shared-credential Basic-auth **Lambda@Edge viewer-request** function (ADR-0002's
CloudFront-layer demo auth; Phil's pattern, implemented in Python). The credential
is supplied at deploy time via the NoEcho `DemoAuthCredential` parameter
(`printf '%s' 'user:pass' | base64`) — never committed. Rotation = redeploy with a
new value + a bumped `EdgeAuthVersionV*` logical id. Note the gate protects the
CloudFront entry; the underlying Function URLs remain publicly reachable
(accepted mock-data POC posture).
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

> `admin-ui.yml` passes `aws cloudformation validate-template` but can't be
> exercised end-to-end until the backend is deployed (it needs the orchestrator
> Function URL domain).

## Teardown

```bash
for s in mock-lms event-consumer context-builder delivery-targets workflow-actions \
         field-mapping field-synthesis transformation-executor orchestrator admin-ui; do
  aws cloudformation delete-stack --stack-name "skills-mobility-dev-$s" --profile smi-deploy
done
# foundation stack + ECR images left in place for redeploys
```
