from account.models import is_valid_username, normalize_username


class AccountService:
    def __init__(self) -> None:
        self._usernames: set[str] = set()

    def register(self, username: str) -> str:
        if not is_valid_username(username):
            raise ValueError("invalid username")
        normalized = normalize_username(username)
        if normalized in self._usernames:
            raise ValueError("duplicate username")
        self._usernames.add(normalized)
        return normalized
