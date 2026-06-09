from datetime import datetime

from exceptions import RateLimitExceededError
from utils import utc_now


class RateLimiter:
    def __init__(self, window_seconds: int) -> None:
        self.window_seconds = window_seconds
        self._last_review_by_user: dict[int, datetime] = {}

    def validate(self, discord_user_id: int) -> None:
        if self.retry_after(discord_user_id) > 0:
            raise RateLimitExceededError()

    def retry_after(self, discord_user_id: int) -> int:
        last_review = self._last_review_by_user.get(discord_user_id)
        if last_review is None:
            return 0
        elapsed = (utc_now() - last_review).total_seconds()
        remaining = self.window_seconds - elapsed
        if remaining <= 0:
            return 0
        return int(remaining) + 1

    def record(self, discord_user_id: int) -> None:
        self._last_review_by_user[discord_user_id] = utc_now()
