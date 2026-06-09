class BotError(Exception):
    user_message: str = "⚠️ Произошла внутренняя ошибка. Попробуйте еще раз позже."


class InvalidRepositoryUrlError(BotError):
    user_message = (
        "⚠️ Неверная ссылка на репозиторий GitHub.\n"
        "Пример: `https://github.com/user/repository`"
    )


class RepositoryNotFoundError(BotError):
    user_message = "🔎 Репозиторий не найден. Проверьте ссылку и доступность проекта."


class PrivateRepositoryError(BotError):
    user_message = "🔒 Нет доступа к репозиторию или он приватный."


class RepositoryTooLargeError(BotError):
    user_message = "📦 В репозитории слишком много файлов кода для безопасного ревью."


class GitHubApiError(BotError):
    user_message = "⚠️ GitHub API не ответил корректно. Попробуйте позже."


class DeepSeekApiError(BotError):
    user_message = "⚠️ Сервис AI-ревью не ответил корректно. Попробуйте позже."


class RateLimitExceededError(BotError):
    user_message = "⏳ Вы недавно запускали ревью. Попробуйте еще раз чуть позже."
