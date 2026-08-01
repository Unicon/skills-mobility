from pathlib import Path

import pytest
from field_mapping.catalog_store import CatalogNotFoundError, CatalogStore
from field_mapping.contracts import DeliveryTarget, TransformationType

store = CatalogStore()  # defaults to the packaged catalogs

_SKILL_MASTERED_RESOURCES = {
    "outcome",
    "assignment",
    "rubric",
    "module_context",
    "module_pages",
    "canvas_user",
    "submission",
}


def test_resolve_source_catalogs_for_fetch_profile() -> None:
    cats = store.resolve_source_catalogs(
        source_system="mock_lms", fetch_profile_id="skill_mastered.v1"
    )
    assert set(cats) == _SKILL_MASTERED_RESOURCES
    assert cats["outcome"]["x-resource-schema-id"] == "outcome"


def test_resolve_target_catalog_by_target_and_transformation_type() -> None:
    issuer = store.resolve_target(
        transformation_type=TransformationType.ISSUER_PAYLOAD,
        delivery_target=DeliveryTarget.LEARNCARD_ISSUER,
    )
    assert issuer["x-transformation-type"] == "issuer_payload"

    wallet = store.resolve_target(
        transformation_type=TransformationType.WALLET_PAYLOAD,
        delivery_target=DeliveryTarget.LEARNCARD_WALLET,
    )
    assert wallet["x-transformation-type"] == "wallet_payload"

    smartresume = store.resolve_target(
        transformation_type=TransformationType.WALLET_PAYLOAD,
        delivery_target=DeliveryTarget.SMART_RESUME,
    )
    assert smartresume["x-delivery-target"] == "smart_resume"
    assert smartresume["required"] == ["recipient", "credentials"]


def test_resolve_credential_template_target() -> None:
    # credential_template is keyed by transformation_type alone (no delivery_target, ADR-0017).
    ct = store.resolve_target(
        transformation_type=TransformationType.CREDENTIAL_TEMPLATE, delivery_target=None
    )
    assert ct["x-transformation-type"] == "credential_template"


def test_unknown_fetch_profile_or_target_is_a_typed_error(tmp_path: Path) -> None:
    with pytest.raises(CatalogNotFoundError):
        store.resolve_fetch_profile(source_system="mock_lms", fetch_profile_id="nope.v9")

    # A genuinely absent target catalog file raises the file-existence error (not the
    # delivery_target parameter guard). Point at an empty catalogs dir so the test's
    # validity doesn't depend on which real catalogs happen to be unimplemented today.
    empty = CatalogStore(base_dir=tmp_path)
    with pytest.raises(CatalogNotFoundError):
        empty.resolve_target(
            transformation_type=TransformationType.ISSUER_PAYLOAD,
            delivery_target=DeliveryTarget.LEARNCARD_ISSUER,
        )
