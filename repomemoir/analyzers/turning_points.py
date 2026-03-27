from __future__ import annotations

from collections import Counter
from pathlib import Path

from repomemoir.models import CommitRecord, TurningPoint


PACKAGE_FILES = {"pyproject.toml", "requirements.txt", "package.json", "Pipfile", "poetry.lock"}
NON_PRODUCT_DIRS = {"docs", "test", "tests", ".github", ".vscode"}


def detect_turning_points(commits: list[CommitRecord], deletion_threshold: int = 500) -> list[TurningPoint]:
    if not commits:
        return []

    points: list[TurningPoint] = []
    seen_top_levels: set[str] = set()

    for idx, commit in enumerate(commits):
        if commit.deletions >= deletion_threshold:
            points.append(
                TurningPoint(
                    date=commit.date,
                    type="refactor",
                    description=f"Large deletion event in {commit.sha[:7]} ({commit.deletions} lines removed).",
                    evidence=commit.message,
                    impact="Potential simplification or architecture reset.",
                )
            )

        top_levels = {f.split("/", 1)[0] for f in commit.files_changed if "/" in f}
        substantive_new_dirs = sorted(
            d
            for d in (top_levels - seen_top_levels)
            if d not in NON_PRODUCT_DIRS and sum(1 for f in commit.files_changed if f.startswith(f"{d}/")) >= 3
        )
        seen_top_levels.update(top_levels)
        if substantive_new_dirs:
            points.append(
                TurningPoint(
                    date=commit.date,
                    type="pivot",
                    description=f"Introduced new top-level area(s): {', '.join(substantive_new_dirs[:3])}.",
                    evidence=commit.message,
                    impact="Signals a structural broadening of project scope.",
                )
            )

        dep_manifest_changed = any(Path(f).name in PACKAGE_FILES for f in commit.files_changed)
        dep_change_size = commit.insertions + commit.deletions
        if dep_manifest_changed and dep_change_size >= 20:
            points.append(
                TurningPoint(
                    date=commit.date,
                    type="dependency_shift",
                    description=f"Dependency manifest changed materially ({dep_change_size} lines touched).",
                    evidence=commit.message,
                    impact="Could indicate tooling/runtime strategy changes.",
                )
            )

        rename_tokens = ("rename", "renaming", "migrate", "move", "moved")
        if len(commit.files_changed) >= 25 and any(token in commit.message.lower() for token in rename_tokens):
            points.append(
                TurningPoint(
                    date=commit.date,
                    type="naming",
                    description="Large rename/move-like change detected.",
                    evidence=commit.message,
                    impact="Possible identity or architecture terminology shift.",
                )
            )

        if idx > 0:
            gap = commit.date - commits[idx - 1].date
            if gap.days >= 90:
                points.append(
                    TurningPoint(
                        date=commit.date,
                        type="revival",
                        description=f"Activity resumed after {gap.days} days of silence.",
                        evidence=commit.message,
                        impact="Suggests renewed project investment or ownership.",
                    )
                )

    if len(commits) >= 10:
        week_counts: Counter[str] = Counter(c.date.strftime("%Y-%W") for c in commits)
        values = sorted(week_counts.values())
        baseline = values[len(values) // 2] if values else 1
        weeks = sorted(week_counts.keys())
        streak: list[str] = []
        for week in weeks:
            if baseline > 0 and week_counts[week] >= baseline * 3:
                streak.append(week)
            else:
                streak = []

            if len(streak) >= 2:
                sample_week = streak[0]
                sample_commit = next(c for c in commits if c.date.strftime("%Y-%W") == sample_week)
                points.append(
                    TurningPoint(
                        date=sample_commit.date,
                        type="active_development",
                        description=(
                            "Sustained commit velocity burst detected "
                            f"({week_counts[streak[0]]}+ commits/week vs baseline {baseline})."
                        ),
                        evidence="Consecutive weekly commit histogram spikes",
                        impact="Likely intense delivery phase or deadline push.",
                    )
                )
                streak = []

    points.sort(key=lambda p: p.date)
    return points
