"""SmartResume Adapter — the Python service boundary for SmartResume delivery.

Delivers an achievement or credential payload into a learner's SmartResume
professional record via the SmartResume CredentialConnect API. The primary POC
case is a non-credential-enabled course achievement (no ``proof``), which
SmartResume accepts as an unverified skill record; an already-issued VC with a
``proof`` is delivered in the same shape. Payload shaping happens upstream; this
adapter owns only the final-mile protocol binding. See
docs/3_design/smartresume-adapter.md."""
