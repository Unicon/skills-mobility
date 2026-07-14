from typing import Any

import pytest
from delivery_targets.catalog_store import CatalogError, CatalogStore

store = CatalogStore()  # defaults to the packaged catalog

_EXPECTED_TARGET_IDS = {"learncard_issuer", "learncard_wallet", "smart_resume"}


def test_load_targets_returns_all_three_entries() -> None:
    catalog = store.load_targets()
    assert len(catalog) == 3
    ids = {entry["delivery_target"] for entry in catalog}
    assert ids == _EXPECTED_TARGET_IDS


def test_target_ids_returns_correct_set() -> None:
    assert store.target_ids() == _EXPECTED_TARGET_IDS


def test_each_entry_has_required_fields() -> None:
    for entry in store.load_targets():
        assert "delivery_target" in entry
        assert "delivery_action" in entry
        assert "description" in entry
        assert "eligibility_notes" in entry


def test_learncard_issuer_has_correct_action() -> None:
    catalog = store.load_targets()
    issuer = next(e for e in catalog if e["delivery_target"] == "learncard_issuer")
    assert issuer["delivery_action"] == "issue_learncard_badge"


def test_missing_catalog_dir_raises_catalog_error(tmp_path: Any) -> None:
    bad_store = CatalogStore(base_dir=tmp_path / "nonexistent")
    with pytest.raises(CatalogError):
        bad_store.load_targets()
