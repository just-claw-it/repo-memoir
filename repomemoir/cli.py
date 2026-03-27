from __future__ import annotations

from collections import Counter
import json
import shutil
import time
from pathlib import Path

import typer
import requests

from repomemoir.analyzers.chapters import cluster_commits_into_chapters
from repomemoir.analyzers.identity import extract_origin_and_current_identity
from repomemoir.analyzers.turning_points import detect_turning_points
from repomemoir.config import load_config
from repomemoir.extractors.commits import extract_commits
from repomemoir.extractors.contributors import score_contributors
from repomemoir.extractors.issues import extract_issues
from repomemoir.extractors.prs import extract_pull_requests
from repomemoir.extractors.repo_meta import extract_current_readme
from repomemoir.generator import generate_memoir
from repomemoir.llm import LLMClient, OfflineLLMClient
from repomemoir.updater import load_sidecar, save_sidecar, update_memoir


app = typer.Typer(help="Generate a living memoir of repository evolution.")


def _repo_slug(repo_ref: str) -> str:
    if "/" in repo_ref and not Path(repo_ref).exists():
        return repo_ref.replace("/", "_")
    return Path(repo_ref).resolve().name


def _output_paths(output: str | None, output_dir: str, repo_ref: str) -> tuple[Path, Path]:
    if output:
        md_path = Path(output)
        json_path = md_path.with_suffix(".json")
        return md_path, json_path
    base = _repo_slug(repo_ref)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{base}.memoir.md", out_dir / f"{base}.memoir.json"


def _aggregate_contributor_signals(prs: list[dict], issues: list[dict]) -> tuple[dict[str, int], dict[str, int]]:
    prs_merged_by_author: Counter[str] = Counter()
    issues_resolved_by_author: Counter[str] = Counter()

    for pr in prs:
        merged_by = pr.get("merged_by")
        if pr.get("merged") and merged_by:
            prs_merged_by_author[merged_by] += 1

    for issue in issues:
        closed_by = issue.get("closed_by")
        if issue.get("state") == "closed" and closed_by:
            issues_resolved_by_author[closed_by] += 1

    return dict(prs_merged_by_author), dict(issues_resolved_by_author)


def _cache_options(cfg, *, no_cache: bool) -> tuple[str | None, int]:
    if no_cache:
        return None, 0
    return cfg.github_cache_dir, cfg.github_cache_ttl_seconds


def _make_llm_client(cfg, *, offline: bool = False) -> LLMClient:
    if offline:
        return OfflineLLMClient()
    return LLMClient(
        cfg.llm_base_url,
        cfg.llm_api_key,
        cfg.llm_model,
        cfg.embedding_model,
        max_retries=cfg.llm_max_retries,
        retry_backoff_seconds=cfg.llm_retry_backoff_seconds,
        embedding_cache_dir=cfg.embedding_cache_dir,
        embedding_cache_ttl_seconds=cfg.embedding_cache_ttl_seconds,
    )


def _load_remote_signals(
    repo: str,
    cfg,
    *,
    no_cache: bool = False,
    offline: bool = False,
) -> tuple[list[dict], list[dict], str]:
    if "/" not in repo or Path(repo).exists():
        return [], [], extract_current_readme(repo)
    if offline:
        return [], [], ""
    cache_dir, cache_ttl_seconds = _cache_options(cfg, no_cache=no_cache)
    prs = extract_pull_requests(
        repo,
        cfg.github_token,
        cache_dir=cache_dir,
        cache_ttl_seconds=cache_ttl_seconds,
    )
    issues = extract_issues(
        repo,
        cfg.github_token,
        cache_dir=cache_dir,
        cache_ttl_seconds=cache_ttl_seconds,
    )
    readme_text = extract_current_readme(
        repo,
        cfg.github_token,
        cache_dir=cache_dir,
        cache_ttl_seconds=cache_ttl_seconds,
    )
    return prs, issues, readme_text


def _build_inspect_payload(
    repo: str,
    commits_count: int,
    turning_points_count: int,
    contributors: list,
    origin: str,
    current: str,
    open_threads: list[str],
    top: int,
    offline_mode: bool,
) -> dict:
    return {
        "repo": repo,
        "offline_mode": offline_mode,
        "commits_analyzed": commits_count,
        "turning_points_detected": turning_points_count,
        "top_contributors": [
            {
                "handle": c.handle,
                "influence_score": c.influence_score,
                "commit_count": c.commit_count,
                "role": c.role,
            }
            for c in contributors[:top]
        ],
        "origin_intent_signals": origin,
        "current_identity_signals": current,
        "open_threads_count": len(open_threads),
        "open_threads": open_threads,
    }


@app.command()
def generate(
    repo: str = typer.Option(..., help="owner/repo or local git path"),
    output: str | None = typer.Option(None, help="Markdown output path"),
    config: str | None = typer.Option(None, help="Path to repomemoir.yaml"),
    focus_contributor: str | None = typer.Option(None, help="Optional contributor handle to prioritize"),
    strict_grounding: bool = typer.Option(False, help="Enforce strict evidence-grounding output validation"),
    strict_grounding_fail_fast: bool = typer.Option(
        False, help="Fail immediately on strict grounding violations instead of auto-repairing"
    ),
    no_cache: bool = typer.Option(False, help="Bypass GitHub API cache for this run"),
    offline: bool = typer.Option(False, help="Run without external API calls (algorithmic/local mode)"),
) -> None:
    cfg = load_config(config)
    llm = _make_llm_client(cfg, offline=offline)

    commits = extract_commits(repo, max_commits=cfg.analysis.max_commits)
    if not commits:
        raise typer.BadParameter("No commits found.")

    embeddings = llm.embed_texts([c.message or "(no message)" for c in commits])
    for commit, embedding in zip(commits, embeddings, strict=True):
        commit.embedding = embedding

    chapters = cluster_commits_into_chapters(commits, min_chapter_commits=cfg.analysis.min_chapter_commits)
    turning_points = detect_turning_points(commits, deletion_threshold=cfg.analysis.turning_point_deletion_threshold)

    prs, issues, readme_text = _load_remote_signals(repo, cfg, no_cache=no_cache, offline=offline)

    prs_merged_by_author, issues_resolved_by_author = _aggregate_contributor_signals(prs, issues)
    contributors = score_contributors(
        commits,
        cfg.analysis.influence_weights,
        prs_merged_by_author=prs_merged_by_author,
        issues_resolved_by_author=issues_resolved_by_author,
    )
    if focus_contributor:
        contributors.sort(key=lambda c: (c.handle != focus_contributor, -c.influence_score))

    origin, current, open_threads = extract_origin_and_current_identity(commits, readme_text, issues=issues, prs=prs)

    document = generate_memoir(
        repo_name=repo,
        chapters=chapters,
        turning_points=turning_points,
        contributors=contributors,
        origin_intent=origin,
        current_identity=current,
        open_threads=open_threads,
        llm=llm,
        last_commit_sha=commits[-1].sha,
        strict_grounding=strict_grounding,
        strict_grounding_fail_fast=strict_grounding_fail_fast,
        offline_mode=offline,
    )

    md_path, json_path = _output_paths(output, cfg.output_dir, repo)
    md_path.write_text(document.markdown)
    save_sidecar(json_path, document)

    if cfg.output_format == "json":
        typer.echo(json.dumps(document.to_dict(), indent=2))
    typer.echo(f"Memoir written: {md_path}")
    typer.echo(f"Metadata sidecar: {json_path}")


@app.command()
def update(
    repo: str = typer.Option(..., help="owner/repo or local git path"),
    output: str | None = typer.Option(None, help="Markdown output path"),
    config: str | None = typer.Option(None, help="Path to repomemoir.yaml"),
    strict_grounding: bool = typer.Option(False, help="Enforce strict evidence-grounding output validation"),
    strict_grounding_fail_fast: bool = typer.Option(
        False, help="Fail immediately on strict grounding violations instead of auto-repairing"
    ),
    no_cache: bool = typer.Option(False, help="Bypass GitHub API cache for this run"),
    offline: bool = typer.Option(False, help="Run without external API calls (algorithmic/local mode)"),
) -> None:
    cfg = load_config(config)
    llm = _make_llm_client(cfg, offline=offline)
    md_path, json_path = _output_paths(output, cfg.output_dir, repo)
    if not json_path.exists():
        raise typer.BadParameter(f"No sidecar found at {json_path}. Run generate first.")

    updated = update_memoir(
        repo_ref=repo,
        sidecar_path=json_path,
        llm=llm,
        influence_weights=cfg.analysis.influence_weights,
        min_chapter_commits=cfg.analysis.min_chapter_commits,
        deletion_threshold=cfg.analysis.turning_point_deletion_threshold,
        strict_grounding=strict_grounding,
        strict_grounding_fail_fast=strict_grounding_fail_fast,
        no_cache=no_cache,
    )
    md_path.write_text(updated.markdown)
    typer.echo(f"Memoir updated: {md_path}")


@app.command()
def inspect(
    repo: str = typer.Option(..., help="owner/repo or local git path"),
    config: str | None = typer.Option(None, help="Path to repomemoir.yaml"),
    top: int = typer.Option(5, help="Number of top contributors to show"),
    format: str = typer.Option("text", help="Output format: text or json"),
    no_cache: bool = typer.Option(False, help="Bypass GitHub API cache for this run"),
    offline: bool = typer.Option(False, help="Run without external API calls (algorithmic/local mode)"),
) -> None:
    """Quickly inspect core repository signals without LLM memoir generation."""
    cfg = load_config(config)
    commits = extract_commits(repo, max_commits=cfg.analysis.max_commits)
    if not commits:
        raise typer.BadParameter("No commits found.")

    if format not in {"text", "json"}:
        raise typer.BadParameter("format must be 'text' or 'json'")

    prs, issues, readme_text = _load_remote_signals(repo, cfg, no_cache=no_cache, offline=offline)

    prs_merged_by_author, issues_resolved_by_author = _aggregate_contributor_signals(prs, issues)
    contributors = score_contributors(
        commits,
        cfg.analysis.influence_weights,
        prs_merged_by_author=prs_merged_by_author,
        issues_resolved_by_author=issues_resolved_by_author,
    )
    turning_points = detect_turning_points(commits, deletion_threshold=cfg.analysis.turning_point_deletion_threshold)
    origin, current, open_threads = extract_origin_and_current_identity(commits, readme_text, issues=issues, prs=prs)

    payload = _build_inspect_payload(
        repo,
        commits_count=len(commits),
        turning_points_count=len(turning_points),
        contributors=contributors,
        origin=origin,
        current=current,
        open_threads=open_threads,
        top=top,
        offline_mode=offline,
    )
    if format == "json":
        typer.echo(json.dumps(payload, indent=2))
        return

    typer.echo(f"Repository: {repo}")
    typer.echo(f"Mode: {'offline' if offline else 'online'}")
    typer.echo(f"Commits analyzed: {len(commits)}")
    typer.echo(f"Turning points detected: {len(turning_points)}")
    typer.echo("")
    typer.echo("Top contributors:")
    for contributor in contributors[:top]:
        typer.echo(
            f"- {contributor.handle}: influence={contributor.influence_score}, "
            f"commits={contributor.commit_count}, role={contributor.role}"
        )
    typer.echo("")
    typer.echo("Origin intent signals:")
    typer.echo(origin[:400] + ("..." if len(origin) > 400 else ""))
    typer.echo("")
    typer.echo("Current identity signals:")
    typer.echo(current[:400] + ("..." if len(current) > 400 else ""))
    typer.echo("")
    typer.echo(f"Open threads: {len(open_threads)}")


@app.command()
def chapters(
    repo: str = typer.Option(..., help="owner/repo or local git path"),
    config: str | None = typer.Option(None, help="Path to repomemoir.yaml"),
    format: str = typer.Option("text", help="Output format: text or json"),
    offline: bool = typer.Option(False, help="Run without external API calls (algorithmic/local mode)"),
) -> None:
    """Preview chapter boundaries and dominant signals before generation."""
    if format not in {"text", "json"}:
        raise typer.BadParameter("format must be 'text' or 'json'")

    cfg = load_config(config)
    llm = _make_llm_client(cfg, offline=offline)
    commits = extract_commits(repo, max_commits=cfg.analysis.max_commits)
    if not commits:
        raise typer.BadParameter("No commits found.")

    embeddings = llm.embed_texts([c.message or "(no message)" for c in commits])
    for commit, embedding in zip(commits, embeddings, strict=True):
        commit.embedding = embedding
    chapter_models = cluster_commits_into_chapters(commits, min_chapter_commits=cfg.analysis.min_chapter_commits)

    payload = {
        "repo": repo,
        "chapter_count": len(chapter_models),
        "chapters": [
            {
                "title": chapter.title,
                "start_date": chapter.start_date.isoformat(),
                "end_date": chapter.end_date.isoformat(),
                "commit_count": len(chapter.commits),
                "dominant_files": chapter.dominant_files,
                "dominant_contributors": chapter.dominant_contributors,
            }
            for chapter in chapter_models
        ],
    }
    if format == "json":
        typer.echo(json.dumps(payload, indent=2))
        return

    typer.echo(f"Repository: {repo}")
    typer.echo(f"Chapter count: {len(chapter_models)}")
    typer.echo("")
    for chapter in payload["chapters"]:
        typer.echo(
            f"- {chapter['title']}: {chapter['start_date'][:10]} -> {chapter['end_date'][:10]}, "
            f"commits={chapter['commit_count']}"
        )


@app.command("cache-clear")
def cache_clear(
    config: str | None = typer.Option(None, help="Path to repomemoir.yaml"),
) -> None:
    """Delete repo-memoir GitHub cache directory."""
    cfg = load_config(config)
    cache_dir = Path(cfg.github_cache_dir)
    if not cache_dir.exists():
        typer.echo(f"Cache directory does not exist: {cache_dir}")
        return
    shutil.rmtree(cache_dir)
    typer.echo(f"Cache cleared: {cache_dir}")


@app.command()
def watch(
    repo: str = typer.Option(..., help="owner/repo or local git path"),
    interval: int = typer.Option(3600, help="Polling interval in seconds"),
    output: str | None = typer.Option(None, help="Markdown output path"),
    config: str | None = typer.Option(None, help="Path to repomemoir.yaml"),
    strict_grounding: bool = typer.Option(False, help="Enforce strict evidence-grounding output validation"),
    strict_grounding_fail_fast: bool = typer.Option(
        False, help="Fail immediately on strict grounding violations instead of auto-repairing"
    ),
    no_cache: bool = typer.Option(False, help="Bypass GitHub API cache for this run"),
    offline: bool = typer.Option(False, help="Run without external API calls (algorithmic/local mode)"),
) -> None:
    try:
        while True:
            try:
                update(
                    repo=repo,
                    output=output,
                    config=config,
                    strict_grounding=strict_grounding,
                    strict_grounding_fail_fast=strict_grounding_fail_fast,
                    no_cache=no_cache,
                    offline=offline,
                )
            except typer.BadParameter:
                generate(
                    repo=repo,
                    output=output,
                    config=config,
                    strict_grounding=strict_grounding,
                    strict_grounding_fail_fast=strict_grounding_fail_fast,
                    no_cache=no_cache,
                    offline=offline,
                )
            time.sleep(interval)
    except KeyboardInterrupt:
        typer.echo("Stopped watch mode.")


@app.command()
def doctor(
    config: str | None = typer.Option(None, help="Path to repomemoir.yaml"),
) -> None:
    """Check configuration and provider connectivity."""
    cfg = load_config(config)
    checks: list[tuple[str, str]] = []
    checks.append(("config_load", "ok"))
    checks.append(("llm_api_key", "ok" if cfg.llm_api_key else "missing"))
    checks.append(("github_token", "ok" if cfg.github_token else "missing_optional"))

    try:
        response = requests.get(f"{(cfg.llm_base_url or 'https://api.openai.com').rstrip('/')}/v1/models", timeout=10)
        checks.append(("llm_models_endpoint", "ok" if response.status_code < 500 else f"error:{response.status_code}"))
    except requests.RequestException:
        checks.append(("llm_models_endpoint", "unreachable"))

    for name, status in checks:
        typer.echo(f"{name}: {status}")


@app.command()
def diff(
    repo: str = typer.Option(..., help="owner/repo or local git path"),
    output: str | None = typer.Option(None, help="Markdown output path"),
    config: str | None = typer.Option(None, help="Path to repomemoir.yaml"),
) -> None:
    """Show what changed since current sidecar snapshot."""
    cfg = load_config(config)
    _, json_path = _output_paths(output, cfg.output_dir, repo)
    if not json_path.exists():
        raise typer.BadParameter(f"No sidecar found at {json_path}. Run generate first.")

    current = load_sidecar(json_path)
    new_commits = extract_commits(repo, since_sha=current.last_commit_sha)
    if not new_commits:
        typer.echo("No changes since last snapshot.")
        return

    turning_points = detect_turning_points(new_commits, deletion_threshold=cfg.analysis.turning_point_deletion_threshold)
    changed_authors = Counter(c.author for c in new_commits)
    typer.echo(f"Base snapshot: {json_path}")
    typer.echo(f"New commits: {len(new_commits)}")
    typer.echo(f"Potential new turning points: {len(turning_points)}")
    typer.echo("Top active contributors in new commits:")
    for author, count in changed_authors.most_common(5):
        typer.echo(f"- {author}: {count}")


if __name__ == "__main__":
    app()
