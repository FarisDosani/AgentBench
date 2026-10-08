from depgraph import DependencyResolver, PackageRegistry, parse_definitions


def test_parses_trimmed_definitions() -> None:
    assert parse_definitions(" app : core, util \ncore:\nutil:") == {
        "app": ["core", "util"],
        "core": [],
        "util": [],
    }


def test_linear_dependencies_are_ordered_before_dependents() -> None:
    registry = PackageRegistry()
    registry.replace({"app": ["service"], "service": ["core"], "core": []})
    assert DependencyResolver(registry).resolve("app") == ["core", "service", "app"]
