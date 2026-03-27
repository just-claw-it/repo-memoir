from __future__ import annotations

from collections import Counter

try:
    import hdbscan
except ImportError:  # pragma: no cover - depends on environment extras
    hdbscan = None

try:
    from sklearn.preprocessing import StandardScaler
except ImportError:  # pragma: no cover - depends on environment extras
    StandardScaler = None

from repomemoir.models import Chapter, CommitRecord


def _cluster_labels(vectors: list[list[float]]) -> list[int]:
    if len(vectors) < 2:
        return [0] * len(vectors)
    if len(vectors) < 5:
        return [0] * len(vectors)
    if hdbscan is None or StandardScaler is None:
        return [0] * len(vectors)

    transformed = StandardScaler().fit_transform(vectors)
    clusterer = hdbscan.HDBSCAN(min_cluster_size=3, min_samples=1)
    return clusterer.fit_predict(transformed).tolist()


def _merge_small_chapters(chapters: list[Chapter], min_chapter_commits: int) -> list[Chapter]:
    if len(chapters) <= 1:
        return chapters

    chapters = sorted(chapters, key=lambda c: c.start_date)
    i = 0
    while i < len(chapters):
        current = chapters[i]
        if len(current.commits) >= min_chapter_commits or len(chapters) == 1:
            i += 1
            continue

        if i == 0:
            target_idx = 1
        elif i == len(chapters) - 1:
            target_idx = i - 1
        else:
            prev_gap = abs((current.start_date - chapters[i - 1].end_date).total_seconds())
            next_gap = abs((chapters[i + 1].start_date - current.end_date).total_seconds())
            target_idx = i - 1 if prev_gap <= next_gap else i + 1

        target = chapters[target_idx]
        target.commits.extend(current.commits)
        target.commits.sort(key=lambda c: c.date)
        target.start_date = min(target.start_date, current.start_date)
        target.end_date = max(target.end_date, current.end_date)
        target.dominant_files = list(dict.fromkeys(target.dominant_files + current.dominant_files))[:5]
        target.dominant_contributors = list(
            dict.fromkeys(target.dominant_contributors + current.dominant_contributors)
        )[:3]

        chapters.pop(i)
        if target_idx < i:
            i -= 1

    chapters.sort(key=lambda c: c.start_date)
    return chapters


def cluster_commits_into_chapters(commits: list[CommitRecord], min_chapter_commits: int = 5) -> list[Chapter]:
    if not commits:
        return []

    missing = [c for c in commits if c.embedding is None]
    if missing:
        raise ValueError("All commits must have embeddings before clustering.")

    labels = _cluster_labels([c.embedding for c in commits])
    by_label: dict[int, list[CommitRecord]] = {}
    for label, commit in zip(labels, commits, strict=True):
        by_label.setdefault(label, []).append(commit)

    chapters: list[Chapter] = []
    for label, grouped in by_label.items():
        grouped.sort(key=lambda c: c.date)
        file_counter: Counter[str] = Counter()
        author_counter: Counter[str] = Counter()
        for commit in grouped:
            file_counter.update(commit.files_changed)
            author_counter.update([commit.author])

        chapters.append(
            Chapter(
                title=f"Chapter {label if label >= 0 else 'Noise'}",
                start_date=grouped[0].date,
                end_date=grouped[-1].date,
                commits=grouped,
                dominant_files=[f for f, _ in file_counter.most_common(5)],
                dominant_contributors=[a for a, _ in author_counter.most_common(3)],
                summary="",
            )
        )

    chapters.sort(key=lambda c: c.start_date)

    merged = _merge_small_chapters(chapters, min_chapter_commits=min_chapter_commits)

    for i, chapter in enumerate(merged, start=1):
        chapter.title = f"Chapter {i}"

    return merged
