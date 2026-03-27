from datetime import datetime, timezone

from repomemoir.models import RepoMemoirDocument


def test_repo_memoir_document_offline_flag_roundtrip():
    doc = RepoMemoirDocument(
        repo="owner/repo",
        generated_at=datetime.now(timezone.utc).isoformat(),
        last_commit_sha="abc",
        offline_mode=True,
        markdown="memoir",
    )
    rebuilt = RepoMemoirDocument.from_dict(doc.to_dict())
    assert rebuilt.offline_mode is True

