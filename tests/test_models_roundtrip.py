from datetime import datetime, timezone

from repomemoir.models import CommitRecord, RepoMemoirDocument


def test_commit_record_roundtrip():
    commit = CommitRecord(
        sha="abc",
        message="init",
        author="alice",
        date=datetime.now(timezone.utc),
        files_changed=["src/a.py"],
        insertions=10,
        deletions=2,
    )
    assert CommitRecord.from_dict(commit.to_dict()).sha == "abc"


def test_document_roundtrip_minimal():
    doc = RepoMemoirDocument(repo="x/y", generated_at=datetime.now(timezone.utc).isoformat(), last_commit_sha="123")
    rebuilt = RepoMemoirDocument.from_dict(doc.to_dict())
    assert rebuilt.repo == "x/y"
