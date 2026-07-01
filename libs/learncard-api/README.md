# learncard-api

Shared client for the [LearnCloud Network](https://network.learncard.com) REST
API, used by the LearnCard **Profile Resolver** (#41) and **Wallet Adapter**
(#43). It owns the shared concern — base URL + scoped bearer auth + raise-on-error —
while each service keeps its own endpoint request/response models.

## What it does (and doesn't)

- ✅ Attaches `Authorization: Bearer <token>` to every request, points at the
  configured base URL, and raises `httpx.HTTPStatusError` on error responses.
- 🚫 Does **not** mint the token. The #39 spike confirmed that turning a seed
  into a session/token is the LearnCard **JS SDK**'s DID-auth flow — so the
  scoped bearer is minted once on the TS side (issuer adapter / a setup step)
  and supplied here as an env var.

## Config

| Env var | Default | Meaning |
| --- | --- | --- |
| `LEARNCARD_API_URL` | `https://network.learncard.com/api` | Network REST base (OpenAPI paths are relative to it) |
| `LEARNCARD_API_TOKEN` | `""` | Pre-minted scoped bearer JWT |

## Usage

```python
from learncard_api import LearnCardClient, LearnCardSettings

with LearnCardClient(LearnCardSettings()) as client:
    me = client.get("/profile")
    client.post("/send", json={"type": "boost", "recipient": "learner@example.com"})
```

## Develop

```bash
uv sync --all-packages
uv run pytest libs/learncard-api
```
