from __future__ import annotations

import logging
import shlex
import tempfile
from pathlib import Path
from typing import Protocol

import discord
from discord import app_commands
from discord.ext import commands

from config import Settings
from database import Database
from deepseek_client import DeepSeekClient
from exceptions import BotError, InvalidRepositoryUrlError
from github_client import GitHubClient
from rate_limiter import RateLimiter
from review_service import ReviewService
from utils import chunk_text


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

DISCORD_MESSAGE_LIMIT = 2000
ATTACHMENT_THRESHOLD = 5500

REPOSITORY_URL_HINT = (
    "⚠️ Неверная ссылка на GitHub.\n"
    "Укажите корень репозитория, например: `https://github.com/owner/repository`"
)
FOCUS_HINT = "⚠️ Параметр `--focus` должен быть `security` или `performance`."
VALID_FOCUS_MODES = {"security", "performance"}


class SupportsReviewService(Protocol):
    review_service: ReviewService
    rate_limiter: RateLimiter


class CodeReviewBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix=settings.command_prefix, intents=intents)
        self.settings = settings
        self.database = Database(settings.database_path)
        self.rate_limiter = RateLimiter(settings.rate_limit_seconds)
        self.review_service = ReviewService(
            GitHubClient(settings.github_token),
            DeepSeekClient(
                settings.deepseek_api_key,
                settings.deepseek_endpoint,
                settings.deepseek_model,
            ),
            self.database,
            self.rate_limiter,
            settings.max_code_files,
        )

    async def setup_hook(self) -> None:
        await self.database.initialize()
        self.add_command(prefix_review)
        self.add_command(prefix_stats)
        self.tree.add_command(slash_review)
        self.tree.add_command(slash_stats)

        if self.settings.discord_guild_id is not None:
            guild = discord.Object(id=self.settings.discord_guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info(
                "Synchronized %s Discord slash command(s) to guild %s",
                len(synced),
                self.settings.discord_guild_id,
            )
            return

        synced = await self.tree.sync()
        logger.info("Synchronized %s global Discord slash command(s)", len(synced))

    async def on_ready(self) -> None:
        logger.info("Discord bot is ready as %s", self.user)

    async def on_command_error(
        self,
        context: commands.Context[commands.Bot],
        error: commands.CommandError,
    ) -> None:
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await context.reply(REPOSITORY_URL_HINT, mention_author=False)
            return
        if isinstance(error, commands.BadArgument):
            await context.reply(REPOSITORY_URL_HINT, mention_author=False)
            return

        logger.exception("Unhandled command error", exc_info=error)
        await context.reply(
            "⚠️ Произошла внутренняя ошибка. Попробуйте еще раз позже.",
            mention_author=False,
        )


def _attachment_path(identifier: int) -> Path:
    handle = tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        prefix=f"review_report_{identifier}_",
        suffix=".txt",
    )
    handle.close()
    return Path(handle.name)


async def send_chunked_response(
    destination: commands.Context[commands.Bot],
    content: str,
) -> None:
    if len(content) > ATTACHMENT_THRESHOLD:
        path = _attachment_path(destination.message.id)
        path.write_text(content, encoding="utf-8")
        try:
            await destination.reply(
                "📎 Отчет получился слишком длинным для Discord, поэтому я прикрепил его файлом.",
                file=discord.File(path, filename="code_review_report.txt"),
                mention_author=False,
            )
        finally:
            path.unlink(missing_ok=True)
        return

    chunks = chunk_text(content, limit=DISCORD_MESSAGE_LIMIT)
    for index, chunk in enumerate(chunks):
        if index == 0:
            await destination.reply(chunk, mention_author=False)
        else:
            await destination.send(chunk)


async def send_interaction_response(
    interaction: discord.Interaction[SupportsReviewService],
    content: str,
) -> None:
    if len(content) > ATTACHMENT_THRESHOLD:
        path = _attachment_path(interaction.id)
        path.write_text(content, encoding="utf-8")
        try:
            await interaction.followup.send(
                "📎 Отчет получился слишком длинным для Discord, поэтому я прикрепил его файлом.",
                file=discord.File(path, filename="code_review_report.txt"),
            )
        finally:
            path.unlink(missing_ok=True)
        return

    chunks = chunk_text(content, limit=DISCORD_MESSAGE_LIMIT)
    for chunk in chunks:
        await interaction.followup.send(chunk)


def _parse_prefix_review_args(arguments: str | None) -> tuple[str, str | None]:
    if not arguments:
        raise InvalidRepositoryUrlError()

    try:
        tokens = shlex.split(arguments)
    except ValueError as exc:
        raise commands.BadArgument(REPOSITORY_URL_HINT) from exc

    if not tokens:
        raise InvalidRepositoryUrlError()

    github_url = tokens[0]
    focus_mode: str | None = None
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token == "--focus":
            index += 1
            if index >= len(tokens):
                raise commands.BadArgument(FOCUS_HINT)
            focus_mode = tokens[index].lower()
        elif token.startswith("--focus="):
            focus_mode = token.split("=", 1)[1].lower()
        else:
            raise commands.BadArgument(FOCUS_HINT)
        index += 1

    if focus_mode is not None and focus_mode not in VALID_FOCUS_MODES:
        raise commands.BadArgument(FOCUS_HINT)
    return github_url, focus_mode


def _client_with_service(client: discord.Client) -> SupportsReviewService:
    return client  # type: ignore[return-value]


async def _send_bot_error_context(
    context: commands.Context[commands.Bot],
    error: BotError,
) -> None:
    await context.reply(error.user_message, mention_author=False)


async def _send_bot_error_interaction(
    interaction: discord.Interaction[SupportsReviewService],
    error: BotError,
) -> None:
    await interaction.followup.send(error.user_message)


@commands.command(name="review")
async def prefix_review(
    context: commands.Context[commands.Bot],
    *,
    arguments: str | None = None,
) -> None:
    try:
        github_url, focus_mode = _parse_prefix_review_args(arguments)
    except InvalidRepositoryUrlError:
        await context.reply(REPOSITORY_URL_HINT, mention_author=False)
        return
    except commands.BadArgument as exc:
        await context.reply(str(exc), mention_author=False)
        return

    bot = _client_with_service(context.bot)
    async with context.typing():
        try:
            review = await bot.review_service.create_review(
                context.author.id,
                str(context.author),
                github_url,
                focus_mode,
            )
        except InvalidRepositoryUrlError:
            await context.reply(REPOSITORY_URL_HINT, mention_author=False)
            return
        except BotError as exc:
            await _send_bot_error_context(context, exc)
            return
        await send_chunked_response(context, review)


@commands.command(name="stats")
async def prefix_stats(context: commands.Context[commands.Bot]) -> None:
    bot = _client_with_service(context.bot)
    try:
        stats = await bot.review_service.get_stats(context.author.id)
    except BotError as exc:
        await _send_bot_error_context(context, exc)
        return
    await send_chunked_response(context, stats)


@app_commands.command(name="review", description="Проверить GitHub-репозиторий через DeepSeek.")
@app_commands.describe(
    github_url="Ссылка на GitHub-репозиторий, например https://github.com/owner/repository",
    focus="Дополнительный фокус ревью",
)
@app_commands.choices(
    focus=[
        app_commands.Choice(name="Безопасность", value="security"),
        app_commands.Choice(name="Производительность", value="performance"),
    ]
)
async def slash_review(
    interaction: discord.Interaction[SupportsReviewService],
    github_url: str,
    focus: app_commands.Choice[str] | None = None,
) -> None:
    await interaction.response.defer(thinking=True)
    client = _client_with_service(interaction.client)
    focus_mode = focus.value if focus else None

    try:
        review = await client.review_service.create_review(
            interaction.user.id,
            str(interaction.user),
            github_url,
            focus_mode,
        )
    except InvalidRepositoryUrlError:
        await interaction.followup.send(REPOSITORY_URL_HINT)
        return
    except BotError as exc:
        await _send_bot_error_interaction(interaction, exc)
        return

    await send_interaction_response(interaction, review)


@app_commands.command(name="stats", description="Показать вашу статистику ревью.")
async def slash_stats(interaction: discord.Interaction[SupportsReviewService]) -> None:
    await interaction.response.defer(thinking=True)
    client = _client_with_service(interaction.client)
    try:
        stats = await client.review_service.get_stats(interaction.user.id)
    except BotError as exc:
        await _send_bot_error_interaction(interaction, exc)
        return

    await send_interaction_response(interaction, stats)


async def run_bot() -> None:
    settings = Settings()
    bot = CodeReviewBot(settings)
    await bot.start(settings.discord_token)


def main() -> None:
    import asyncio

    asyncio.run(run_bot())
