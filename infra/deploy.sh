#!/usr/bin/env bash
#
# Turnkey deploy of the Skills Mobility demo slice to AWS Lambda (Function URLs).
#
# Prereqs (see infra/iam/README.md):
#   - Foundation stack already deployed (DynamoDB table + ECR repos + UI bucket):
#       aws cloudformation deploy --template-file infra/cloudformation/foundation-demo.yml \
#         --stack-name skills-mobility-dev-foundation --profile <deploy>
#   - The 9 service images pushed to ECR at $IMAGE_TAG.
#   - A Lambda execution role created by Ops (EXEC_ROLE_ARN) and a deploy identity
#     that can iam:PassRole it (AWS_PROFILE — e.g. a profile assuming the deploy role).
#
# Usage:
#   AWS_PROFILE=smi-deploy ./infra/deploy.sh
#   (override EXEC_ROLE_ARN / IMAGE_TAG / REGION as needed)
#
# Idempotent: re-running updates the stacks in place. The wiring is two-pass because
# the chain is circular (mock-lms->event-consumer->orchestrator->context-builder->mock-lms):
# pass 1 creates every function + its Function URL; pass 2 feeds the collected URLs back in.

set -euo pipefail

PROJECT=${PROJECT:-skills-mobility}
ENV=${ENV:-dev}
REGION=${REGION:-us-east-1}
ACCOUNT=${ACCOUNT:-584569945336}
IMAGE_TAG=${IMAGE_TAG:-e0ad733}
EXEC_ROLE_ARN=${EXEC_ROLE_ARN:-arn:aws:iam::${ACCOUNT}:role/${PROJECT}-${ENV}-lambda-exec}
TABLE=${TABLE:-${PROJECT}-${ENV}-execution-state}
REG="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"
TMPL="$(dirname "$0")/cloudformation/lambda-service-demo.yml"

# The full 9-service transformation chain (all packaged + imaged). orchestrator is
# last so pass 2 can wire the URLs its downstream seams expose.
SERVICES=(mock-lms event-consumer context-builder delivery-targets workflow-actions \
  field-mapping field-synthesis transformation-executor \
  delivery-router learncard-issuer-adapter learncard-wallet-adapter orchestrator)

aws() { command aws --region "$REGION" "$@"; }
stack() { echo "${PROJECT}-${ENV}-$1"; }
image() { echo "${REG}/${PROJECT}/$1:${IMAGE_TAG}"; }

deploy_service() {  # $1=service, rest=extra --parameter-overrides
  local svc=$1; shift
  aws cloudformation deploy \
    --template-file "$TMPL" \
    --stack-name "$(stack "$svc")" \
    --no-fail-on-empty-changeset \
    --parameter-overrides \
      ProjectName="$PROJECT" EnvName="$ENV" ServiceName="$svc" \
      ImageUri="$(image "$svc")" ExecutionRoleArn="$EXEC_ROLE_ARN" "$@" >/dev/null
  echo "  deployed $(stack "$svc")"
}

url_of() {  # $1=service -> its Function URL (trailing slash stripped)
  aws cloudformation describe-stacks --stack-name "$(stack "$1")" \
    --query "Stacks[0].Outputs[?OutputKey=='FunctionUrl'].OutputValue" --output text | sed 's:/*$::'
}

# --- Preflight -------------------------------------------------------------
echo "== preflight =="
aws sts get-caller-identity --query Arn --output text
for svc in "${SERVICES[@]}"; do
  aws ecr describe-images --repository-name "${PROJECT}/${svc}" \
    --image-ids imageTag="$IMAGE_TAG" >/dev/null \
    || { echo "MISSING image: $(image "$svc")"; exit 1; }
done
# iam:GetRole is denied under PowerUserAccess; iam:ListRoles is allowed.
EXEC_ROLE_NAME=$(basename "$EXEC_ROLE_ARN")
aws iam list-roles --query "Roles[?RoleName=='${EXEC_ROLE_NAME}'].RoleName" --output text \
  | grep -q "$EXEC_ROLE_NAME" \
  || { echo "exec role not found: $EXEC_ROLE_ARN (Ops must create it — infra/iam/README.md)"; exit 1; }
echo "  images present, exec role present"

# --- Pass 1: create every function + Function URL (no cross-service URLs yet) --
echo "== pass 1: create functions + Function URLs =="
for svc in "${SERVICES[@]}"; do
  case "$svc" in
    # Timeouts: the chain is synchronous — mock-lms waits on event-consumer,
    # which waits on the orchestrator's whole workflow (Bedrock calls + cold
    # starts routinely exceed the 30s Lambda default).
    orchestrator)      deploy_service "$svc" DynamoTable="$TABLE" TimeoutSeconds=120 ;;
    mock-lms|event-consumer) deploy_service "$svc" TimeoutSeconds=150 ;;
    delivery-targets|workflow-actions|field-mapping|field-synthesis) \
                       deploy_service "$svc" LlmMode=bedrock TimeoutSeconds=60 ;;
    # LearnCard delivery leg: adapters call live LearnCloud; the router waits on
    # them. Issuer identity derives from the public seed label; the wallet token
    # comes from the deployer's env (tools/learncard-demo/.env — never committed).
    delivery-router)   deploy_service "$svc" TimeoutSeconds=90 ;;
    learncard-issuer-adapter) deploy_service "$svc" TimeoutSeconds=60 \
      IssuerSecureSeed="${SECURE_SEED:-}" \
      IssuerSeedLabel="${ISSUER_SEED_LABEL:-organization}" \
      IssuerProfileId="${LEARNCARD_ISSUER_PROFILE_ID:-smi-demo-organization}" \
      IssuerProfileName="${LEARNCARD_ISSUER_PROFILE_NAME:-SMI Demo Organization}" ;;
    learncard-wallet-adapter) deploy_service "$svc" TimeoutSeconds=60 \
      LearncardApiUrl="${LEARNCARD_API_URL:-https://network.learncard.com/api}" \
      LearncardApiToken="${LEARNCARD_API_TOKEN:?set LEARNCARD_API_TOKEN (tools/learncard-demo/.env)}" ;;
    *)                 deploy_service "$svc" ;;
  esac
done

# --- Collect Function URLs -------------------------------------------------
echo "== collecting Function URLs =="
MOCK_LMS_URL=$(url_of mock-lms)
EVENT_CONSUMER_URL=$(url_of event-consumer)
ORCHESTRATOR_URL=$(url_of orchestrator)
CONTEXT_BUILDER_URL=$(url_of context-builder)
DELIVERY_TARGETS_URL=$(url_of delivery-targets)
WORKFLOW_ACTIONS_URL=$(url_of workflow-actions)
FIELD_MAPPING_URL=$(url_of field-mapping)
FIELD_SYNTHESIS_URL=$(url_of field-synthesis)
TRANSFORMATION_EXECUTOR_URL=$(url_of transformation-executor)
DELIVERY_ROUTER_URL=$(url_of delivery-router)
LEARNCARD_ISSUER_URL=$(url_of learncard-issuer-adapter)
LEARNCARD_WALLET_URL=$(url_of learncard-wallet-adapter)
printf "  orchestrator: %s\n  mock-lms: %s\n" "$ORCHESTRATOR_URL" "$MOCK_LMS_URL"

# --- Pass 2: wire the chain (feed URLs back into the consumers) ------------
echo "== pass 2: wire the chain =="
deploy_service mock-lms        TimeoutSeconds=150 EventConsumerUrl="$EVENT_CONSUMER_URL"
deploy_service event-consumer  TimeoutSeconds=150 OrchestratorUrl="$ORCHESTRATOR_URL"
deploy_service context-builder LmsBaseUrl="$MOCK_LMS_URL"
deploy_service delivery-router TimeoutSeconds=90 \
  LearncardIssuerUrl="$LEARNCARD_ISSUER_URL" \
  LearncardWalletUrl="$LEARNCARD_WALLET_URL"
deploy_service orchestrator    DynamoTable="$TABLE" TimeoutSeconds=120 \
  OrchestratorIssuerDid="${LEARNCARD_ISSUER_DID:-}" \
  ContextBuilderUrl="$CONTEXT_BUILDER_URL" \
  DeliveryTargetsUrl="$DELIVERY_TARGETS_URL" \
  WorkflowActionsUrl="$WORKFLOW_ACTIONS_URL" \
  FieldMappingUrl="$FIELD_MAPPING_URL" \
  FieldSynthesisUrl="$FIELD_SYNTHESIS_URL" \
  TransformationExecutorUrl="$TRANSFORMATION_EXECUTOR_URL" \
  DeliveryRouterUrl="$DELIVERY_ROUTER_URL"

# --- Smoke test ------------------------------------------------------------
echo "== smoke test =="
curl -sf "${MOCK_LMS_URL}/demo/courses" >/dev/null && echo "  mock-lms /demo/courses OK"
CORR=$(curl -sf -X POST "${MOCK_LMS_URL}/demo/courses/ACCY-111/actions" \
  -H 'content-type: application/json' \
  -d '{"action_id":"ACCY-111-grade-m1","scope":"one"}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['correlation_id'])")
echo "  fired event: $CORR"
for i in $(seq 1 15); do
  STATUS=$(curl -sf "${ORCHESTRATOR_URL}/executions?correlation_id=${CORR}" \
    | python3 -c "import json,sys; r=json.load(sys.stdin); print(r[0]['status'] if r else 'pending')")
  [ "$STATUS" = "completed" ] && { echo "  execution completed ✓"; break; }
  [ "$STATUS" = "failed" ] && { echo "  execution FAILED"; exit 1; }
  sleep 2
done

echo
echo "Done. Admin UI: run infra/deploy-admin-ui.sh with ORCHESTRATOR_URL=${ORCHESTRATOR_URL}"
