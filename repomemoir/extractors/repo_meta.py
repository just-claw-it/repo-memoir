from __future__ import annotations

from pathlib import Path

from github import Github

from repomemoir.extractors.github_cache import get_cached_payload, set_cached_payload

def _read_local_readme(repo_path: str) -> str:
    candidates = ("README.md", "README.rst", "README.txt", "readme.md")
    root = Path(repo_path)
    for name in candidates:
        candidate = root / name
        if candidate.exists():
            return candidate.read_text(errors="ignore")
    return ""


def extract_current_readme(
    repo_ref: str,
    token: str | None = None,
    cache_dir: str | None = None,
    cache_ttl_seconds: int = 3600,
) -> str:
    if Path(repo_ref).exists():
        return _read_local_readme(repo_ref)

    if "/" not in repo_ref:
        return ""

    cache_key = f"readme:{repo_ref}"
    if cache_dir:
        cached = get_cached_payload(cache_dir, cache_key, cache_ttl_seconds)
        if isinstance(cached, str):
            return cached

    gh = Github(token) if token else Github()
    repo = gh.get_repo(repo_ref)
    try:
        readme = repo.get_readme()
        text = readme.decoded_content.decode("utf-8", errors="ignore")
        if cache_dir:
            set_cached_payload(cache_dir, cache_key, text)
        return text
    except Exception:
        return ""
