# e2e — demo health check

One happy-path Playwright flow (per AGENTS.md's testing strategy) that does what a
human reviewer does after a deploy: fire an event in the Mock LMS console, watch it
complete in the Admin UI, then audit the execution read model — decision provenance
(`decision_source`), degraded step markers (`_degraded`), the issuance/delivery
bookends, and stub visibility.

Degraded/stubbed findings are **reported** (annotations + stdout), not failed —
audit-visible degradation is designed behavior. `E2E_STRICT=1` turns any finding
into a failure (release-gate mode).

```bash
npm install                       # once, repo root
npx playwright install chromium   # once

# Local (mock-lms console on :5173, admin on :5174, backends running):
npm run e2e -w e2e

# Deployed demo:
E2E_MOCK_LMS_URL=https://<mock-lms-console>.cloudfront.net \
E2E_ADMIN_URL=https://<admin-console>.cloudfront.net \
E2E_DEMO_CREDENTIAL='user:pass' \
npm run e2e -w e2e
```

`E2E_COURSE` picks the course fired (default `ACCY-111` → wallet branch; use a
`FINC-*` course for the SmartResume branch).
