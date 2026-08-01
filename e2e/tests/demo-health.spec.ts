import { expect, test } from "@playwright/test";

/**
 * Demo health check (from Mary's 2026-07-31 AWS test report): fire one event
 * through the Mock LMS console, watch it land in the Admin UI, then audit the
 * execution read model for exactly the things a human reviewer looks for —
 * decision provenance, degraded steps, stubbed seams. Degraded/stubbed results
 * are REPORTED (annotations + stdout) rather than failed by default, because
 * audit-visible degradation is designed behavior; set E2E_STRICT=1 to fail on
 * any of them (e.g. as a release gate).
 */

const MOCK_LMS_URL = process.env.E2E_MOCK_LMS_URL ?? "http://localhost:5173";
const ADMIN_URL = process.env.E2E_ADMIN_URL ?? "http://localhost:5174";
const STRICT = process.env.E2E_STRICT === "1";
const ACTION_LABEL = /grade → emit skill_mastered/i;

// One scenario per delivery branch: ACCY-* routes to the LearnCard wallet,
// FINC-* to SmartResume (delivery-targets pairs each subject accordingly).
// E2E_COURSE narrows the run to a single scenario (any other value runs it
// as a wallet-branch scenario, preserving the old single-course behavior).
const ALL_SCENARIOS = [
  { course: "ACCY-111", expectDelivery: "deliver_to_learncard_wallet" },
  { course: "FINC-106", expectDelivery: "deliver_to_smartresume" },
];
const SCENARIOS = process.env.E2E_COURSE
  ? ALL_SCENARIOS.filter((s) => s.course === process.env.E2E_COURSE).length > 0
    ? ALL_SCENARIOS.filter((s) => s.course === process.env.E2E_COURSE)
    : [{ course: process.env.E2E_COURSE, expectDelivery: "deliver_to_learncard_wallet" }]
  : ALL_SCENARIOS;

type Decision = {
  kind: string;
  confidence: number | null;
  decision_source: string | null;
};
type Step = {
  step_id: number;
  action_id: string;
  status: string;
  output: Record<string, unknown> | null;
};
type Execution = {
  execution_id: string;
  status: string;
  decisions: Decision[];
  steps: Step[];
  result: Record<string, unknown> | null;
  created_at: string;
};

for (const scenario of SCENARIOS) {
test(`fire ${scenario.course} and audit the execution end to end`, async ({ page, request }, testInfo) => {
  // Epoch millis with a 60s allowance for clock skew between this machine and
  // the backend; created_at strings come in both "Z" and "+00:00" ISO forms,
  // so parse — never compare — the strings.
  const startedAtMs = Date.now() - 60_000;
  const auth = process.env.E2E_DEMO_CREDENTIAL
    ? { Authorization: "Basic " + Buffer.from(process.env.E2E_DEMO_CREDENTIAL).toString("base64") }
    : undefined;

  // --- 0. Reset the demo so the fire can't hit ingress dedup (and so this
  // check exercises the reset cascade itself every run) ---
  const reset = await request.post(`${MOCK_LMS_URL}/demo/reset`, { headers: auth });
  expect(reset.ok()).toBe(true);
  const resetBody = (await reset.json()) as Record<string, string>;
  expect(resetBody["event_consumer"], "reset must cascade to the Event Consumer").toBe("reset");
  expect(resetBody["orchestrator"], "reset must reach the Orchestrator terminus").toBe("reset");

  // --- 1. Mock LMS console: pick the course, fire the action, see the cue ---
  await page.goto(MOCK_LMS_URL);
  await page.getByText(scenario.course, { exact: false }).first().click();
  await page.getByRole("button", { name: ACTION_LABEL }).first().click();
  // The fire returns fast now (short forward timeout) and the toast points at
  // the Admin UI — both are part of what this check protects.
  await expect(page.locator(".toast")).toContainText(/Emitted \d+ event/i, { timeout: 30_000 });

  // --- 2. Read model: poll for the new execution to complete ---
  let execution: Execution | undefined;
  await expect
    .poll(
      async () => {
        const resp = await request.get(`${ADMIN_URL}/executions?limit=5`, { headers: auth });
        if (!resp.ok()) return "read-api-unreachable";
        const rows = (await resp.json()) as Execution[];
        const fresh = rows.find((r) => Date.parse(r.created_at) >= startedAtMs);
        if (!fresh) return "pending";
        if (fresh.status === "completed" || fresh.status === "failed") {
          const detail = await request.get(`${ADMIN_URL}/executions/${fresh.execution_id}`, {
            headers: auth,
          });
          execution = (await detail.json()) as Execution;
          return fresh.status;
        }
        return fresh.status;
      },
      { timeout: 180_000, intervals: [5_000] },
    )
    .toBe("completed");
  if (!execution) throw new Error("execution detail never loaded");

  // --- 3. Admin UI renders it ---
  await page.goto(`${ADMIN_URL}/#/executions/${execution.execution_id}`);
  // The workflow chip specifically — every step row renders its own chip.
  await expect(page.locator(".status-chip.completed")).toBeVisible();

  // --- 4. Audit: the things a reviewer checks by hand (Mary's list) ---
  const report: string[] = [];

  // 4a. All three planning decisions present, each with provenance recorded.
  const kinds = execution.decisions.map((d) => d.kind);
  expect(kinds).toEqual(["gate", "delivery_targets", "workflow_actions_plan"]);
  for (const d of execution.decisions) {
    expect(d.decision_source, `${d.kind} must record decision_source`).not.toBeNull();
    if (d.decision_source !== "llm") report.push(`decision ${d.kind}: ${d.decision_source}`);
  }

  // 4b. Every step succeeded; degraded markers surfaced.
  for (const s of execution.steps) {
    expect(s.status, `step ${s.step_id} ${s.action_id}`).toBe("succeeded");
    const degraded = s.output?.["_degraded"];
    if (degraded) report.push(`step ${s.action_id} DEGRADED: ${String(degraded).slice(0, 120)}`);
  }

  // 4c. The issuance bookend exists, and the branch-specific delivery ran.
  const actions = execution.steps.map((s) => s.action_id);
  expect(actions).toContain("resolve_learncard_profile");
  expect(actions).toContain("issue_learncard_badge");
  expect(actions, `the ${scenario.course} branch must deliver via ${scenario.expectDelivery}`)
    .toContain(scenario.expectDelivery);
  // The summary reads whichever delivery step ran (#139 regression guard).
  expect(execution.result?.["delivery"], "result.delivery must be populated").not.toBeNull();
  expect(execution.result?.["delivery"]).toBeDefined();

  // 4d. Stubbed seams stay visible: the stub issuer marks its result.
  if (execution.result?.["issued_ref"] === "stub-issued") {
    report.push("issuance/delivery seam is the STUB (LearnCard delivery layer not deployed)");
  }

  // --- 5. Report or fail ---
  for (const line of report) {
    testInfo.annotations.push({ type: "demo-health", description: line });
    console.log(`[demo-health] ${line}`);
  }
  if (STRICT) {
    expect(report, "E2E_STRICT=1: no degraded steps, fallback decisions, or stubs allowed").toEqual([]);
  }
});
}
