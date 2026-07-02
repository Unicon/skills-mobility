# learncard-profile-resolver

Resolves a learner identifier to a LearnCard profile (`profileId` + DID). The
Orchestrator invokes it as a step before any LearnCard issuance or delivery, so
the issuer (TS) and wallet (Python) adapters consume a resolved `profileId`
without each re-implementing resolution.

See [design](../../docs/3_design/learncard-profile-resolver.md).

## What it resolves (and what it can't)

Scoped to what the LearnCard REST API actually supports (verified live, [#41](https://github.com/Unicon/skills-mobility/issues/41)):

1. **Mapping store** — a previously resolved learner returns immediately (`resolution_method: stored`), no API call.
2. **Search Profiles** — a LearnCard handle (`learner_id_type: profile_id`) is looked up via `GET /search/profiles/{input}`; an exact handle match resolves (`searched`).
3. **Everything else → `unresolved`.** There is **no create path**: creating a learner's profile needs Profile-Manager provisioning, and Search does **not** match email. An `email` identifier therefore always returns `unresolved`.

## Endpoint

`POST /resolve-learncard-profile`

```json
{
  "contract_version": "v1",
  "workflow_id": "wf_123",
  "execution_id": "exec_123",
  "step_id": "step_resolve_profile",
  "correlation_id": "corr_123",
  "delivery_config_ref": "learncard-dev",
  "payload": { "learner_id_type": "profile_id", "learner_id_value": "smi-learner-1" }
}
```

Responses:
- Resolved → `{"status": "succeeded", "result": {"profile_id": "...", "did": "...", "resolution_method": "stored|searched"}, "error": null}`
- No profile → `{"status": "unresolved", "result": null, "error": null}`
- API/transport error → `{"status": "failed", "result": null, "error": {"message": "..."}}`

## Run

```bash
uv sync --all-packages
cp services/learncard-profile-resolver/.env.example services/learncard-profile-resolver/.env  # set LEARNCARD_API_TOKEN
uv run learncard-profile-resolver          # http://127.0.0.1:8700 — Swagger at /docs
```

Smoke test: `curl -s localhost:8700/healthz`

## Config

| Env var | Default | Meaning |
| --- | --- | --- |
| `LEARNCARD_PROFILE_RESOLVER_PORT` | `8700` | Local HTTP port (clear of Consul's 8300) |
| `LEARNCARD_PROFILE_RESOLVER_DB_PATH` | `learncard-profile-resolver.db` | SQLite mapping store (`:memory:` for ephemeral) |
| `LEARNCARD_PROFILE_RESOLVER_LOG_LEVEL` | `INFO` | Root log level |
| `LEARNCARD_API_URL` | `https://network.learncard.com/api` | LearnCloud Network REST base (`libs/learncard-api`) |
| `LEARNCARD_API_TOKEN` | `""` | Pre-minted scoped bearer JWT (see #39) |

## Test

```bash
uv run pytest services/learncard-profile-resolver
```

Tests use `httpx.MockTransport` and in-memory SQLite — no live LearnCard access.
