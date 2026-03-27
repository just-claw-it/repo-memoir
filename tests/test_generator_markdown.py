from datetime import datetime, timezone

from repomemoir.generator import render_markdown
from repomemoir.models import Chapter, CommitRecord, Contributor, TurningPoint


def test_render_markdown_contains_evidence_sections():
    now = datetime.now(timezone.utc)
    commit = CommitRecord(
        sha="abc",
        message="add core pipeline",
        author="alice",
        date=now,
        files_changed=["src/core.py"],
        insertions=10,
        deletions=2,
        embedding=[0.1, 0.2],
    )
    chapter = Chapter(
        title="Core Pipeline Emerges",
        start_date=now,
        end_date=now,
        commits=[commit],
        dominant_files=["src/core.py"],
        dominant_contributors=["alice"],
        summary="Narrative body",
    )
    turning_point = TurningPoint(
        date=now,
        type="pivot",
        description="Introduced src/core subsystem.",
        evidence="add core pipeline",
        impact="A clear architecture direction.",
    )
    contributor = Contributor(
        handle="alice",
        commit_count=1,
        influence_score=3.0,
        core_areas=["src"],
        active_period=(now, now),
        role="maintainer",
    )

    markdown = render_markdown(
        repo="owner/repo",
        generated_at=now.isoformat(),
        chapters=[chapter],
        turning_points=[turning_point],
        contributors=[contributor],
        origin_intent="Initial goal",
        current_identity="Current goal",
        open_threads=["Issue A"],
        assembly_text="Assembly",
    )

    assert "**Evidence markers:**" in markdown
    assert "> **Evidence:** add core pipeline" in markdown
    assert "> **Interpretation:** A clear architecture direction." in markdown


def test_render_markdown_offline_mode_banner():
    now = datetime.now(timezone.utc)
    commit = CommitRecord(
        sha="abc",
        message="add core pipeline",
        author="alice",
        date=now,
        files_changed=["src/core.py"],
        insertions=10,
        deletions=2,
        embedding=[0.1, 0.2],
    )
    chapter = Chapter(
        title="Core Pipeline Emerges",
        start_date=now,
        end_date=now,
        commits=[commit],
        dominant_files=["src/core.py"],
        dominant_contributors=["alice"],
        summary="Narrative body",
    )
    markdown = render_markdown(
        repo="owner/repo",
        generated_at=now.isoformat(),
        chapters=[chapter],
        turning_points=[],
        contributors=[],
        origin_intent="Initial goal",
        current_identity="Current goal",
        open_threads=[],
        assembly_text="Assembly",
        offline_mode=True,
    )
    assert "Offline algorithmic mode" in markdown

