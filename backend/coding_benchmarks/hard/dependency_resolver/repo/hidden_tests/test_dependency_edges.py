import pytest

from depgraph import DependencyResolver, PackageRegistry, parse_definitions


def make_resolver(packages: dict[str, list[str]]) -> DependencyResolver:
    registry = PackageRegistry()
    registry.replace(packages)
    return DependencyResolver(registry)


def test_diamond_dependency_is_emitted_once_and_siblings_are_sorted() -> None:
    resolver = make_resolver(
        {"app": ["zeta", "alpha"], "alpha": ["core"], "zeta": ["core"], "core": []}
    )
    assert resolver.resolve("app") == ["core", "alpha", "zeta", "app"]


def test_cycles_and_missing_packages_raise_value_error() -> None:
    with pytest.raises(ValueError):
        make_resolver({"a": ["b"], "b": ["a"]}).resolve("a")
    with pytest.raises(ValueError):
        make_resolver({"a": ["missing"]}).resolve("a")


def test_parser_rejects_duplicate_and_malformed_definitions() -> None:
    with pytest.raises(ValueError):
        parse_definitions("app:core\napp:util")
    with pytest.raises(ValueError):
        parse_definitions("not a definition")
