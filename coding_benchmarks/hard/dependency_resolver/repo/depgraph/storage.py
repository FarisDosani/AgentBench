class PackageRegistry:
    def __init__(self) -> None:
        self._packages: dict[str, list[str]] = {}

    def replace(self, packages: dict[str, list[str]]) -> None:
        self._packages = {name: list(dependencies) for name, dependencies in packages.items()}

    def contains(self, name: str) -> bool:
        return name in self._packages

    def dependencies_for(self, name: str) -> list[str]:
        return list(self._packages[name])
