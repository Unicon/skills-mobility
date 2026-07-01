"""LearnCard Wallet Adapter — the Python service boundary for wallet delivery.

Takes an already-issued (signed) credential plus the recipient's resolved
LearnCard profile ID and delivers it to the recipient's wallet via the
LearnCloud Network API. Issuance and profile resolution happen upstream; this
adapter owns only the post-issuance delivery call. See
docs/3_design/learncard-wallet-adapter.md."""
