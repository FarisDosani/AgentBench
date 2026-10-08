def parse_definitions(text: str) -> dict[str, list[str]]:
    definitions: dict[str, list[str]] = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        name, dependencies = line.split(":", 1)
        definitions[name] = dependencies.split(",") if dependencies else []
    return definitions
