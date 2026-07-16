# Local docker-compose environment

Brings up the whole pipeline — the Phase-1 spine **plus the LearnCard delivery
layer** — as containers you can build + run with one command. (Asked for by Mary;
scoped "spine now, grow as the delivery PRs merge.")

```bash
docker compose up --build     # from the repo root
```

Then: mock-lms `http://localhost:8000`, context-builder `:8100`, event-consumer
`:8200`, orchestrator `:8400`, profile-resolver `:8700`, delivery-router `:8800`,
issuer-adapter `:8910`, wallet-adapter `:8900` (each serves `/healthz`).

The LearnCard adapters/resolver need secrets (tokens + issuer seed) from the demo
provisioning step — see **Secrets** below. Without them the stack still comes up,
but LearnCard issuance/delivery/resolution report unconfigured.

## How it's wired

```
mock-lms (8000) --emits--> event-consumer (8200) --hands off--> orchestrator (8400)
     ^                                                                  |
     |                                                          builds context
     +------------------ context-builder (8100) <----------------------+
                                                                        |
                          resolve learner + deliver credential         v
   profile-resolver (8700) <---------------------------------- orchestrator
   delivery-router (8800) <------------------------------------ orchestrator
        |  routes by action
        +--> learncard-issuer-adapter (8910)  --sign OBv3-->  LearnCard network
        +--> learncard-wallet-adapter (8900)  --deliver--->   LearnCard network
```

Set via compose env (services reach each other by service name):

| Service | Env | Points at |
| --- | --- | --- |
| mock-lms | `MOCK_LMS_EVENT_CONSUMER_URL` | `http://event-consumer:8200` |
| event-consumer | `EVENT_CONSUMER_ORCHESTRATOR_URL` | `http://orchestrator:8400` |
| context-builder | `CONTEXT_BUILDER_LMS_BASE_URL` | `http://mock-lms:8000` |
| orchestrator | `ORCHESTRATOR_CONTEXT_BUILDER_URL` | `http://context-builder:8100` |
| orchestrator | `ORCHESTRATOR_PROFILE_RESOLVER_URL` | `http://profile-resolver:8700` |
| orchestrator | `ORCHESTRATOR_DELIVERY_ROUTER_URL` | `http://delivery-router:8800` |
| delivery-router | `DELIVERY_ROUTER_LEARNCARD_ISSUER_URL` | `http://learncard-issuer-adapter:8910` |
| delivery-router | `DELIVERY_ROUTER_LEARNCARD_WALLET_URL` | `http://learncard-wallet-adapter:8900` |

SQLite state for event-consumer, orchestrator and profile-resolver lives in named volumes.

## Secrets

The LearnCard layer reads secrets via compose interpolation from a **gitignored
root `.env`** (copy [`.env.example`](../.env.example)). They come from the demo
provisioning step (`tools/learncard-demo`, ADR-0020) — `provision.mjs` derives the
fixed demo wallets from committed non-secret labels and emits the tokens/seed:

- `LEARNCARD_API_TOKEN` — sender bearer for profile-resolver + wallet-adapter.
- `LEARNCARD_RECIPIENT_API_TOKEN` — recipient read token for the wallet read-back.
- `SEED_LABEL` (default `organization`) — the issuer adapter derives its signing
  seed from this label internally (#48 option b): nothing to copy or compute by
  hand. In the demo the issuer is the *organization* profile `provision.mjs`
  provisions (#54). `SECURE_SEED` (left blank) overrides it only for a standalone
  throwaway identity.
- `LEARNCARD_ISSUER_DID` — the issuer's resolvable network DID, stamped as the
  OBv3 issuer (`ORCHESTRATOR_ISSUER_ID`); signing fails if it isn't resolvable.
- `LEARNCARD_DEMO_RECIPIENT_PROFILE_ID` / `LEARNCARD_ISSUER_PROFILE_ID` — fixed
  demo handles (default to `smi-demo-learner` / `smi-demo-organization`).

## The image pattern

One shared image (`Dockerfile.python`) builds the whole uv workspace
(`uv sync --all-packages --frozen`); each service is the *same* image run with a
different `command`. The commands run `uvicorn` on `0.0.0.0` (the `run()`
entrypoints bind `127.0.0.1` — right for local dev, unreachable across
containers) and call `logging.basicConfig(INFO)` first, so the services' own
app-level logs (gate decisions, ingress, LMS fetches) show in `docker compose
logs`, not just uvicorn's access lines.

The **LearnCard Issuer Adapter** is the one non-Python service (Node/TS), so it
has its own image (`docker/Dockerfile.node`: `npm ci` + `tsc` build, `express`
listens on `0.0.0.0`).

## Not included

The mock-lms React UI runs separately (`cd apps/mock-lms && npm run dev`) — this
compose is the backend pipeline.
