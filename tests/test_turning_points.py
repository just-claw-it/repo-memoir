from datetime import datetime, timedelta

from repomemoir.analyzers.turning_points import detect_turning_points
from repomemoir.models import CommitRecord


def _commit(
    idx: int,
    date: datetime,
    *,
    files_changed: list[str],
    message: str = "update",
    insertions: int = 5,
    deletions: int = 5,
) -> CommitRecord:
    return CommitRecord(
        sha=f"sha{idx:04d}",
        message=message,
        author="alice",
        date=date,
        files_changed=files_changed,
        insertions=insertions,
        deletions=deletions,
        embedding=[0.1, 0.2],
    )


def test_dependency_shift_requires_material_change():
    start = datetime(2024, 1, 1)
    commits = [
        _commit(1, start, files_changed=["src/a.py"]),
        _commit(2, start + timedelta(days=1), files_changed=["pyproject.toml"], insertions=1, deletions=1),
    ]
    points = detect_turning_points(commits)
    assert not any(point.type == "dependency_shift" for point in points)


def test_pivot_ignores_docs_and_tests():
    start = datetime(2024, 1, 1)
    commits = [
        _commit(1, start, files_changed=["src/a.py", "src/b.py", "src/c.py"]),
        _commit(2, start + timedelta(days=1), files_changed=["docs/x.md", "docs/y.md", "docs/z.md"]),
        _commit(
            3,
            start + timedelta(days=2),
            files_changed=["engine/a.py", "engine/b.py", "engine/c.py"],
            message="add engine module",
        ),
    ]
    points = detect_turning_points(commits)
    assert any(point.type == "pivot" for point in points)
    assert not any(point.type == "pivot" and "docs" in point.description for point in points)


def test_revival_detected_after_long_gap():
    start = datetime(2024, 1, 1)
    commits = [
        _commit(1, start, files_changed=["src/a.py"]),
        _commit(2, start + timedelta(days=100), files_changed=["src/b.py"], message="resume work"),
    ]
    points = detect_turning_points(commits)
    assert any(point.type == "revival" for point in points)

