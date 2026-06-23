"""The Phase-1 deterministic workflow plan (no LLM planning).

Pure function: runs the fixed step sequence against the injected client seams and
returns the ExecutionRecord. Persistence (the "record outcome" step) is the
caller's job. The offloaded LLM Decision Services and Policy Rules are bypassed;
``prepare_issuer_input`` is the Orchestrator's deterministic stand-in for the
transformation pipeline.
"""

from __future__ import annotations

from typing import Any

from orchestrator import obv3
from orchestrator.clients import ContextBuilderClient, DeliveryRouterClient, ProfileResolverClient
from orchestrator.schemas import ExecutionRecord, RunRequest, StepTrace


def run_workflow(
    request: RunRequest,
    *,
    context_builder: ContextBuilderClient,
    profile_resolver: ProfileResolverClient,
    delivery_router: DeliveryRouterClient,
    issuer_id: str,
) -> ExecutionRecord:
    event = request.event
    metadata = event.get("metadata", {})
    steps: list[StepTrace] = []

    def trace(step: str, status: str, note: str = "") -> None:
        steps.append(StepTrace(step=step, status=status, note=note))

    def record(status: str, result: dict[str, Any] | None = None) -> ExecutionRecord:
        return ExecutionRecord(
            execution_id=request.execution_id,
            event_type=metadata.get("event_name"),
            status=status,
            steps=steps,
            result=result or {},
        )

    # 2. Build context (real Context Builder swaps in here).
    bundle = context_builder.build_context(request.execution_id, event)
    if "context_builder_error" in bundle:
        trace("build_context", "error", "context builder could not start")
        return record("failed")
    trace("build_context", "ok", f"{len(bundle.get('source_data', {}))} source keys")

    # 3. Resolve the learner's LearnCard profile (stub).
    profile = profile_resolver.resolve(metadata.get("user_id", ""))
    did, profile_id = profile["did"], profile["profile_id"]
    trace("resolve_profile", "stubbed", f"{profile_id} ({profile.get('resolution_method')})")

    # 4. Prepare the unsigned OBv3 input (Orchestrator-owned Phase-1 transform stub).
    unsigned_vc = obv3.build_unsigned_obv3(bundle, did, issuer_id)
    trace("prepare_issuer_input", "ok", unsigned_vc["credentialSubject"]["achievement"]["name"])

    # 5. Issue via the Delivery Router → LearnCard Issuer Adapter (stub).
    issued = delivery_router.dispatch("issue_learncard_badge", {"unsigned_vc": unsigned_vc})
    if issued.get("status") != "succeeded":
        trace("issue", "error", str(issued.get("error")))
        return record("failed")
    signed_credential = issued["result"]["issued_credential"]
    trace("issue", "stubbed", str(issued.get("external_reference_id", "")))

    # 6. Prepare the wallet-delivery input.
    wallet_payload = obv3.prepare_wallet_input(signed_credential, profile_id)
    trace("prepare_wallet_input", "ok")

    # 7. Deliver to the wallet via the Delivery Router → LearnCard Wallet Adapter (stub).
    delivered = delivery_router.dispatch("deliver_to_learncard_wallet", wallet_payload)
    if delivered.get("status") != "succeeded":
        trace("deliver_to_wallet", "error", str(delivered.get("error")))
        return record("failed")
    trace("deliver_to_wallet", "stubbed", str(delivered.get("external_reference_id", "")))

    return record(
        "completed",
        {
            "recipient_profile_id": profile_id,
            "issued_ref": issued.get("external_reference_id"),
            "delivery": delivered.get("result"),
        },
    )
