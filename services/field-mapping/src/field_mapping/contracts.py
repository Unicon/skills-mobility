"""Request/response contracts for the Field Mapping LLM Decision Service.

Design refs: §4 (transient-payload-first request) and §10 (small response
envelope). The response is exactly the five-key shape the Orchestrator's mapping
seam reads — see ``orchestrator.actions._generate_payload_mapping``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator


class TransformationType(StrEnum):
    """The three transformation phases (ADR-0017)."""

    ISSUER_PAYLOAD = "issuer_payload"
    WALLET_PAYLOAD = "wallet_payload"
    CREDENTIAL_TEMPLATE = "credential_template"


class DeliveryTarget(StrEnum):
    """Downstream delivery targets a mapping can serve."""

    LEARNCARD_ISSUER = "learncard_issuer"
    LEARNCARD_WALLET = "learncard_wallet"
    SMART_RESUME = "smart_resume"


class MappingRequest(BaseModel):
    """§4 request. ``transformation_type`` and ``delivery_target`` are independent
    literals from the Workflow Actions plan — this service derives neither from the
    other. ``delivery_target`` is absent (not null) for ``credential_template``."""

    model_config = ConfigDict(extra="forbid")

    execution_id: str
    event_id: str
    transformation_type: TransformationType
    source_system: str
    fetch_profile_id: str
    delivery_target: DeliveryTarget | None = None
    synthesis_allowed: bool
    source_payloads: dict[str, Any]

    @model_validator(mode="after")
    def _check_delivery_target_presence(self) -> Self:
        # §4 / ADR-0017: credential_template omits delivery_target entirely; the
        # other two phases require it (catalog resolution keys on it).
        if self.transformation_type is TransformationType.CREDENTIAL_TEMPLATE:
            if self.delivery_target is not None:
                raise ValueError("credential_template requests must omit delivery_target")
        elif self.delivery_target is None:
            raise ValueError(f"{self.transformation_type} requests require a delivery_target")
        return self


class MappingResponse(BaseModel):
    """§10 response envelope — exactly the five keys the Orchestrator seam reads.
    ``requires_synthesis`` is derived, never set independently; build via
    ``succeeded`` / ``failed`` so the §6 permission gate stays self-enforcing."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["succeeded", "failed"]
    mapping_artifact_ref: str | None
    synthesis_request_ref: str | None
    requires_synthesis: bool
    llm_invocation_log_ref: str | None

    @classmethod
    def succeeded(
        cls,
        *,
        mapping_artifact_ref: str,
        synthesis_request_ref: str | None,
        llm_invocation_log_ref: str,
        synthesis_allowed: bool,
        placeholder_ids: list[str],
    ) -> Self:
        # §10 derivation — can never be true when the request forbade synthesis,
        # regardless of the placeholders/ref present.
        requires_synthesis = (
            synthesis_allowed and bool(placeholder_ids) and synthesis_request_ref is not None
        )
        return cls(
            status="succeeded",
            mapping_artifact_ref=mapping_artifact_ref,
            synthesis_request_ref=synthesis_request_ref,
            requires_synthesis=requires_synthesis,
            llm_invocation_log_ref=llm_invocation_log_ref,
        )

    @classmethod
    def failed(cls, *, llm_invocation_log_ref: str | None = None) -> Self:
        return cls(
            status="failed",
            mapping_artifact_ref=None,
            synthesis_request_ref=None,
            requires_synthesis=False,
            llm_invocation_log_ref=llm_invocation_log_ref,
        )
