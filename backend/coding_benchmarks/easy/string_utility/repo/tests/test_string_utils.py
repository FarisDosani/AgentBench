from string_utils import display_name, normalize_username


def test_normalizes_mixed_case() -> None:
    assert normalize_username("Alice") == "alice"


def test_display_name_is_unchanged() -> None:
    assert display_name("  ada lovelace ") == "Ada Lovelace"
