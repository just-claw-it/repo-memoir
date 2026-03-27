from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime

from repomemoir.models import CommitRecord, Contributor


CORE_PREFIXES = ("src/", "lib/")


def _is_core_file(path: str) -> bool:
    if path.startswith(("tests/", "test/", "docs/", ".github/")):
        return False
    if "/" not in path:
        return True
    return path.startswith(CORE_PREFIXES)


def score_contributors(
    commits: list[CommitRecord],
    influence_weights: dict[str, float],
    prs_merged_by_author: dict[str, int] | None = None,
    issues_resolved_by_author: dict[str, int] | None = None,
    review_comments_by_author: dict[str, int] | None = None,
) -> list[Contributor]:
    prs_merged_by_author = prs_merged_by_author or {}
    issues_resolved_by_author = issues_resolved_by_author or {}
    review_comments_by_author = review_comments_by_author or {}

    by_author: dict[str, list[CommitRecord]] = defaultdict(list)
    for commit in commits:
        by_author[commit.author].append(commit)

    contributors: list[Contributor] = []
    for author, authored_commits in by_author.items():
        commit_count = len(authored_commits)
        core_commit_count = sum(1 for c in authored_commits if any(_is_core_file(f) for f in c.files_changed))

        area_counter: Counter[str] = Counter()
        for commit in authored_commits:
            for changed in commit.files_changed:
                area = changed.split("/", 1)[0] if "/" in changed else changed
                area_counter[area] += 1

        start = min(c.date for c in authored_commits) if authored_commits else datetime.utcnow()
        end = max(c.date for c in authored_commits) if authored_commits else datetime.utcnow()

        influence = (
            core_commit_count * influence_weights.get("core_commits", 3)
            + prs_merged_by_author.get(author, 0) * influence_weights.get("prs_merged", 2)
            + issues_resolved_by_author.get(author, 0) * influence_weights.get("issues_resolved", 1)
            + review_comments_by_author.get(author, 0) * influence_weights.get("review_comments", 0.5)
        )

        role = "maintainer"
        if influence >= 60:
            role = "architect"
        elif influence >= 30:
            role = "implementer"

        contributors.append(
            Contributor(
                handle=author,
                commit_count=commit_count,
                influence_score=float(round(influence, 2)),
                core_areas=[a for a, _ in area_counter.most_common(3)],
                active_period=(start, end),
                role=role,
            )
        )

    contributors.sort(key=lambda c: c.influence_score, reverse=True)
    return contributors
