# 0017. Admin UI Frontend Stack and Design-Token Architecture

- Status: Accepted
- Date: 2026-06-25
- Related: [ADR-0001](./0001-repo-structure.md) · [ADR-0002](./0002-frontend-architecture.md) · [Admin UI Requirements](../2_requirements/admin-ui.md) · [Admin UI Design](../3_design/admin-ui.md) · [Mock LMS Design](../3_design/mock-lms.md)

## Context

[ADR-0002](./0002-frontend-architecture.md) chartered two React SPAs (Mock LMS and Admin), static on S3 + CloudFront, single demo user, CloudFront-layer auth. It did not settle the *frontend stack* — component layer, styling approach, design tokens, or shared-code structure.

The first SPA, `apps/mock-lms`, was built with hand-authored CSS and a distinctive dark "mission-control" aesthetic (warm near-black panels, gold credential signal, live-green status, per-event telemetry colors, Archivo + JetBrains Mono). It uses Motion for animation and hand-rolls everything else — including behavior primitives (a modal, copyable ids, a JSON viewer) and a small set of design values.

Building the second SPA (`apps/admin`) is the moment to settle the shared stack, so the two apps converge instead of diverging and so the visual identity is captured as reusable tokens rather than duplicated CSS. ADR-0002 is Accepted and treated as immutable; this ADR extends it with the stack and token decisions rather than rewriting it.

## Decision

### Animation

Keep **Motion** (`framer-motion` / `motion/react`). It is MIT-licensed and free; only the separate **Motion+** product is paid, and the POC does not need it. The Mock LMS already uses it, so both apps share one animation library.

### Components

Use **Radix Primitives** (headless, unstyled) styled with our own CSS. **Base UI** is an acceptable alternative primitive layer on a per-component basis. The primitive layer supplies accessible behavior (dialogs, popovers, tabs, collapsibles); our CSS owns all visual styling.

**Not adopted:** **shadcn/ui** and **Tailwind**. Styling is plain CSS driven by design tokens, consistent with the Mock LMS's existing hand-authored CSS.

### Design tokens — three layers

1. **Base / primitive** — [Open Props](https://open-props.style) scales (spacing, sizing, type scale, radii, shadows, easings) + [Radix Colors](https://www.radix-ui.com/colors) 12-step light/dark scales. Both are free, pure CSS variables, no Tailwind. Open Props fills the scales the Mock LMS lacks today; Radix Colors supplies systematic color ramps.
2. **Semantic** — our names mapped onto the base layer: `--bg`, `--panel`, `--gold`, `--live`, the event-type colors `--evt-*`, and scale aliases `--space-*`, `--radius-*`, `--text-*`. This is the contract both apps — and, later, Figma — consume.
3. **Component** — component-local variables referencing the semantic layer.

The existing Mock LMS `apps/mock-lms/src/index.css` is the de-facto source of the semantic layer; the token system formalizes it. The mission-control identity is preserved **through this layer**, not re-invented per app.

### Shared code

Introduce two shared packages under `packages/` ([ADR-0001](./0001-repo-structure.md): `apps/` may depend on `packages/`):

- **`packages/ui`** — the design tokens plus shared primitives: the JSON/envelope viewer, the event-type color mapping, and the copyable correlation-id affordance.
- **`packages/contracts`** — shared TypeScript types and typed API clients (orchestrator `ExecutionView`/`StepResult`; Mock LMS emission/envelope shapes).

The extraction of these packages and the migration of `apps/mock-lms` onto them is implementation work, deferred to a later round; this ADR records the target structure.

## Rationale

- **Free and self-hosted.** Motion (MIT), Radix Primitives/Colors, Open Props, and Base UI are all free and vendored; no SaaS or paid tier enters the POC.
- **Preserve the existing identity.** The Mock LMS aesthetic already reads as a credible "mission-control" instrument. A token layer captures it once and lets the Admin UI inherit it, avoiding a second, divergent visual language.
- **Accessibility without a visual framework.** Radix/Base primitives give correct dialog/popover/tabs behavior that the Mock LMS built by hand, while leaving styling to our CSS — so we gain robustness without adopting Tailwind or shadcn's opinions.
- **No Tailwind/shadcn.** The Mock LMS is plain CSS; introducing a utility framework now would mean either rewriting it or running two styling models. Tokens + plain CSS keep one model across both apps.
- **Shared packages prevent drift.** A second app is exactly when duplicated UI atoms and ad-hoc API typing start to diverge; `packages/ui` and `packages/contracts` give both apps one source of truth.

## Consequences

### Positive

- Both SPAs share one animation library, one token system, and one set of UI primitives and contracts.
- The mission-control identity becomes a reusable, documentable artifact (and a future Figma source) rather than CSS trapped in one app.
- Accessible behavior primitives come for free without adopting a CSS framework.
- All chosen libraries are free and self-hosted.

### Negative

- Standing up `packages/ui` and `packages/contracts` and migrating `apps/mock-lms` onto them is additional up-front work before the Admin UI fully benefits.
- Hand-authored CSS over headless primitives is more verbose than a styled component kit like shadcn — the cost of keeping full control of the visual layer.
- Two primitive options (Radix and Base UI) require a light per-component judgment rather than a single default.

## Alternatives considered

- **Tailwind + shadcn/ui.** Fast to assemble, but would clash with the Mock LMS's existing plain-CSS aesthetic (forcing a rewrite or a split styling model) and pull in utility-class conventions the team did not want for the POC.
- **Continue hand-rolling everything (no primitive library).** Matches the Mock LMS as-is, but re-implementing accessible dialogs/popovers/tabs by hand for the Admin UI is avoidable effort and a likely source of a11y bugs.
- **A full design-system/component library (e.g. MUI, Mantine).** Heavier and visually opinionated; would override the existing identity and add more than the POC needs.
- **Extend ADR-0002 in place instead of a new ADR.** Rejected: ADR-0002 is Accepted and ADRs are immutable history (decisions README); these are new cross-cutting decisions and belong in a new, referencing ADR.
