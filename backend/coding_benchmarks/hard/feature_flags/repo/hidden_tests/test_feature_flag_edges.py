import pytest

from featureflags import FeatureFlagService, JsonFlagStorage, parse_flags


def test_parser_rejects_invalid_values_duplicates_and_malformed_lines() -> None:
    with pytest.raises(ValueError):
        parse_flags("search=maybe")
    with pytest.raises(ValueError):
        parse_flags("search=on\nsearch=off")
    with pytest.raises(ValueError):
        parse_flags("missing separator")


def test_batch_update_is_atomic_when_unknown_flag_is_present(tmp_path) -> None:
    storage = JsonFlagStorage(tmp_path / "flags.json")
    service = FeatureFlagService(storage, {"search": False, "export": False})
    with pytest.raises(ValueError):
        service.update_many({"search": True, "unknown": True})
    assert storage.load() == {"search": False, "export": False}


def test_batch_update_rejects_non_boolean_and_preserves_unspecified_flags(tmp_path) -> None:
    storage = JsonFlagStorage(tmp_path / "flags.json")
    service = FeatureFlagService(storage, {"search": False, "export": True})
    with pytest.raises(ValueError):
        service.update_many({"search": "yes"})  # type: ignore[dict-item]
    assert storage.load() == {"search": False, "export": True}
    assert service.update_many({"search": True}) == {"search": True, "export": True}
