"""GitHub connector: fetch a user's repositories, languages and READMEs.

Uses the user's stored OAuth token when available (higher rate limit, access to
their own repos); falls back to the unauthenticated public API by username.
Only public repository data is read unless the token carries the `repo` scope.
"""

from __future__ import annotations

import base64
from abc import ABC, abstractmethod

import httpx

from app.connectors.base import GitHubData, RepoData
from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("github")

_API = "https://api.github.com"
MAX_REPOS = 20  # cap detailed fetches (languages + README) per sync


class GitHubClient(ABC):
    @abstractmethod
    async def fetch(self, *, token: str | None, username: str | None) -> GitHubData: ...


class RealGitHubClient(GitHubClient):
    async def fetch(self, *, token: str | None, username: str | None) -> GitHubData:
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=20, headers=headers) as client:
            if token:
                me = (await client.get(f"{_API}/user")).json()
                username = username or me.get("login")
                profile = me
                repos_url = f"{_API}/user/repos"
                params = {"per_page": "100", "sort": "pushed", "affiliation": "owner"}
            else:
                if not username:
                    raise ValueError("A GitHub username is required when not authenticated")
                profile = (await client.get(f"{_API}/users/{username}")).json()
                repos_url = f"{_API}/users/{username}/repos"
                params = {"per_page": "100", "sort": "pushed"}

            repos_raw = (await client.get(repos_url, params=params)).json()
            if not isinstance(repos_raw, list):
                raise ValueError(f"GitHub API error: {repos_raw}")

            # Rank: non-forks first, then by stars, then recency.
            repos_raw.sort(
                key=lambda r: (not r.get("fork", False), r.get("stargazers_count", 0)),
                reverse=True,
            )

            repos: list[RepoData] = []
            for raw in repos_raw[:MAX_REPOS]:
                repo = RepoData(
                    name=raw["name"],
                    full_name=raw["full_name"],
                    description=raw.get("description"),
                    html_url=raw["html_url"],
                    primary_language=raw.get("language"),
                    topics=raw.get("topics", []),
                    stars=raw.get("stargazers_count", 0),
                    is_fork=raw.get("fork", False),
                    pushed_at=raw.get("pushed_at"),
                )
                repo.languages = await self._languages(client, raw["languages_url"])
                repo.readme = await self._readme(client, raw["full_name"])
                repo.commits = await self._commits(client, raw["full_name"], username)
                repos.append(repo)

            return GitHubData(
                username=username or "",
                name=profile.get("name"),
                bio=profile.get("bio"),
                repos=repos,
            )

    async def _languages(self, client: httpx.AsyncClient, url: str) -> list[str]:
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                return list(resp.json().keys())
        except Exception as exc:  # pragma: no cover
            log.warning("github_languages_failed", error=str(exc))
        return []

    async def _commits(
        self, client: httpx.AsyncClient, full_name: str, username: str | None,
    ) -> list[str]:
        try:
            params: dict[str, str] = {"per_page": "30"}
            if username:
                params["author"] = username
            resp = await client.get(f"{_API}/repos/{full_name}/commits", params=params)
            if resp.status_code == 200:
                return [
                    c["commit"]["message"].split("\n")[0]
                    for c in resp.json()
                    if c.get("commit", {}).get("message")
                ]
        except Exception as exc:
            log.warning("github_commits_failed", error=str(exc))
        return []

    async def _readme(self, client: httpx.AsyncClient, full_name: str) -> str | None:
        try:
            resp = await client.get(f"{_API}/repos/{full_name}/readme")
            if resp.status_code == 200:
                content = resp.json().get("content", "")
                return base64.b64decode(content).decode("utf-8", errors="replace")[:8000]
        except Exception as exc:  # pragma: no cover
            log.warning("github_readme_failed", error=str(exc))
        return None


class FakeGitHubClient(GitHubClient):
    """Deterministic data for tests/offline dev."""

    async def fetch(self, *, token: str | None, username: str | None) -> GitHubData:
        uname = username or "octocat"
        return GitHubData(
            username=uname,
            name="Octo Cat",
            bio="Builder of things",
            repos=[
                RepoData(
                    name="rag-search",
                    full_name=f"{uname}/rag-search",
                    description="A retrieval-augmented search engine",
                    html_url=f"https://github.com/{uname}/rag-search",
                    primary_language="Python",
                    languages=["Python", "TypeScript"],
                    topics=["rag", "llm"],
                    stars=42,
                    is_fork=False,
                    readme="# rag-search\nBuilt with FastAPI, LangChain and PostgreSQL.",
                    pushed_at="2026-01-01T00:00:00Z",
                    commits=[
                        "feat: add hybrid search with BM25 + vector retrieval",
                        "fix: handle empty query edge case in ranking",
                        "refactor: extract embedding pipeline into separate module",
                        "test: add integration tests for retrieval endpoint",
                        "ci: add GitHub Actions workflow for pytest",
                    ],
                ),
                RepoData(
                    name="dotfiles",
                    full_name=f"{uname}/dotfiles",
                    description="My configuration",
                    html_url=f"https://github.com/{uname}/dotfiles",
                    primary_language="Shell",
                    languages=["Shell"],
                    stars=3,
                    is_fork=False,
                    readme=None,
                    pushed_at="2025-06-01T00:00:00Z",
                    commits=[
                        "chore: update neovim config for LSP",
                        "feat: add tmux session manager script",
                    ],
                ),
            ],
        )


def get_github_client() -> GitHubClient:
    if settings.environment.lower() == "test":
        return FakeGitHubClient()
    return RealGitHubClient()
