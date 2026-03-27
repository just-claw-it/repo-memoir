from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from repomemoir.analyzers.chapters import cluster_commits_into_chapters
from repomemoir.analyzers.turning_points import detect_turning_points
from repomemoir.extractors.commits import extract_commits
from repomemoir.extractors.contributors import score_contributors
from repomemoir.generator import (
    generate_assembly_text,
    generate_chapter_content,
    generate_turning_point_interpretation,
    render_markdown,
)
from repomemoir.llm import LLMClient
from repomemoir.llm import OfflineLLMClient
from repomemoir.models import Chapter, RepoMemoirDocument


def load_sidecar(path: Path) -> RepoMemoirDocument:
    payload = json.loads(path.read_text())
    return RepoMemoirDocument.from_dict(payload)


def save_sidecar(path: Path, document: RepoMemoirDocument) -> None:
    path.write_text(json.dumps(document.to_dict(), indent=2))


def _refresh_chapter_stats(chapter: Chapter) -> None:
    file_counter: Counter[str] = Counter()
    author_counter: Counter[str] = Counter()
    chapter.commits.sort(key=lambda c: c.date)
    for commit in chapter.commits:
        file_counter.update(commit.files_changed)
        author_counter.update([commit.author])
    chapter.start_date = chapter.commits[0].date
    chapter.end_date = chapter.commits[-1].date
    chapter.dominant_files = [f for f, _ in file_counter.most_common(5)]
    chapter.dominant_contributors = [a for a, _ in author_counter.most_common(3)]


def _should_extend_last_chapter(current: RepoMemoirDocument, new_commits_count: int, first_new_commit_date: datetime) -> bool:
    if not current.chapters:
        return False
    if new_commits_count <= 0:
        return False
    last = current.chapters[-1]
    gap_days = (first_new_commit_date.replace(tzinfo=None) - last.end_date).days
    return new_commits_count <= 25 and gap_days <= 30


def update_memoir(
    repo_ref: str,
    sidecar_path: Path,
    llm: LLMClient,
    influence_weights: dict[str, float],
    min_chapter_commits: int,
    deletion_threshold: int,
    strict_grounding: bool = False,
    strict_grounding_fail_fast: bool = False,
    no_cache: bool = False,
) -> RepoMemoirDocument:
    current = load_sidecar(sidecar_path)
    offline_mode = isinstance(llm, OfflineLLMClient)
    new_commits = extract_commits(repo_ref, since_sha=current.last_commit_sha)
    if not new_commits:
        current.generated_at = datetime.now(timezone.utc).isoformat()
        save_sidecar(sidecar_path, current)
        return current

    embeddings = llm.embed_texts([c.message or "(no message)" for c in new_commits])
    for commit, embedding in zip(new_commits, embeddings, strict=True):
        commit.embedding = embedding

    chapters = list(current.chapters)
    if _should_extend_last_chapter(current, len(new_commits), new_commits[0].date):
        chapters[-1].commits.extend(new_commits)
        _refresh_chapter_stats(chapters[-1])
        generate_chapter_content(
            current.repo,
            chapters[-1],
            llm,
            strict_grounding=strict_grounding,
            strict_grounding_fail_fast=strict_grounding_fail_fast,
        )
    else:
        new_chapters = cluster_commits_into_chapters(new_commits, min_chapter_commits=min_chapter_commits)
        for chapter in new_chapters:
            generate_chapter_content(
                current.repo,
                chapter,
                llm,
                strict_grounding=strict_grounding,
                strict_grounding_fail_fast=strict_grounding_fail_fast,
            )
        chapters.extend(new_chapters)

    all_commits = [c for chapter in chapters for c in chapter.commits]
    new_turning_points = detect_turning_points(new_commits, deletion_threshold=deletion_threshold)
    for tp in new_turning_points:
        generate_turning_point_interpretation(
            current.repo,
            tp,
            llm,
            strict_grounding=strict_grounding,
            strict_grounding_fail_fast=strict_grounding_fail_fast,
        )
    turning_points = sorted(current.turning_points + new_turning_points, key=lambda tp: tp.date)
    contributors = score_contributors(all_commits, influence_weights)
    assembly = generate_assembly_text(
        current.repo,
        current.origin_intent,
        current.current_identity,
        current.open_threads,
        llm,
        strict_grounding=strict_grounding,
        strict_grounding_fail_fast=strict_grounding_fail_fast,
    )
    updated = RepoMemoirDocument(
        repo=current.repo,
        generated_at=datetime.now(timezone.utc).isoformat(),
        last_commit_sha=all_commits[-1].sha,
        chapters=chapters,
        turning_points=turning_points,
        contributors=contributors,
        origin_intent=current.origin_intent,
        current_identity=current.current_identity,
        open_threads=current.open_threads,
        markdown=render_markdown(
            current.repo,
            datetime.now(timezone.utc).isoformat(),
            chapters,
            turning_points,
            contributors,
            current.origin_intent,
            current.current_identity,
            current.open_threads,
            assembly,
            offline_mode=offline_mode,
        ),
        offline_mode=offline_mode,
    )

    save_sidecar(sidecar_path, updated)
    return updated
