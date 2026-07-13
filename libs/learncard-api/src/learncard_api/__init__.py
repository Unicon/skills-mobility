"""Shared LearnCloud Network API client for the Skills Mobility POC.

Both the LearnCard Profile Resolver (#41) and the LearnCard Wallet Adapter (#43)
call LearnCloud Network REST endpoints with a scoped bearer token. Rather than
duplicate the auth + transport wiring, they share ``LearnCardClient`` here.

The token is pre-minted (see config) — this lib never runs the AuthGrant flow.
"""

from learncard_api.client import LearnCardClient
from learncard_api.config import LearnCardSettings

__all__ = [
    "LearnCardClient",
    "LearnCardSettings",
]
