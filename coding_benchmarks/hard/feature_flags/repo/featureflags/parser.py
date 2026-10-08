def parse_flags(text: str) -> dict[str, bool]:
    flags: dict[str, bool] = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        name, value = line.split("=", 1)
        flags[name] = value == "on"
    return flags
