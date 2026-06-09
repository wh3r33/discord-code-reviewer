import asyncio
import sqlite3
from pathlib import Path
from typing import Any


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self._initialize_sync)

    async def log_review(
        self,
        discord_user_id: int,
        discord_username: str,
        repository: str,
        focus_mode: str | None,
    ) -> None:
        async with self._lock:
            await asyncio.to_thread(
                self._log_review_sync,
                discord_user_id,
                discord_username,
                repository,
                focus_mode,
            )

    async def get_user_stats(self, discord_user_id: int) -> dict[str, Any]:
        async with self._lock:
            return await asyncio.to_thread(self._get_user_stats_sync, discord_user_id)

    def _connect(self) -> sqlite3.Connection:
        if self.path.parent != Path("."):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_sync(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    discord_user_id INTEGER PRIMARY KEY,
                    discord_username TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    discord_user_id INTEGER NOT NULL,
                    discord_username TEXT NOT NULL,
                    repository TEXT NOT NULL,
                    focus_mode TEXT,
                    FOREIGN KEY (discord_user_id) REFERENCES users(discord_user_id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_reviews_user_id ON reviews(discord_user_id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_reviews_timestamp ON reviews(timestamp)"
            )

    def _log_review_sync(
        self,
        discord_user_id: int,
        discord_username: str,
        repository: str,
        focus_mode: str | None,
    ) -> None:
        from utils import utc_now

        timestamp = utc_now().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO users (
                    discord_user_id,
                    discord_username,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(discord_user_id) DO UPDATE SET
                    discord_username = excluded.discord_username,
                    updated_at = excluded.updated_at
                """,
                (discord_user_id, discord_username, timestamp, timestamp),
            )
            connection.execute(
                """
                INSERT INTO reviews (
                    timestamp,
                    discord_user_id,
                    discord_username,
                    repository,
                    focus_mode
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (timestamp, discord_user_id, discord_username, repository, focus_mode),
            )

    def _get_user_stats_sync(self, discord_user_id: int) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    COUNT(*) AS total_reviews,
                    COUNT(DISTINCT repository) AS repositories_reviewed,
                    MAX(timestamp) AS last_review_date
                FROM reviews
                WHERE discord_user_id = ?
                """,
                (discord_user_id,),
            ).fetchone()
        return {
            "total_reviews": row["total_reviews"] or 0,
            "repositories_reviewed": row["repositories_reviewed"] or 0,
            "last_review_date": row["last_review_date"],
        }
