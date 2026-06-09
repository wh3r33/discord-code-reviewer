import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


class Settings:
    discord_token: str
    command_prefix: str
    deepseek_api_key: str
    github_token: str | None
    database_path: Path
    max_code_files: int
    rate_limit_seconds: int
    deepseek_endpoint: str
    deepseek_model: str
    discord_guild_id: int | None

    def __init__(self) -> None:
        self.discord_token = self._required("DISCORD_TOKEN")
        self.command_prefix = self._optional("COMMAND_PREFIX", "!")
        self.deepseek_api_key = self._required("DEEPSEEK_API_KEY")
        self.github_token = self._optional("GITHUB_TOKEN") or None
        self.database_path = Path(self._optional("DATABASE_PATH", "reviews.db"))
        self.max_code_files = self._positive_int("MAX_CODE_FILES", 30)
        self.rate_limit_seconds = self._positive_int("RATE_LIMIT_SECONDS", 300)
        self.deepseek_endpoint = self._optional(
            "DEEPSEEK_ENDPOINT",
            "https://api.deepseek.com/chat/completions",
        )
        self.deepseek_model = self._optional("DEEPSEEK_MODEL", "deepseek-chat")
        self.discord_guild_id = self._optional_int("DISCORD_GUILD_ID")

    @staticmethod
    def _required(name: str) -> str:
        value = os.getenv(name, "").strip()
        if not value:
            raise RuntimeError(f"Missing required environment variable: {name}")
        return value

    @staticmethod
    def _optional(name: str, default: str = "") -> str:
        return os.getenv(name, default).strip()

    @staticmethod
    def _positive_int(name: str, default: int) -> int:
        value = os.getenv(name)
        if value is None or not value.strip():
            return default
        try:
            parsed = int(value)
        except ValueError as exc:
            raise RuntimeError(f"{name} must be an integer.") from exc
        if parsed <= 0:
            raise RuntimeError(f"{name} must be greater than zero.")
        return parsed

    @staticmethod
    def _optional_int(name: str) -> int | None:
        value = os.getenv(name)
        if value is None or not value.strip():
            return None
        try:
            parsed = int(value)
        except ValueError as exc:
            raise RuntimeError(f"{name} must be an integer.") from exc
        if parsed <= 0:
            raise RuntimeError(f"{name} must be greater than zero.")
        return parsed
