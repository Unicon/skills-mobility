"""LearnCard Profile Resolver — resolves a learner identifier to a LearnCard
profile (``profileId`` + DID), invoked by the Orchestrator as a step before any
LearnCard issuance or delivery. Centralizes resolution so the issuer (TS) and
wallet (Python) adapters don't each duplicate it.

Scoped to what LearnCard REST actually supports (verified in the #41 spike):
mapping-store lookup, then Search Profiles by handle. There is no create path —
creating a learner's profile needs Profile-Manager provisioning, and Search does
not match on email. See docs/3_design/learncard-profile-resolver.md."""
