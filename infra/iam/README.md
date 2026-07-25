# Lambda execution role — for Ops (needs IAM permissions)

The demo deploys with `PowerUserAccess`, which **cannot create IAM roles**. Someone
with IAM rights needs to create **one shared Lambda execution role** for the 6
demo-slice services and hand back its ARN. The per-service CloudFormation stacks
take that ARN as a parameter (`ExecutionRoleArn`) rather than creating roles inline.

One role is intentionally over-scoped for a POC: mock-lms / event-consumer /
context-builder use neither DynamoDB nor Bedrock, but sharing one role keeps the
deploy simple. Tighten later if desired.

**Grants:** CloudWatch Logs (via the managed `AWSLambdaBasicExecutionRole`),
DynamoDB CRUD on the `skills-mobility-dev-execution-state` table (orchestrator
state), and `bedrock:InvokeModel*` on the Claude inference profile
(delivery-targets, workflow-actions).

Account `584569945336`, region `us-east-1`.

## Create it

```bash
aws iam create-role \
  --role-name skills-mobility-dev-lambda-exec \
  --assume-role-policy-document file://trust-policy.json \
  --description "Shared execution role for Skills Mobility demo-slice Lambdas" \
  --profile skills

aws iam attach-role-policy \
  --role-name skills-mobility-dev-lambda-exec \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole \
  --profile skills

aws iam put-role-policy \
  --role-name skills-mobility-dev-lambda-exec \
  --policy-name skills-mobility-dev-lambda-exec-inline \
  --policy-document file://permissions-policy.json \
  --profile skills

# Return this ARN:
aws iam get-role --role-name skills-mobility-dev-lambda-exec \
  --query 'Role.Arn' --output text --profile skills
```

Expected ARN: `arn:aws:iam::584569945336:role/skills-mobility-dev-lambda-exec`
