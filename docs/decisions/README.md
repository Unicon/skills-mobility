# Decisions (ADRs)

**Intent:** Record architecture decisions that cut across phases and components — the choice, its context, rationale, and consequences. ADRs are referenced from requirements and design docs rather than duplicated there.

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](./0001-repo-structure.md) | Repository Structure — Conventional Monorepo vs. Polylith | Accepted |
| [0002](./0002-frontend-architecture.md) | Frontend Architecture (two React SPAs, S3+CloudFront, CloudFront-layer auth) | Accepted |
| [0003](./0003-programming-language.md) | Primary Programming Language Selection (Python-first) | Accepted |

## Conventions

- Filename: `NNNN-short-title.md`, numbered sequentially.
- ADRs are **immutable history**: don't move or delete them. To retire one, set `Status: Superseded by ADR-XXXX` and add the replacement.
