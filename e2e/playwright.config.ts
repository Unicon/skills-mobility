import { defineConfig } from "@playwright/test";

// Demo health check — one happy-path flow with audit assertions (AGENTS.md:
// e2e stays happy-path only). Targets are env-driven so the same spec runs
// against local dev servers or the deployed CloudFront consoles:
//
//   local (default):  npm run dev -w apps/mock-lms  +  npm run dev -w apps/admin
//   AWS:              E2E_MOCK_LMS_URL=https://<mock-lms-console> \
//                     E2E_ADMIN_URL=https://<admin-console> \
//                     E2E_DEMO_CREDENTIAL='user:pass' npm run e2e -w e2e
//
// E2E_STRICT=1 fails the run on ANY degraded step or fallback decision
// (default: they're reported as annotations — degradation is audit-visible
// by design, not automatically a failure).
export default defineConfig({
  testDir: "./tests",
  timeout: 240_000,
  expect: { timeout: 15_000 },
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    trace: "retain-on-failure",
    httpCredentials: process.env.E2E_DEMO_CREDENTIAL
      ? {
          username: process.env.E2E_DEMO_CREDENTIAL.split(":")[0],
          password: process.env.E2E_DEMO_CREDENTIAL.split(":").slice(1).join(":"),
        }
      : undefined,
  },
});
