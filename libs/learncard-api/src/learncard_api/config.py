"""Config for the shared LearnCloud Network API client.

The scoped bearer token is **pre-minted** and supplied via config — this lib
does not run the AuthGrant handshake. Minting a token from a seed requires the
LearnCard JS SDK's DID-auth flow (verified in the #39 spike), so it happens once
on the TS side (the issuer adapter / a setup step) and the resulting JWT is fed
here as ``LEARNCARD_API_TOKEN``. See docs/3_design/learncard-wallet-adapter.md §4.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class LearnCardSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LEARNCARD_")

    # LearnCloud Network API base. The OpenAPI paths (/send, /profile, ...) are
    # relative to this. Override: LEARNCARD_API_URL.
    api_url: str = "https://network.learncard.com/api"
    # Scoped bearer JWT minted from an AuthGrant (LEARNCARD_API_TOKEN).
    api_token: str = ""
