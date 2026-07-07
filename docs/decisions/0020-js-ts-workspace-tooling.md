# 0020. JS/TS Workspace Tooling and Token Publishing

- Status: Accepted
- Date: 2026-06-30
- Related: [ADR-0001](./0001-repo-structure.md) · [ADR-0002](./0002-frontend-architecture.md) · [ADR-0018](./0018-admin-ui-frontend-stack.md) · [Admin UI Design](../3_design/admin-ui.md)

## Context

[ADR-0018](./0018-admin-ui-frontend-stack.md) settled the Admin UI's *libraries and token architecture* (Radix Primitives, Open Props + Radix Colors, Motion, and two shared packages `packages/ui` and `packages/contracts`) but explicitly left the *workspace plumbing* open, to be resolved "before extraction — preferably in a short follow-up ADR." [ADR-0001](./0001-repo-structure.md) had likewise deferred JS/TS monorepo tooling: the Python side runs a `uv` workspace (`libs/*`, `services/*`), while the JS side is currently per-app with no root.

Today there is no root `package.json`, no JS workspace, and `apps/mock-lms` carries its own `package-lock.json`. Introducing `packages/*` that both `apps/mock-lms` and the new `apps/admin` consume forces the deferred decision. ADR-0018 named the specifics this ADR must cover: the workspace manager, the package names and public entry points, TypeScript project references / build order, and how the CSS token layer is published and consumed. This is that follow-up ADR.

## Decision

### Workspace manager — npm workspaces

Adopt **npm workspaces**. A root `package.json` declares the members and is the only place dependencies are installed from:

```jsonc
{
  "name": "skills-mobility",
  "private": true,
  "workspaces": ["apps/*", "packages/*"]
}
```

npm is already the package manager in use; this adds no new tool and mirrors the structure of the existing `uv` workspace (one workspace per language, members under globbed directories). pnpm and yarn were considered but rejected for the POC: both add a tool and CI wiring to gain isolation guarantees the POC does not need.

### Lockfile — single root

There is **one root `package-lock.json`**, and `apps/mock-lms/package-lock.json` is removed. A single root lockfile is the canonical npm-workspaces model; keeping a per-app lockfile alongside it invites install drift, since workspace resolution and hoisting happen at the root.

### Package names and entry points

Shared packages take the **`@skills-mobility`** scope; apps keep their existing unscoped names (`mock-lms-ui`, and `admin-ui` for the new app) to avoid churn.

- **`@skills-mobility/ui`** — exposes its TypeScript entry and its token CSS as separate subpaths:
  ```jsonc
  {
    "name": "@skills-mobility/ui",
    "private": true,
    "type": "module",
    "exports": {
      ".": "./src/index.ts",
      "./tokens.css": "./src/tokens/index.css"
    }
  }
  ```
- **`@skills-mobility/contracts`** — exposes its TypeScript entry:
  ```jsonc
  {
    "name": "@skills-mobility/contracts",
    "private": true,
    "type": "module",
    "exports": { ".": "./src/index.ts" }
  }
  ```

Apps depend on them by name with the workspace wildcard (`"@skills-mobility/ui": "*"`), which npm resolves to the local package via a symlink.

### Build and consumption — no build step, consume source directly

The packages are **not pre-built**. Both apps build with Vite, which compiles workspace TypeScript source on demand, so the apps consume the packages' `src/` directly:

- **TypeScript** — `exports["."]` points at `src/index.ts`. Apps and packages use `"moduleResolution": "bundler"` (matching Vite), so `tsc --noEmit` type-checks straight through to package source. No emitted `dist/`, no `composite`, no project references.
- **CSS tokens** — `@skills-mobility/ui` ships plain `.css` files. An app pulls the token layer in with a direct import, `import "@skills-mobility/ui/tokens.css"`, which Vite handles natively. The token CSS is authored once in the package and is never bundled or transformed by a package-level build.

This resolves ADR-0018's "TypeScript project references / build order" item by **eliminating** the build order: with source consumption there is no inter-package build to sequence. Vite owns the dependency graph at app-build time, and type-checking is per-workspace (`tsc --noEmit`).

### Root scripts

Dependencies install once from the root (`npm install`). Per-app dev and build run through workspace selection (`npm run dev -w apps/admin`, `npm run build -w apps/mock-lms`); a root `typecheck` fans out with `npm run typecheck --workspaces --if-present`.

## Rationale

- **Lightest tooling that fits the POC.** npm workspaces reuses the package manager already present and parallels the `uv` workspace mental model — one workspace per language, single root lockfile each.
- **No build step removes a whole class of plumbing.** Source consumption means no `dist/`, no `.d.ts` emit, no project-reference graph, and no build-order bugs. Vite already compiles TypeScript and imports CSS, so the packages lean on the toolchain both apps already run.
- **Plain CSS token publishing matches the styling decision.** ADR-0018 chose plain CSS driven by tokens; shipping the token layer as importable `.css` keeps it as plain CSS end to end, with no CSS-in-JS or package build to reconcile.
- **One source of truth, minimal churn.** Scoped package names make shared imports unambiguous while leaving the working `apps/mock-lms` name untouched.

## Consequences

### Positive

- A single `npm install` from the root wires both apps and both packages; one lockfile to review.
- Editing `packages/ui` or `packages/contracts` is reflected in the apps immediately — no rebuild/watch step between a package and its consumers.
- The token layer stays plain CSS, importable by any Vite app, with no transform to keep in sync.

### Negative

- The shared packages are **internal-only**: consuming their TypeScript source requires a TS-aware bundler (Vite). They are not independently publishable or usable by a non-Vite consumer as-is. Acceptable — the only consumers are the two in-repo SPAs.
- npm hoists workspace dependencies to the root, so **React (and other singletons) must be kept at one version across the workspace** to avoid duplicate-copy bugs. The baseline is **React 19** ([Admin UI Design §5](../3_design/admin-ui.md)); `apps/mock-lms` is on React 18.3 today and migrates to 19 as part of workspace adoption rather than the two apps diverging.
- Removing `apps/mock-lms/package-lock.json` and moving installs to the root changes the app's local setup; the migration must update any per-app install instructions.

## Alternatives considered

- **pnpm or yarn workspaces.** Stricter isolation and faster installs, but each adds a tool and CI wiring the POC does not need; npm workspaces covers the monorepo requirement with what is already installed.
- **Pre-built packages with TypeScript project references.** Emitting `dist/` with `.d.ts` and a `composite` build graph gives publishable, bundler-agnostic packages and enforced boundaries — at the cost of a build step, watch mode between packages and apps, and build-order maintenance. Unnecessary when both consumers are Vite apps in the same repo.
- **Keeping per-app lockfiles / no root workspace.** Continuing the current per-app setup avoids touching `apps/mock-lms`, but then `packages/*` cannot be shared cleanly and dependency versions drift between apps — the exact divergence ADR-0018's shared packages exist to prevent.
