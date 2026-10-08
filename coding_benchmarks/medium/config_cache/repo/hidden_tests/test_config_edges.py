import pytest

from configlib import ConfigService, parse_config


def test_comments_blank_lines_and_indented_comments_are_ignored() -> None:
    assert parse_config("\n # comment\nvalue = yes\n") == {"value": "yes"}


def test_malformed_and_duplicate_entries_are_rejected() -> None:
    with pytest.raises(ValueError):
        parse_config("missing separator")
    with pytest.raises(ValueError):
        parse_config("key=one\nkey=two")


def test_cache_invalidates_when_file_contents_change(tmp_path) -> None:
    path = tmp_path / "app.conf"
    path.write_text("mode=old", encoding="utf-8")
    service = ConfigService()
    first = service.load(path)
    path.write_text("mode=new", encoding="utf-8")
    second = service.load(path)
    assert second == {"mode": "new"}
    assert second is not first
