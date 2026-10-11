from depgraph.storage import PackageRegistry


class DependencyResolver:
    def __init__(self, registry: PackageRegistry) -> None:
        self.registry = registry

    def resolve(self, package: str) -> list[str]:
        resolved = [package]
        for dependency in self.registry.dependencies_for(package):
            resolved.extend(self.resolve(dependency))
        return resolved
