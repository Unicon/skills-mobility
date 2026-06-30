# 0018. Admin UI Frontend Stack and Design-Token Architecture

- Status: Accepted
- Date: 2026-06-25
- Related: [ADR-0001](./0001-repo-structure.md) · [ADR-0002](./0002-frontend-architecture.md) · [ADR-0019](./0019-js-ts-workspace-tooling.md) · [Admin UI Requirements](../2_requirements/admin-ui.md) · [Admin UI Design](../3_design/admin-ui.md) · [Mock LMS Design](../3_design/mock-lms.md)

## Context

[ADR-0002](./0002-frontend-architecture.md) chartered two React SPAs (Mock LMS and Admin), static on S3 + CloudFront, single demo user, CloudFront-layer auth. It did not settle the *frontend stack* — component layer, styling approach, design tokens, or shared-code structure.

The first SPA, `apps/mock-lms`, was built with hand-authored CSS and a distinctive dark instrumentation look (its **current** aesthetic: warm near-black panels, a gold accent, live-green status, per-event telemetry colors, Archivo + JetBrains Mono). That look is the current state, **not a committed long-term UX decision** — it may be revised, and this ADR is about the token *architecture* that captures whatever the identity is, not about mandating this particular palette. The Mock LMS uses Motion for animation and hand-rolls everything else — including behavior primitives (a modal, copyable ids, a JSON viewer) and a small set of design values.

Building the second SPA (`apps/admin`) is the moment to settle the shared stack, so the two apps converge instead of diverging and so the visual identity is captured as reusable tokens rather than duplicated CSS. ADR-0002 is Accepted; this ADR adds the stack and token decisions in a new, referencing ADR rather than reopening it.

## Decision

### Animation

Keep **Motion** — the same library the Mock LMS already uses. It is MIT-licensed and free; only the separate **Motion+** product is paid, and the POC does not need it.

Standardize on the current **`motion`** package (`import { … } from "motion/react"`), which is the renamed continuation of `framer-motion` (the official docs now install `motion`). The Mock LMS currently depends on `framer-motion` and imports from it; to avoid the two apps starting with split imports, `apps/mock-lms` migrates from `framer-motion` to `motion` as part of its `packages/ui` migration (build-order step 2 in the design doc). Until that migration lands, the Admin UI MAY use either import path, but the **target is a single `motion` dependency across both apps** — not a permanent `framer-motion`/`motion` split.

### Components

Use **Radix Primitives** (headless, unstyled) styled with our own CSS. **Base UI** is an acceptable alternative primitive layer on a per-component basis. The primitive layer supplies accessible behavior (dialogs, popovers, tabs, collapsibles); our CSS owns all visual styling.

**Not adopted:** **shadcn/ui** and **Tailwind**. Styling is plain CSS driven by design tokens, consistent with the Mock LMS's existing hand-authored CSS.

### React version

Standardize the workspace on **React 19** (baseline added 2026-06-30). The Mock LMS is on React 18.3 today and migrates to 19 as part of its `packages/ui` adoption. Because the JS workspace hoists a single React copy ([ADR-0019](./0019-js-ts-workspace-tooling.md)), both apps share one version rather than diverging; React 19 is the baseline both inherit. Radix Primitives and Motion both support React 19, and the token layer is framework-agnostic CSS.

### Design tokens — three layers

1. **Base / primitive** — [Open Props](https://open-props.style) scales (spacing, sizing, type scale, radii, shadows, easings) + [Radix Colors](https://www.radix-ui.com/colors) 12-step light/dark scales. Both are free, pure CSS variables, no Tailwind. Open Props fills the scales the Mock LMS lacks today; Radix Colors supplies systematic color ramps.
2. **Semantic** — our names mapped onto the base layer (the specific names/values below are **illustrative of the current look, not fixed by this ADR**): e.g. `--bg`, `--panel`, `--gold`, `--live`, the event-type colors `--evt-*`, and scale aliases `--space-*`, `--radius-*`, `--text-*`. This is the contract both apps — and, later, Figma — consume; the **layering** is the decision here, not any particular palette.
3. **Component** — component-local variables referencing the semantic layer.

The existing Mock LMS `apps/mock-lms/src/index.css` is the de-facto source of the semantic layer; the token system formalizes it. Whatever the current visual identity is, it is preserved **through this layer** rather than re-invented per app — and it can be re-themed at the semantic layer if the look changes later.

### Shared code

Introduce two shared packages under `packages/` ([ADR-0001](./0001-repo-structure.md): `apps/` may depend on `packages/`):

- **`packages/ui`** — the design tokens plus shared primitives: the JSON/envelope viewer, the event-type color mapping, and the copyable correlation-id affordance.
- **`packages/contracts`** — shared TypeScript types and typed API clients. The Orchestrator's read model (its `ExecutionMetadata`/`StepResult` shapes) is surfaced to the SPA as a **client-side** type defined here, *derived from* the Orchestrator contract rather than importing a backend type; plus the Mock LMS emission/envelope shapes.

The extraction of these packages and the migration of `apps/mock-lms` onto them is implementation work, deferred to a later round; this ADR records the target structure.

**Open dependency — JS/TS workspace tooling.** [ADR-0001](./0001-repo-structure.md) deferred JS/TS monorepo workspace tooling (the Python side uses a `uv` workspace; the JS side is currently per-app). Introducing `packages/*` that both apps consume forces that deferred decision. It is **not settled here** and SHALL be resolved before extraction — preferably in a short follow-up ADR — covering at least: workspace manager (npm workspaces vs pnpm/yarn), the package names and public entry points, TypeScript project references / build order, and how the CSS token layer is published and consumed by both apps (e.g. a plain CSS import vs a build step). This ADR settles the *libraries and the token architecture*; it does not settle the *workspace plumbing*.

## Rationale

- **Free and self-hosted.** Motion (MIT), Radix Primitives/Colors, Open Props, and Base UI are all free and vendored; no SaaS or paid tier enters the POC.
- **Preserve the existing identity.** The Mock LMS already has a coherent visual identity. A token layer captures whatever that identity is, once, and lets the Admin UI inherit it — avoiding a second, divergent visual language while leaving room to re-theme later.
- **Accessibility without a visual framework.** Radix/Base primitives give correct dialog/popover/tabs behavior that the Mock LMS built by hand, while leaving styling to our CSS — so we gain robustness without adopting Tailwind or shadcn's opinions.
- **No Tailwind/shadcn.** The Mock LMS is plain CSS; introducing a utility framework now would mean either rewriting it or running two styling models. Tokens + plain CSS keep one model across both apps.
- **Shared packages prevent drift.** A second app is exactly when duplicated UI atoms and ad-hoc API typing start to diverge; `packages/ui` and `packages/contracts` give both apps one source of truth.

## Consequences

### Positive

- Both SPAs share one animation library, one token system, and one set of UI primitives and contracts.
- The visual identity becomes a reusable, documentable artifact (and a future Figma source) rather than CSS trapped in one app, and can be re-themed at the semantic layer if it changes.
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
