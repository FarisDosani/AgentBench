from featureflags.storage import JsonFlagStorage


class FeatureFlagService:
    def __init__(self, storage: JsonFlagStorage, definitions: dict[str, bool]) -> None:
        self.storage = storage
        self.definitions = dict(definitions)
        if not self.storage.load():
            self.storage.save(self.definitions)

    def update_many(self, updates: dict[str, bool]) -> dict[str, bool]:
        current = self.storage.load()
        for name, enabled in updates.items():
            current[name] = enabled
            self.storage.save(current)
        return current
