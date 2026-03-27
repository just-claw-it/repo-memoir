from __future__ import annotations

from repomemoir.models import CommitRecord


def extract_origin_and_current_identity(
    commits: list[CommitRecord],
    readme_text: str,
    issues: list[dict] | None = None,
    prs: list[dict] | None = None,
) -> tuple[str, str, list[str]]:
    issues = issues or []
    prs = prs or []

    early_commits = commits[:20]
    recent_commits = commits[-20:]

    origin_signals = [c.message for c in early_commits if c.message] + [i.get("title", "") for i in issues[:10]]
    current_signals = [c.message for c in recent_commits if c.message] + [pr.get("title", "") for pr in prs[-10:]]

    origin = " ; ".join([s.strip() for s in origin_signals if s.strip()][:10])
    current = " ; ".join([s.strip() for s in current_signals if s.strip()][:10])

    if readme_text.strip():
        current = (readme_text.strip().splitlines()[0] + " ; " + current).strip(" ;")

    open_threads = [f"{i.get('title', 'Untitled issue')} (open)" for i in issues if i.get("state") == "open"][:10]

    return origin or "No clear origin intent signal found.", current or "No clear current identity signal found.", open_threads
