from arithmetic import add


def test_adds_negative_values() -> None:
    assert add(-8, -5) == -13


def test_adds_mixed_floats() -> None:
    assert add(-1.5, 2.25) == 0.75


def test_zero_is_identity() -> None:
    assert add(0, 19) == 19
