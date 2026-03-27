from datetime import datetime

from repomemoir.models import Chapter, CommitRecord, RepoMemoirDocument
from repomemoir.updater import _should_extend_last_chapter


def _commit(dt: datetime) -> CommitRecord:
    return CommitRecord(
        sha="abc",
        message="msg",
        author="alice",
        date=dt,
        files_changed=["src/a.py"],
        insertions=1,
        deletions=0,
        embedding=[0.1, 0.2],
    )


def test_should_extend_last_chapter_when_recent_and_small():
    last_date = datetime(2024, 1, 1)
    chapter = Chapter(
        title="c1",
        start_date=last_date,
        end_date=last_date,
        commits=[_commit(last_date)],
        dominant_files=["src/a.py"],
        dominant_contributors=["alice"],
        summary="x",
    )
    doc = RepoMemoirDocument(repo="r", generated_at="x", last_commit_sha="a", chapters=[chapter])
    assert _should_extend_last_chapter(doc, new_commits_count=5, first_new_commit_date=datetime(2024, 1, 20))


def test_should_not_extend_for_long_gap():
    last_date = datetime(2024, 1, 1)
    chapter = Chapter(
        title="c1",
        start_date=last_date,
        end_date=last_date,
        commits=[_commit(last_date)],
        dominant_files=["src/a.py"],
        dominant_contributors=["alice"],
        summary="x",
    )
    doc = RepoMemoirDocument(repo="r", generated_at="x", last_commit_sha="a", chapters=[chapter])
    assert not _should_extend_last_chapter(doc, new_commits_count=5, first_new_commit_date=datetime(2024, 3, 15))

