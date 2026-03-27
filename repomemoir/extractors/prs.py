from __future__ import annotations

from github import Github

from repomemoir.extractors.github_cache import get_cached_payload, set_cached_payload


def extract_pull_requests(
    repo_name: str,
    token: str | None = None,
    state: str = "all",
    cache_dir: str | None = None,
    cache_ttl_seconds: int = 3600,
) -> list[dict]:
    cache_key = f"prs:{repo_name}:{state}"
    if cache_dir:
        cached = get_cached_payload(cache_dir, cache_key, cache_ttl_seconds)
        if cached is not None:
            return cached

    gh = Github(token) if token else Github()
    repo = gh.get_repo(repo_name)
    pulls = repo.get_pulls(state=state, sort="created", direction="asc")
    payload = [
        {
            "number": pr.number,
            "title": pr.title,
            "body": pr.body or "",
            "state": pr.state,
            "merged": bool(pr.merged_at),
            "created_at": pr.created_at.isoformat() if pr.created_at else None,
            "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
            "user": pr.user.login if pr.user else "unknown",
            "merged_by": pr.merged_by.login if pr.merged_by else None,
        }
        for pr in pulls
    ]
    if cache_dir:
        set_cached_payload(cache_dir, cache_key, payload)
    return payload
