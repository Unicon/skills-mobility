#!/usr/bin/env bash
# deploy.sh — deploy Skills Mobility CloudFormation stacks.
#
# Usage:
#   infra/deploy.sh                  # deploy all stacks in STACK_ORDER
#   infra/deploy.sh --only foundation
#   infra/deploy.sh --only event-consumer
#   ENV=staging infra/deploy.sh --only orchestrator
#
# Prerequisites:
#   1. aws CLI v2 installed and configured with the SSO_PROFILE in ~/.aws/config.
#   2. TEMPLATE_BUCKET exists and is writable by the SSO_PROFILE role.
#   3. Run 'aws sso login --profile <SSO_PROFILE>' before deploying.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------
usage() {
  grep '^#' "$0" | grep -v '^#!/' | sed 's/^# \?//'
  exit 0
}
[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && usage

# ---------------------------------------------------------------------------
# Load declarative env
# ---------------------------------------------------------------------------
# shellcheck source=skills-mobility.aws
source "${SCRIPT_DIR}/skills-mobility.aws"

# Optional --only <stack-suffix> flag
ONLY_STACK=""
if [[ "${1:-}" == "--only" ]]; then
  ONLY_STACK="${2:?'--only requires a stack name'}"
fi

TEMPLATE_DIR="${SCRIPT_DIR}/cloudformation"
PARAMS_DIR="${SCRIPT_DIR}/params/${ENV}"

# ---------------------------------------------------------------------------
# Sync templates to S3
# ---------------------------------------------------------------------------
echo "==> Uploading templates to s3://${TEMPLATE_BUCKET}/cloudformation/ ..."
aws s3 sync "${TEMPLATE_DIR}/" "s3://${TEMPLATE_BUCKET}/cloudformation/" \
  --profile "${SSO_PROFILE}" \
  --region  "${AWS_REGION}"

# ---------------------------------------------------------------------------
# Deploy stacks
# ---------------------------------------------------------------------------
deploy_stack() {
  local suffix="$1"
  local template_base="${STACKS[$suffix]}"
  local stack_name="${PROJECT}-${ENV}-${suffix}"
  local template_s3="https://${TEMPLATE_BUCKET}.s3.${AWS_REGION}.amazonaws.com/cloudformation/${template_base}.yml"
  local params_file="${PARAMS_DIR}/${suffix}.json"

  echo ""
  echo "==> Stack: ${stack_name}  (template: ${template_base}.yml)"

  local param_args=()
  if [[ -f "${params_file}" ]]; then
    param_args=(--parameter-overrides "file://${params_file}")
  else
    echo "    WARNING: no params file at ${params_file} — deploying with defaults only"
  fi

  aws cloudformation deploy \
    --profile             "${SSO_PROFILE}" \
    --region              "${AWS_REGION}" \
    --template-url        "${template_s3}" \
    --stack-name          "${stack_name}" \
    "${param_args[@]}" \
    --capabilities        CAPABILITY_IAM \
    --no-fail-on-empty-changeset

  echo "    OK: ${stack_name}"
}

if [[ -n "${ONLY_STACK}" ]]; then
  if [[ -z "${STACKS[$ONLY_STACK]+_}" ]]; then
    echo "ERROR: unknown stack '${ONLY_STACK}'. Valid names: ${!STACKS[*]}" >&2
    exit 1
  fi
  deploy_stack "${ONLY_STACK}"
else
  for stack in "${STACK_ORDER[@]}"; do
    deploy_stack "${stack}"
  done
fi

echo ""
echo "==> Done."
