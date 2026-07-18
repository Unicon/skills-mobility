#!/usr/bin/env bash
#
# Part 1 of the LLM-decision demo (see docs/3_design/evaluating-llm-decisions.md):
# emit one Canvas-style learner event from the Mock LMS and run it through the
# pipeline, printing the live LLM decisions (Workflow Actions gate + Delivery
# Targets) — the same per-run view the admin UI (#82) renders.
#
# Uses the synchronous /run-workflow with a fresh execution_id, so it is
# repeatable: it sidesteps the event-consumer's re-emit idempotency (ADR-0015),
# which otherwise makes a second emit of the same learner+outcome a silent no-op.
#
# Usage:   evals/demo_pipeline.sh [COURSE] [ACTION] [USER_ID]
# Default: ACCY-111 / ACCY-111-grade-m1 / WU1125875   (the demo learner is only
#          enrolled in ACCY-111). Override endpoints with MOCK_LMS_URL / ORCHESTRATOR_URL.
set -euo pipefail

COURSE="${1:-ACCY-111}"
ACTION="${2:-${COURSE}-grade-m1}"
USER_ID="${3:-WU1125875}"
MOCK_LMS="${MOCK_LMS_URL:-http://localhost:8000}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8400}"
EXEC_ID="demo-$(date +%s)-${RANDOM}"
PAYLOAD="$(mktemp)"
trap 'rm -f "$PAYLOAD"' EXIT

echo "▶ STEP 1 — emit ${ACTION} for ${USER_ID} in ${COURSE} (Mock LMS console)"
emit="$(curl -sS -X POST "${MOCK_LMS}/demo/courses/${COURSE}/actions" \
  -H 'Content-Type: application/json' \
  -d "{\"action_id\":\"${ACTION}\",\"scope\":\"one\",\"user_id\":\"${USER_ID}\"}")"

if ! printf '%s' "$emit" | python3 -c "import sys,json; sys.exit(0 if json.load(sys.stdin).get('emitted') else 1)" 2>/dev/null; then
  echo "  emit failed: ${emit}" >&2
  exit 1
fi
printf '%s' "$emit" | python3 -c "
import sys, json
e = json.load(sys.stdin)['emitted'][0]
json.dump({'execution_id': '${EXEC_ID}', 'event': e}, open('${PAYLOAD}', 'w'))
print('   event:', e['metadata']['event_name'], '| course', e['body'].get('result_context_id'))
"

echo "▶ STEP 2 — run through the pipeline (execution ${EXEC_ID}); live LLM decisions:"
curl -sS -X POST "${ORCH}/run-workflow" -H 'Content-Type: application/json' -d @"${PAYLOAD}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
g = d.get('gate_decision') or {}
print('   status:', d['status'])
print('   ● GATE (Workflow Actions):  %s   confidence=%s' % (g.get('decision'), g.get('confidence')))
print('        rationale:', (g.get('rationale') or '')[:160])
deliv = [s['action_id'].replace('deliver_to_', '') for s in d.get('steps', []) if s['action_id'].startswith('deliver')]
print('   ● DELIVERY TARGETS → selected:', deliv, ' (plan_id:', d.get('plan_id'), ')')
steps = d.get('steps', [])
print('   ● PLAN EXECUTED:', len(steps), 'steps →', sorted(set(s['status'] for s in steps)))
"
