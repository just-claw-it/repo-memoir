from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from git import Repo

from repomemoir.models import CommitRecord


def _is_local_repo(repo_ref: str) -> bool:
    return Path(repo_ref).exists()


def _collect_commits(repo: Repo, max_commits: int, since_sha: str | None) -> list[CommitRecord]:
    commits: list[CommitRecord] = []
    for commit in repo.iter_commits("HEAD", max_count=max_commits):
        if since_sha and commit.hexsha == since_sha:
            break

        stats = commit.stats.total
        files_changed = sorted(commit.stats.files.keys())
        committed_dt = datetime.fromtimestamp(commit.committed_date)

        commits.append(
            CommitRecord(
                sha=commit.hexsha,
                message=(commit.message or "").strip(),
                author=getattr(commit.author, "name", "unknown") or "unknown",
                date=committed_dt,
                files_changed=files_changed,
                insertions=int(stats.get("insertions", 0)),
                deletions=int(stats.get("deletions", 0)),
            )
        )
    commits.reverse()
    return commits


def extract_commits(repo_ref: str, max_commits: int = 5000, since_sha: str | None = None) -> list[CommitRecord]:
    """Extract commit history with file metadata from local path or GitHub owner/repo."""
    if _is_local_repo(repo_ref):
        return _collect_commits(Repo(repo_ref), max_commits=max_commits, since_sha=since_sha)

    if "/" not in repo_ref:
        raise ValueError("Expected local path or GitHub owner/repo.")

    clone_url = f"https://github.com/{repo_ref}.git"
    with TemporaryDirectory(prefix="repo_memoir_") as tmp:
        repo = Repo.clone_from(clone_url, tmp, depth=max_commits)
        return _collect_commits(repo, max_commits=max_commits, since_sha=since_sha)
