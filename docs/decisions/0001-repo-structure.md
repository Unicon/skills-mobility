# ADR-0001: Repository Structure - Conventional Monorepo vs. Polylith

Status: Accepted
Date: 2026-06-10

## Context

The Skills Mobility Infrastructure project requires a repository structure capable of supporting:

* Multiple backend services
* Shared libraries and domain models
* Infrastructure-as-code
* Documentation
* Open source development
* React frontend applications

The current project is a proof of concept focused on validating orchestration, context assembly, policy evaluation, delivery, and auditability across multiple components. The repository structure needs to be understandable to contributors, compatible with common Python and React tooling, and flexible enough to evolve as the POC scope becomes clearer.

The team evaluated two approaches:

1. Conventional monorepo
2. Polylith for Python

Polylith was considered because it provides strong architectural guardrails, explicit component boundaries, support for reusable components, and flexibility across multiple deployment targets such as Lambda, Docker, and serverless platforms. The team also has prior experience with Polylith and considered potential alignment with patterns used in the LIF project.

A conventional monorepo was considered because it provides a familiar structure for Python and React development, integrates naturally with common tooling, and supports the expected shape of the project, including frontend applications, backend services, shared libraries, infrastructure, and documentation.

## Decision

The project will use a conventional monorepo structure.

The repository will be organized into applications, services, shared libraries, shared packages, infrastructure, and documentation:

```
skills-mobility/
  apps/
    <frontend-app>/

  services/
    <backend-service>/

  libs/
    <python-library>/

  packages/
    <typescript-or-cross-stack-package>/

  infra/

  docs/
```

### Repository Conventions

* `apps/` contains deployable frontend applications.
* `services/` contains deployable backend services.
* `libs/` contains shared Python libraries, domain logic, and models that are reused by multiple services.
* `packages/` contains shared TypeScript packages and cross-stack assets such as client libraries, UI packages, and contract definitions intended for JavaScript/TypeScript consumers.
* `infra/` contains infrastructure and deployment configuration.
* `docs/` contains project documentation and ADRs.

### Dependency Rules

* `apps/` may depend on `packages/` but must not import code from `services/`.
* `services/` may depend on `libs/` and, where appropriate, packages that contain generated clients or shared contract artifacts.
* `services/` must not import code from other `services/` directly; cross-service interaction should occur through APIs, events, or other explicit interfaces.
* `libs/` must not depend on `apps/` or `services/`.
* Shared contracts that appear in both Python and TypeScript must have a documented source of truth to reduce schema drift.

### Deferred Decisions

The following decisions are intentionally deferred and should be captured in follow-up ADRs if they become material to delivery:

* Python workspace and packaging tooling — **provisionally exercised** by the first code landing; see [Implementation Notes](#implementation-notes-2026-06-10).
* JavaScript/TypeScript workspace tooling
* Contract generation and schema ownership across Python and TypeScript
* CI checks used to enforce dependency boundaries

## Rationale

### Monorepo

Pros

* Still understandable to most developers.
* Clearer deployable boundaries than a single src/ package.
* Good fit for multiple Lambdas, mock APIs, shared client libraries, and infrastructure.
* Easier to split into separate repos later if needed.
* More conventional than Polylith.

Cons

* Shared library versioning can become annoying.
* Need decisions about workspace tooling: uv, Poetry, Hatch, Pants, etc.
* Without discipline, local path dependencies can become messy.

Best fit: a POC with multiple deployable units where obvious service boundaries are useful, but a specialized component model is not yet justified.

Overall, the simple monorepo with services/ and libs/ is a better fit for several Lambdas or shared services plus shared code, whereas Polylith is a better fit for multiple deployables with substantial reusable domain components. For this project, the team does not currently anticipate that level of reuse.

The team also determined that many of the architectural goals supported by Polylith can be addressed through conventional tooling and practices, including:

* Package boundaries
* Linting
* CI validation
* Import restrictions
* Code review
* Documentation
* Architectural conventions


## Consequences

### Positive

* Clear separation between frontend applications, backend services, shared libraries, infrastructure, and documentation
* Straightforward integration of Python and React projects
* Compatibility with common tooling and contributor expectations
* Flexibility to evolve service boundaries as requirements mature
* Ability to enforce architectural boundaries through tooling and process

### Negative

* Architectural boundaries are enforced primarily through conventions and tooling rather than repository-level constraints
* Additional discipline is required to prevent excessive coupling between services and libraries
* Some benefits provided by Polylith’s component model are not available out of the box
* Repository structure may need to be revisited if the project grows substantially in size or complexity

### Revisit Triggers

This decision should be revisited if one or more of the following occur:

* Shared logic is repeatedly copied or awkwardly extracted across multiple services
* Service boundaries become difficult to enforce with conventional linting, CI, and code review
* The number of deployables or independently reusable components grows enough that build, test, or ownership boundaries become hard to manage
* The project needs stricter architectural enforcement than the monorepo conventions provide

## Implementation Notes (2026-06-10)

The first code landed with the Mock Event Producer. These choices are
**provisional** — they exercise the structure above without re-opening the
decision, and may be moved if the lead prefers a different direction.

### Directories instantiated

The placeholder directories from the layout above now have their first real
occupants:

```
skills-mobility/
  apps/mock-lms/        # mock-lms-ui: React + TS + Vite demo console
  libs/events/          # skills-mobility-events: shared event contracts (Pydantic)
  services/mock-lms/    # mock-lms: Canvas-style LMS Resource APIs + event emission
  pyproject.toml        # uv workspace root (virtual; not a package)
  .python-version       # 3.12 (per ADR-0003)
```

`packages/` and `infra/` remain unpopulated until generated TS contracts and CDK
land (per the Mock Event Producer design's build order). The React app uses
npm + Vite (not part of the uv workspace); a JS/TS workspace tool remains a
deferred decision should a second JS package appear.

### Python workspace tooling (provisional): uv workspace

This addresses the deferred "Python workspace and packaging tooling" item.

- A **uv workspace** is declared at the repo root (`[tool.uv.workspace]` with
  members `libs/*` and `services/*`). The root is virtual (`package = false`).
- Each member is a standalone package with its own `pyproject.toml` and a
  `src/` layout, built with **hatchling**.
- Cross-package dependencies use uv workspace sources (e.g. `mock-lms` depends
  on `skills-mobility-events` via `{ workspace = true }`), so the dependency
  rules above (`services/` may depend on `libs/`) are expressed in metadata, not
  just convention.
- Shared dev tooling (pytest, ruff, mypy, coverage — per CLAUDE.md) is pinned in
  the root `[dependency-groups].dev` and configured once at the root.
- `uv.lock` and `.python-version` are committed; `.venv/` and tool caches are
  gitignored.

Common commands:

```bash
uv sync --all-packages          # create env + install all members
uv run pytest                   # run the whole suite
uv run ruff check .             # lint
uv run mypy libs/*/src services/*/src   # type-check
uv run mock-lms                 # run the service locally
```

Why uv: single fast tool for venv + resolution + workspace, first-class
multi-package monorepo support, and a committed lockfile for reproducibility —
which keeps the "lightweight POC" intent while still enforcing package
boundaries. Alternatives (Poetry, Hatch, Pants/uv-less pip) were not separately
evaluated in an ADR; if the lead wants a different tool, the per-package
`pyproject.toml` files port with minimal change.

## Alternatives Considered

### Polylith for Python

Polylith’s Python docs describe its main use case as supporting one or more microservices/apps in a monorepo while sharing code between services. It organizes code into reusable “bricks”: components for business logic and bases for application/service entry points.  

Polylith offers advantages in architectural convention enforcement, reusable isolated components, deployment flexibility, and existing team experience.

Pros

* Stronger architectural guardrails.
* Good for shared logic across multiple deployables.
* Encourages thin entry points and reusable components.
* Can work well when the team already understands it.
* Helpful if you expect the POC to evolve into many services/Lambdas.

Cons

* Less common in Python.
* Higher onboarding cost.
* Requires explaining Polylith vocabulary: bases, components, bricks, projects.
* Tooling and IDE setup may be less familiar.
* Future maintainers may need to learn the architecture before making simple changes.

It was not selected because the expected benefits did not currently justify the additional repository structure and conventions for the POC.
