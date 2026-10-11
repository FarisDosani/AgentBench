import pytest

from account import AccountService


def test_registration_returns_normalized_username() -> None:
    assert AccountService().register("Alice_7") == "alice_7"


def test_short_username_is_rejected() -> None:
    with pytest.raises(ValueError):
        AccountService().register("ab")
