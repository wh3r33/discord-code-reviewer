import re
from datetime import datetime, timezone

from exceptions import InvalidRepositoryUrlError


ALLOWED_EXTENSIONS = (".py", ".js", ".ts", ".html", ".css", ".go", ".rs")
MAX_DISCORD_MESSAGE_LENGTH = 2000
GITHUB_REPOSITORY_URL_RE = re.compile(
    r"^"
    r"(?:https?://)?"
    r"(?:www\.)?"
    r"github\.com/"
    r"(?P<owner>[A-Za-z0-9_.-]+)"
    r"/"
    r"(?P<repository>[A-Za-z0-9_.-]+)"
    r"(?:\.git)?"
    r"/?"
    r"(?:[?#].*)?"
    r"$",
    re.IGNORECASE,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_github_url(url: str) -> tuple[str, str]:
    normalized_url = url.strip()
    match = GITHUB_REPOSITORY_URL_RE.fullmatch(normalized_url)
    if not match:
        raise InvalidRepositoryUrlError()

    owner = match.group("owner")
    repository = match.group("repository")
    if not owner or not repository:
        raise InvalidRepositoryUrlError()
    return owner, repository.removesuffix(".git")


def is_code_file(path: str) -> bool:
    return path.lower().endswith(ALLOWED_EXTENSIONS)


def format_repository_name(owner: str, repository: str) -> str:
    return f"{owner}/{repository}"


def _is_code_fence_line(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith("```")


def _close_chunk(chunk: str, in_code_block: bool, limit: int) -> str:
    if not chunk:
        return chunk
    if in_code_block and not chunk.endswith("```"):
        if len(chunk) + 4 <= limit:
            return f"{chunk}\n```"
    return chunk


def chunk_text(text: str, limit: int = MAX_DISCORD_MESSAGE_LENGTH) -> list[str]:
    if limit < 32:
        raise ValueError("Discord chunk limit is too small to split safely.")
    if not text:
        return [""]
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    in_code_block = False
    opening_fence = ""

    for line in text.splitlines(keepends=True):
        while line:
            if not current and in_code_block and opening_fence:
                current = opening_fence

            safety_margin = 4 if in_code_block else 0
            effective_limit = limit - safety_margin
            available = effective_limit - len(current)

            if available <= 0:
                chunks.append(_close_chunk(current, in_code_block, limit))
                current = ""
                continue

            if len(line) > available:
                current += line[:available]
                line = line[available:]
                chunks.append(_close_chunk(current, in_code_block, limit))
                current = ""
                continue

            current += line
            if _is_code_fence_line(line):
                if in_code_block:
                    in_code_block = False
                    opening_fence = ""
                else:
                    in_code_block = True
                    opening_fence = line
            line = ""

    if current:
        chunks.append(_close_chunk(current, in_code_block, limit))

    return [chunk for chunk in chunks if chunk]
