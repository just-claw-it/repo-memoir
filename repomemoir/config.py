from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class AnalysisConfig:
    max_commits: int = 5000
    min_chapter_commits: int = 5
    turning_point_deletion_threshold: int = 500
    influence_weights: dict[str, float] = field(
        default_factory=lambda: {
            "core_commits": 3,
            "prs_merged": 2,
            "issues_resolved": 1,
            "review_comments": 0.5,
        }
    )


@dataclass
class AppConfig:
    github_token: str | None = None
    github_cache_dir: str = ".repomemoir-cache"
    github_cache_ttl_seconds: int = 3600
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    llm_max_retries: int = 3
    llm_retry_backoff_seconds: float = 1.0
    embedding_cache_dir: str = ".repomemoir-cache"
    embedding_cache_ttl_seconds: int = 604800
    output_dir: str = "./memoirs"
    output_format: str = "markdown"
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)


def _resolve_env(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        return os.getenv(value[2:-1])
    return value


def load_config(path: str | Path | None = None) -> AppConfig:
    config_path = Path(path) if path else Path("repomemoir.yaml")
    raw: dict[str, Any] = {}
    if config_path.exists():
        raw = yaml.safe_load(config_path.read_text()) or {}

    github = raw.get("github", {})
    llm = raw.get("llm", {})
    output = raw.get("output", {})
    analysis_raw = raw.get("analysis", {})

    analysis = AnalysisConfig(
        max_commits=analysis_raw.get("max_commits", 5000),
        min_chapter_commits=analysis_raw.get("min_chapter_commits", 5),
        turning_point_deletion_threshold=analysis_raw.get("turning_point_deletion_threshold", 500),
        influence_weights=analysis_raw.get("influence_weights", AnalysisConfig().influence_weights),
    )

    return AppConfig(
        github_token=_resolve_env(github.get("token", os.getenv("GITHUB_TOKEN"))),
        github_cache_dir=github.get("cache_dir", ".repomemoir-cache"),
        github_cache_ttl_seconds=int(github.get("cache_ttl_seconds", 3600)),
        llm_base_url=_resolve_env(llm.get("base_url", os.getenv("LLM_BASE_URL"))),
        llm_api_key=_resolve_env(llm.get("api_key", os.getenv("LLM_API_KEY"))),
        llm_model=_resolve_env(llm.get("model", os.getenv("LLM_MODEL") or "gpt-4o-mini")),
        embedding_model=_resolve_env(llm.get("embedding_model", os.getenv("EMBED_MODEL") or "text-embedding-3-small")),
        llm_max_retries=int(llm.get("max_retries", 3)),
        llm_retry_backoff_seconds=float(llm.get("retry_backoff_seconds", 1.0)),
        embedding_cache_dir=llm.get("embedding_cache_dir", ".repomemoir-cache"),
        embedding_cache_ttl_seconds=int(llm.get("embedding_cache_ttl_seconds", 604800)),
        output_dir=output.get("dir", "./memoirs"),
        output_format=output.get("format", "markdown"),
        analysis=analysis,
    )
