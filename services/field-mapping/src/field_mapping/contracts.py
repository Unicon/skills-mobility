"""Request/response contracts for the Field Mapping LLM Decision Service.

Design refs: §4 (transient-payload-first request) and §10 (small response
envelope). The response is exactly the five-key shape the Orchestrator's mapping
seam reads — see ``orchestrator.actions._generate_payload_mapping``.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


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

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "execution_id": "exec_1",
                "event_id": "evt_1",
                "transformation_type": "issuer_payload",
                "source_system": "mock_lms",
                "fetch_profile_id": "skill_mastered.v1",
                "delivery_target": "learncard_issuer",
                "synthesis_allowed": True,
                "source_payloads": {
                    "outcome": {
                        "code": "1.0.0",
                        "display_name": "Demonstrate the sample competency",
                        "description": "Demonstrates mastery of the sample competency.",
                    },
                    "profile_resolution": {
                        "issuer_id": "did:web:issuer.example.com",
                        "recipient_did": "did:web:network.learncard.com:users:learner",
                    },
                },
            }
        },
    )

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
    """§10 response envelope — the Orchestrator seam reads the five core keys;
    ``mapping`` carries the generated JSONata inline so the Transformation Executor
    can run it without a second artifact-store fetch.
    ``requires_synthesis`` is derived, never set independently; build via
    ``succeeded`` / ``failed`` so the §6 permission gate stays self-enforcing."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["succeeded", "failed"]
    mapping_artifact_ref: str | None
    synthesis_request_ref: str | None
    requires_synthesis: bool
    llm_invocation_log_ref: str | None
    mapping: str | None = None

    @classmethod
    def succeeded(
        cls,
        *,
        mapping_artifact_ref: str,
        synthesis_request_ref: str | None,
        llm_invocation_log_ref: str,
        synthesis_allowed: bool,
        placeholder_ids: list[str],
        mapping: str | None = None,
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
            mapping=mapping,
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


# --- Stored artifacts (§2) ---

_CAMEL_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")


def placeholder_id_from_path(target_path: str) -> str:
    """Derive a snake_case ``placeholder_id`` from a target field path (§2).

    Example: ``achievement.description`` -> ``achievement_description``. A leading
    ``credentialSubject`` segment is implicit in the id (the design's own example
    maps ``credentialSubject.achievement.description`` -> ``achievement_description``).
    """
    segments = [s for s in target_path.split(".") if s]
    if segments and segments[0] == "credentialSubject":
        segments = segments[1:]
    return "_".join(_CAMEL_BOUNDARY.sub("_", s).lower() for s in segments)


class MappingArtifact(BaseModel):
    """§2 stored mapping artifact: ready-to-run JSONata for one transformation
    target, plus the ids of any synthesis-backed fields."""

    model_config = ConfigDict(extra="forbid")

    mapping_artifact_schema_version: Literal["v1"] = "v1"
    transformation_type: TransformationType
    source_system: str
    fetch_profile_id: str
    delivery_target: DeliveryTarget | None = None
    target_schema_ref: str
    jsonata: str
    placeholder_ids: list[str] = Field(default_factory=list)


class SynthesisRequestEntry(BaseModel):
    """One placeholder's synthesis instruction. At least one of
    ``source_payload_paths`` / ``source_payloads`` must be present; when both are,
    ``source_payloads`` is the concrete snapshot of the referenced values (§2)."""

    model_config = ConfigDict(extra="forbid")

    placeholder_id: str
    target_path: str
    source_payload_paths: list[str] | None = None
    source_payloads: dict[str, Any] | None = None
    instruction: str

    @model_validator(mode="after")
    def _require_a_source_representation(self) -> Self:
        if not self.source_payload_paths and self.source_payloads is None:
            raise ValueError(
                "synthesis request needs source_payload_paths or a source_payloads snapshot"
            )
        return self


class SynthesisRequestArtifact(BaseModel):
    """§2 stored synthesis-request artifact — what Field Synthesis needs per
    placeholder, kept out of the compact mapping artifact."""

    model_config = ConfigDict(extra="forbid")

    synthesis_request_schema_version: Literal["v1"] = "v1"
    transformation_type: TransformationType
    requests: list[SynthesisRequestEntry]


class MappingGeneration(BaseModel):
    """The structured model output the LLM/replay adapter returns (§7): the JSONata
    mapping body, the synthesis requests for any placeholders, and confidence /
    rationale. ``confidence`` / ``rationale`` are optional here so their absence is
    a validation failure (FR-FM-14), not a parse crash."""

    model_config = ConfigDict(extra="forbid")

    jsonata: str
    placeholder_ids: list[str] = Field(default_factory=list)
    synthesis_requests: list[SynthesisRequestEntry] = Field(default_factory=list)
    confidence: float | None = None
    rationale: str | None = None
