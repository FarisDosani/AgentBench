from configlib import ConfigService, parse_config


def test_parser_trims_keys_and_values() -> None:
    assert parse_config(" host = localhost \nport=8000") == {
        "host": "localhost",
        "port": "8000",
    }


def test_service_reuses_unchanged_cached_object(tmp_path) -> None:
    path = tmp_path / "app.conf"
    path.write_text("mode=test", encoding="utf-8")
    service = ConfigService()
    assert service.load(path) is service.load(path)
