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

By default the check runs **both delivery branches** as separate tests:
`ACCY-111` (→ `deliver_to_learncard_wallet`) and `FINC-106`
(→ `deliver_to_smartresume`), each asserting its branch's delivery step ran and
that `result.delivery` is populated (#139). `E2E_COURSE` narrows the run to a
single course (an unlisted course runs as a wallet-branch scenario).
