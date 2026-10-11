from arithmetic import add, multiply


def test_adds_positive_integers() -> None:
    assert add(17, 25) == 42


def test_multiply_remains_available() -> None:
    assert multiply(6, 7) == 42
