from string_utils import normalize_username


def test_trims_surrounding_whitespace() -> None:
    assert normalize_username("  Alice\t") == "alice"


def test_preserves_internal_whitespace() -> None:
    assert normalize_username("  ALICE  SMITH  ") == "alice  smith"


def test_empty_input_remains_empty() -> None:
    assert normalize_username("   ") == ""
