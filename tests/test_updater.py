import json
from datetime import datetime, timezone
from pathlib import Path

from repomemoir.models import RepoMemoirDocument
from repomemoir.updater import update_memoir


class DummyLLM:
    def embed_texts(self, texts):  # pragma: no cover - not used in this test
        return []

    def complete(self, prompt, system=None):  # pragma: no cover - not used in this test
        return ""


def test_update_no_new_commits_persists_timestamp(monkeypatch, tmp_path: Path):
    sidecar = tmp_path / "memoir.json"
    original = RepoMemoirDocument(
        repo="owner/repo",
        generated_at="2024-01-01T00:00:00+00:00",
        last_commit_sha="abc123",
        markdown="memoir",
    )
    sidecar.write_text(json.dumps(original.to_dict()))

    monkeypatch.setattr("repomemoir.updater.extract_commits", lambda repo_ref, since_sha=None: [])

    updated = update_memoir(
        repo_ref="owner/repo",
        sidecar_path=sidecar,
        llm=DummyLLM(),
        influence_weights={"core_commits": 3, "prs_merged": 2, "issues_resolved": 1, "review_comments": 0.5},
        min_chapter_commits=5,
        deletion_threshold=500,
    )

    assert updated.generated_at != original.generated_at
    assert datetime.fromisoformat(updated.generated_at).tzinfo == timezone.utc

    persisted = RepoMemoirDocument.from_dict(json.loads(sidecar.read_text()))
    assert persisted.generated_at == updated.generated_at

