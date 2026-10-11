import pytest

from account import AccountService


def test_surrounding_whitespace_is_normalized_before_validation() -> None:
    assert AccountService().register("  Alice_7  ") == "alice_7"


def test_invalid_characters_and_long_names_are_rejected() -> None:
    service = AccountService()
    for username in ["bad-name", "has space", "x" * 21]:
        with pytest.raises(ValueError):
            service.register(username)


def test_duplicates_are_case_insensitive() -> None:
    service = AccountService()
    service.register("Alice_7")
    with pytest.raises(ValueError):
        service.register(" alice_7 ")
