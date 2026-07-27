"""SmartResume Adapter — the Python service boundary for SmartResume delivery.

Delivers an achievement or credential payload into a learner's SmartResume
professional record via the SmartResume CredentialConnect API. **Verified,
signed delivery is the primary case**: the POC credential travels the full
issuance pipeline (``issue_learncard_badge`` signs every delivery) and arrives
here already carrying a ``proof``. The no-proof path — SmartResume accepts
achievements without proof as unverified skill records — is retained only for
a possible future case; no current POC course routes through it. Payload
shaping happens upstream; this adapter owns only the final-mile protocol
binding. See docs/3_design/smartresume-adapter.md."""
