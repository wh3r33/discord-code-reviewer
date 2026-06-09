import logging

from database import Database
from deepseek_client import DeepSeekClient
from github_client import GitHubClient
from rate_limiter import RateLimiter
from utils import format_repository_name, parse_github_url


logger = logging.getLogger(__name__)


class ReviewService:
    def __init__(
        self,
        github_client: GitHubClient,
        deepseek_client: DeepSeekClient,
        database: Database,
        rate_limiter: RateLimiter,
        max_code_files: int,
    ) -> None:
        self._github_client = github_client
        self._deepseek_client = deepseek_client
        self._database = database
        self._rate_limiter = rate_limiter
        self._max_code_files = max_code_files

    async def create_review(
        self,
        discord_user_id: int,
        discord_username: str,
        repository_url: str,
        focus_mode: str | None,
    ) -> str:
        self._rate_limiter.validate(discord_user_id)
        owner, repository = parse_github_url(repository_url)
        repository_name = format_repository_name(owner, repository)

        logger.info(
            "Review requested: user_id=%s username=%s repository=%s focus=%s",
            discord_user_id,
            discord_username,
            repository_name,
            focus_mode or "default",
        )
        files = await self._github_client.fetch_repository_code_files(
            owner,
            repository,
            self._max_code_files,
        )
        prompt = self._build_prompt(repository_name, files, focus_mode)
        review = await self._deepseek_client.review_code(prompt)
        await self._database.log_review(
            discord_user_id,
            discord_username,
            repository_name,
            focus_mode,
        )
        self._rate_limiter.record(discord_user_id)
        return self._format_review(repository_name, focus_mode, review)

    async def get_stats(self, discord_user_id: int) -> str:
        stats = await self._database.get_user_stats(discord_user_id)
        last_review = stats["last_review_date"] or "Пока нет ревью"
        return (
            "## 📊 Статистика ревью\n\n"
            f"**Всего ревью:** `{stats['total_reviews']}`\n"
            f"**Проверено репозиториев:** `{stats['repositories_reviewed']}`\n"
            f"**Последнее ревью:** `{last_review}`"
        )

    def _build_prompt(
        self,
        repository_name: str,
        files: list[dict[str, str]],
        focus_mode: str | None,
    ) -> str:
        focus_instruction = self._focus_instruction(focus_mode)
        file_blocks = []
        total_chars = 0
        max_total_chars = 120_000

        for file in files:
            content = file["content"]
            remaining = max_total_chars - total_chars
            if remaining <= 0:
                break
            if len(content) > remaining:
                content = content[:remaining]
            total_chars += len(content)
            file_blocks.append(
                f"FILE: {file['path']}\n```text\n{content}\n```"
            )

        if not file_blocks:
            file_blocks.append("Поддерживаемые файлы кода не найдены.")

        return (
            f"Проведи code review GitHub-репозитория `{repository_name}`.\n"
            "Ответ должен быть полностью на русском языке.\n"
            "Используй красивый Discord Markdown без таблиц: заголовки, разделители, "
            "жирные подписи, короткие списки и inline code.\n"
            "Пиши профессионально, ясно и без воды.\n"
            "По возможности указывай конкретные файлы.\n"
            "Сортируй проблемы по приоритету строго так: ВЫСОКИЙ, СРЕДНИЙ, НИЗКИЙ.\n"
            f"{focus_instruction}\n\n"
            "Обязательный формат ответа:\n\n"
            "## 📌 Обзор проекта\n"
            "**Репозиторий:** `<owner/repository>`\n"
            "**Назначение:** <кратко, что делает проект>\n"
            "**Общая оценка:** <короткий вывод>\n\n"
            "## 🧭 Оценки\n"
            "- **Архитектура:** `<1-10>` — <причина>\n"
            "- **Качество кода:** `<1-10>` — <причина>\n"
            "- **Поддерживаемость:** `<1-10>` — <причина>\n"
            "- **Безопасность:** `<1-10>` — <причина>\n"
            "- **Тестирование:** `<1-10>` — <причина>\n\n"
            "## ✅ Сильные стороны\n"
            "- **<сильная сторона>** — <доказательство и эффект>\n\n"
            "## ⚠️ Проблемы по приоритету\n"
            "- **ВЫСОКИЙ:** <проблема>. **Где:** `<файл или область>`. **Риск:** <эффект>\n"
            "- **СРЕДНИЙ:** <проблема>. **Где:** `<файл или область>`. **Риск:** <эффект>\n"
            "- **НИЗКИЙ:** <проблема>. **Где:** `<файл или область>`. **Риск:** <эффект>\n\n"
            "## 🛠️ Рекомендации\n"
            "- **ВЫСОКИЙ:** <что сделать>. **Цель:** `<файл или область>`. **Результат:** <ожидаемый эффект>\n"
            "- **СРЕДНИЙ:** <что сделать>. **Цель:** `<файл или область>`. **Результат:** <ожидаемый эффект>\n\n"
            "## 🧪 Тесты\n"
            "**Наблюдение:** <что видно по тестам>\n"
            "**Что добавить:** <рекомендация>\n\n"
            "## 🏁 Вердикт\n"
            "**Рейтинг:** `<1-10>`\n"
            "**Решение:** `<Можно использовать / Нужна доработка / Высокий риск>`\n"
            "**Итог:** <финальный короткий вывод>\n\n"
            "Файлы репозитория:\n\n"
            + "\n\n".join(file_blocks)
        )

    @staticmethod
    def _focus_instruction(focus_mode: str | None) -> str:
        if focus_mode == "security":
            return (
                "Сфокусируйся на уязвимостях, аутентификации, авторизации, утечках "
                "секретов и небезопасных паттернах кода."
            )
        if focus_mode == "performance":
            return (
                "Сфокусируйся на узких местах производительности, неэффективных "
                "алгоритмах, лишних API-вызовах и расходе памяти."
            )
        return (
            "Проверь архитектуру, качество кода, поддерживаемость, баги, безопасность, "
            "производительность и дай оценку по шкале от 1 до 10."
        )

    @staticmethod
    def _format_review(repository_name: str, focus_mode: str | None, review: str) -> str:
        mode_labels = {
            "security": "безопасность",
            "performance": "производительность",
        }
        mode = mode_labels.get(focus_mode or "", "общее ревью")
        return (
            "# 🔍 Ревью кода\n\n"
            f"**Репозиторий:** `{repository_name}`\n"
            f"**Режим:** `{mode}`\n\n"
            "---\n\n"
            f"{review}"
        )
