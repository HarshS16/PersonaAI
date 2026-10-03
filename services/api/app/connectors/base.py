"""Shared connector types. Each external source implements a client that
returns these normalized structures, which the sync layer maps into the
persona.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RepoData:
    name: str
    full_name: str
    description: str | None
    html_url: str
    primary_language: str | None
    languages: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    stars: int = 0
    is_fork: bool = False
    readme: str | None = None
    pushed_at: str | None = None
    commits: list[str] = field(default_factory=list)


@dataclass
class GitHubData:
    username: str
    name: str | None
    bio: str | None
    repos: list[RepoData] = field(default_factory=list)
