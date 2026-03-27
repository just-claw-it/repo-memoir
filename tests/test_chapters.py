from datetime import datetime, timedelta

from repomemoir.analyzers.chapters import cluster_commits_into_chapters
from repomemoir.models import CommitRecord


def _commit(idx: int, dt: datetime, emb: list[float] | None) -> CommitRecord:
    return CommitRecord(
        sha=f"sha{idx:04d}",
        message=f"msg {idx}",
        author="alice",
        date=dt,
        files_changed=["src/a.py"],
        insertions=1,
        deletions=0,
        embedding=emb,
    )


def test_chapters_require_embeddings():
    commits = [_commit(1, datetime(2024, 1, 1), None)]
    try:
        cluster_commits_into_chapters(commits)
        assert False, "Expected ValueError for missing embeddings"
    except ValueError:
        assert True


def test_small_history_becomes_single_chapter():
    start = datetime(2024, 1, 1)
    commits = [
        _commit(1, start, [0.1, 0.1]),
        _commit(2, start + timedelta(days=1), [0.1, 0.2]),
        _commit(3, start + timedelta(days=2), [0.2, 0.1]),
    ]
    chapters = cluster_commits_into_chapters(commits, min_chapter_commits=5)
    assert len(chapters) == 1
    assert len(chapters[0].commits) == 3

