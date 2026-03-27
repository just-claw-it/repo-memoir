from __future__ import annotations

from github import Github

from repomemoir.extractors.github_cache import get_cached_payload, set_cached_payload


def extract_issues(
    repo_name: str,
    token: str | None = None,
    state: str = "all",
    cache_dir: str | None = None,
    cache_ttl_seconds: int = 3600,
) -> list[dict]:
    cache_key = f"issues:{repo_name}:{state}"
    if cache_dir:
        cached = get_cached_payload(cache_dir, cache_key, cache_ttl_seconds)
        if cached is not None:
            return cached

    gh = Github(token) if token else Github()
    repo = gh.get_repo(repo_name)
    issues = repo.get_issues(state=state, sort="created", direction="asc")
    payload: list[dict] = []
    for issue in issues:
        if issue.pull_request:
            continue
        payload.append(
            {
                "number": issue.number,
                "title": issue.title,
                "labels": [label.name for label in issue.labels],
                "state": issue.state,
                "created_at": issue.created_at.isoformat() if issue.created_at else None,
                "closed_at": issue.closed_at.isoformat() if issue.closed_at else None,
                "user": issue.user.login if issue.user else "unknown",
                "closed_by": issue.closed_by.login if issue.closed_by else None,
            }
        )
    if cache_dir:
        set_cached_payload(cache_dir, cache_key, payload)
    return payload
