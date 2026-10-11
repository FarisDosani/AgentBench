from featureflags import FeatureFlagService, JsonFlagStorage, parse_flags


def test_parser_handles_whitespace_and_comments() -> None:
    assert parse_flags(" # defaults\n search = on \nexport=off") == {
        "search": True,
        "export": False,
    }


def test_service_updates_multiple_known_flags(tmp_path) -> None:
    storage = JsonFlagStorage(tmp_path / "flags.json")
    service = FeatureFlagService(storage, {"search": False, "export": False})
    assert service.update_many({"search": True, "export": True}) == {
        "search": True,
        "export": True,
    }
