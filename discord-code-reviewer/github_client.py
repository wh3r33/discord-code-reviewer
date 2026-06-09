import logging
from typing import Any
from urllib.parse import quote

import httpx

from exceptions import GitHubApiError, PrivateRepositoryError, RepositoryNotFoundError
from utils import is_code_file


logger = logging.getLogger(__name__)


class GitHubClient:
    def __init__(self, token: str | None) -> None:
        self._base_url = "https://api.github.com"
        self._headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "discord-ai-code-reviewer",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    async def fetch_repository_code_files(
        self,
        owner: str,
        repository: str,
        max_files: int,
    ) -> list[dict[str, str]]:
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                repository_data = await self._get_repository(client, owner, repository)
                if repository_data.get("private"):
                    raise PrivateRepositoryError()

                default_branch = repository_data.get("default_branch")
                if not isinstance(default_branch, str) or not default_branch:
                    raise GitHubApiError()

                tree = await self._get_tree(client, owner, repository, default_branch)
                code_paths = [
                    item["path"]
                    for item in tree
                    if item.get("type") == "blob"
                    and isinstance(item.get("path"), str)
                    and is_code_file(item["path"])
                ]

                if len(code_paths) > max_files:
                    from exceptions import RepositoryTooLargeError

                    raise RepositoryTooLargeError()

                files: list[dict[str, str]] = []
                for path in code_paths:
                    content = await self._get_file_content(client, owner, repository, path)
                    files.append({"path": path, "content": content})
                return files
        except httpx.HTTPError as exc:
            logger.warning("GitHub request failed: %s", exc)
            raise GitHubApiError() from exc

    async def _get_repository(
        self,
        client: httpx.AsyncClient,
        owner: str,
        repository: str,
    ) -> dict[str, Any]:
        response = await client.get(
            f"{self._base_url}/repos/{owner}/{repository}",
            headers=self._headers,
        )
        if response.status_code == 404:
            raise RepositoryNotFoundError()
        if response.status_code in (401, 403):
            raise PrivateRepositoryError()
        if response.status_code >= 400:
            logger.warning("GitHub repository request failed: status=%s", response.status_code)
            raise GitHubApiError()
        try:
            data = response.json()
        except ValueError as exc:
            raise GitHubApiError() from exc
        if not isinstance(data, dict):
            raise GitHubApiError()
        return data

    async def _get_tree(
        self,
        client: httpx.AsyncClient,
        owner: str,
        repository: str,
        branch: str,
    ) -> list[dict[str, Any]]:
        encoded_branch = quote(branch, safe="")
        response = await client.get(
            f"{self._base_url}/repos/{owner}/{repository}/git/trees/{encoded_branch}",
            params={"recursive": "1"},
            headers=self._headers,
        )
        if response.status_code == 404:
            raise RepositoryNotFoundError()
        if response.status_code in (401, 403):
            raise PrivateRepositoryError()
        if response.status_code >= 400:
            logger.warning("GitHub tree request failed: status=%s", response.status_code)
            raise GitHubApiError()
        try:
            data = response.json()
        except ValueError as exc:
            raise GitHubApiError() from exc
        tree = data.get("tree") if isinstance(data, dict) else None
        if not isinstance(tree, list):
            raise GitHubApiError()
        return tree

    async def _get_file_content(
        self,
        client: httpx.AsyncClient,
        owner: str,
        repository: str,
        path: str,
    ) -> str:
        headers = {**self._headers, "Accept": "application/vnd.github.raw"}
        encoded_path = quote(path, safe="/")
        response = await client.get(
            f"{self._base_url}/repos/{owner}/{repository}/contents/{encoded_path}",
            headers=headers,
        )
        if response.status_code == 404:
            raise RepositoryNotFoundError()
        if response.status_code in (401, 403):
            raise PrivateRepositoryError()
        if response.status_code >= 400:
            logger.warning(
                "GitHub file content request failed: path=%s status=%s",
                path,
                response.status_code,
            )
            raise GitHubApiError()
        return response.text
