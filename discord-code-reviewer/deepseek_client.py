import logging

import httpx

from exceptions import DeepSeekApiError


logger = logging.getLogger(__name__)


class DeepSeekClient:
    def __init__(self, api_key: str, endpoint: str, model: str) -> None:
        self._api_key = api_key
        self._endpoint = endpoint
        self._model = model

    async def review_code(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ты senior software engineer и проводишь production code review. "
                        "Всегда отвечай на русском языке. Пиши кратко, конкретно и "
                        "практично. Используй красивый Discord Markdown: заголовки, "
                        "жирные подписи, короткие списки и inline code. Эмодзи допустимы "
                        "только как аккуратные маркеры разделов и приоритетов."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 2500,
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            try:
                response = await client.post(self._endpoint, headers=headers, json=payload)
            except httpx.HTTPError as exc:
                logger.warning("DeepSeek request failed: %s", exc)
                raise DeepSeekApiError() from exc

        if response.status_code >= 400:
            logger.warning("DeepSeek API returned status=%s body=%s", response.status_code, response.text[:500])
            raise DeepSeekApiError()

        try:
            data = response.json()
        except ValueError as exc:
            raise DeepSeekApiError() from exc
        choices = data.get("choices") if isinstance(data, dict) else None
        if not isinstance(choices, list) or not choices:
            raise DeepSeekApiError()
        first_choice = choices[0]
        message = first_choice.get("message") if isinstance(first_choice, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise DeepSeekApiError()

        if not content.strip():
            raise DeepSeekApiError()
        return content.strip()
