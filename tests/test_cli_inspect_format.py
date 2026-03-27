from datetime import datetime, timezone

from repomemoir.cli import _build_inspect_payload
from repomemoir.models import Contributor


def test_build_inspect_payload_shapes_json_response():
    now = datetime.now(timezone.utc)
    contributors = [
        Contributor(
            handle="alice",
            commit_count=10,
            influence_score=42.0,
            core_areas=["src"],
            active_period=(now, now),
            role="architect",
        )
    ]
    payload = _build_inspect_payload(
        repo="owner/repo",
        commits_count=100,
        turning_points_count=7,
        contributors=contributors,
        origin="origin signals",
        current="current signals",
        open_threads=["Issue 1"],
        top=5,
        offline_mode=True,
    )
    assert payload["repo"] == "owner/repo"
    assert payload["offline_mode"] is True
    assert payload["commits_analyzed"] == 100
    assert payload["turning_points_detected"] == 7
    assert payload["top_contributors"][0]["handle"] == "alice"
    assert payload["open_threads_count"] == 1

