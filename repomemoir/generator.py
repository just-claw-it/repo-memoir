from __future__ import annotations

from datetime import datetime, timezone

from repomemoir.llm import LLMClient
from repomemoir.models import Chapter, Contributor, RepoMemoirDocument, TurningPoint

INFERENCE_HINT_WORDS = ("likely", "probably", "appears", "seems", "suggests", "maybe", "perhaps")


class StrictGroundingError(ValueError):
    """Raised when strict grounding validation fails in fail-fast mode."""


def _chapter_prompt(repo: str, chapter: Chapter) -> str:
    commit_list = "\n".join(f"- [{c.date.date()}] {c.author}: {c.message}" for c in chapter.commits[:200])
    return f"""Given these commits from {chapter.start_date.date()} to {chapter.end_date.date()} in repo {repo}:
{commit_list}

These files were most changed: {', '.join(chapter.dominant_files)}
These contributors were most active: {', '.join(chapter.dominant_contributors)}

Write a 2-3 paragraph narrative chapter about this period.
Focus on: what was being built, why (infer from commit messages),
what problems were being solved. Do not fabricate - only use
what is in the data. If you infer, prefix sentence with "[Inference]".
End with an "Evidence used:" line listing 3-6 commit bullets or facts.
"""


def _turning_point_prompt(repo: str, tp: TurningPoint) -> str:
    return f"""This event occurred in repo {repo} on {tp.date.date()}:
{tp.evidence}

Interpret this turning point: what changed architecturally,
what does this suggest about the project's direction at this moment?
2-3 sentences only. Ground everything in the evidence provided.
If you infer, prefix sentence with "[Inference]".
"""


def _chapter_title_prompt(repo: str, chapter: Chapter) -> str:
    commit_list = "\n".join(f"- {c.message}" for c in chapter.commits[:25])
    return f"""Create a concise chapter title for repo {repo}.
Date window: {chapter.start_date.date()} to {chapter.end_date.date()}
Commits:
{commit_list}

Rules:
- 4-8 words
- Concrete and specific, no clichés
- No punctuation at the end
- Return title only
"""


def validate_grounding_text(text: str, *, require_evidence_line: bool) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return False, ["empty text"]

    if require_evidence_line and not any(line.lower().startswith("evidence used:") for line in lines):
        reasons.append("missing 'Evidence used:' line")

    for line in lines:
        lower = line.lower()
        if any(word in lower for word in INFERENCE_HINT_WORDS) and "[inference]" not in lower:
            reasons.append("contains inferred language without [Inference] marker")
            break

    return len(reasons) == 0, reasons


def _repair_grounding_text(llm: LLMClient, text: str, reasons: list[str], *, require_evidence_line: bool) -> str:
    evidence_instruction = (
        "You MUST end with one line beginning exactly with 'Evidence used:'." if require_evidence_line else ""
    )
    prompt = f"""Rewrite the text to satisfy strict evidence-grounding rules.

Rules:
- Keep same meaning and scope as the original text.
- Any inferred statement must start with "[Inference]".
- No fabricated facts.
{evidence_instruction}

Validation failures:
- {'; '.join(reasons)}

Original text:
{text}
"""
    return llm.complete(prompt)


def _enforce_or_repair_grounding(
    llm: LLMClient,
    text: str,
    *,
    require_evidence_line: bool,
    fail_fast: bool,
    section_label: str,
) -> str:
    ok, reasons = validate_grounding_text(text, require_evidence_line=require_evidence_line)
    if ok:
        return text
    if fail_fast:
        raise StrictGroundingError(f"{section_label} failed strict grounding checks: {'; '.join(reasons)}")
    return _repair_grounding_text(llm, text, reasons, require_evidence_line=require_evidence_line)


def generate_chapter_content(
    repo_name: str,
    chapter: Chapter,
    llm: LLMClient,
    *,
    strict_grounding: bool,
    strict_grounding_fail_fast: bool,
) -> Chapter:
    chapter.title = llm.complete(_chapter_title_prompt(repo_name, chapter)).strip().strip('"')
    chapter.summary = llm.complete(_chapter_prompt(repo_name, chapter))
    if strict_grounding:
        chapter.summary = _enforce_or_repair_grounding(
            llm,
            chapter.summary,
            require_evidence_line=True,
            fail_fast=strict_grounding_fail_fast,
            section_label=f"chapter '{chapter.title}'",
        )
    return chapter


def generate_turning_point_interpretation(
    repo_name: str,
    turning_point: TurningPoint,
    llm: LLMClient,
    *,
    strict_grounding: bool,
    strict_grounding_fail_fast: bool,
) -> TurningPoint:
    turning_point.impact = llm.complete(_turning_point_prompt(repo_name, turning_point))
    if strict_grounding:
        turning_point.impact = _enforce_or_repair_grounding(
            llm,
            turning_point.impact,
            require_evidence_line=False,
            fail_fast=strict_grounding_fail_fast,
            section_label=f"turning point '{turning_point.type}'",
        )
    return turning_point


def generate_assembly_text(
    repo_name: str,
    origin_intent: str,
    current_identity: str,
    open_threads: list[str],
    llm: LLMClient,
    *,
    strict_grounding: bool,
    strict_grounding_fail_fast: bool,
) -> str:
    assembly_prompt = f"""You are assembling a repo memoir.

Repo: {repo_name}
Origin intent signals: {origin_intent}
Current identity signals: {current_identity}
Open threads: {open_threads}

Write:
1) Intro paragraph
2) Identity comparison section (what it became vs what it was)
3) Open threads summary paragraph
Keep claims grounded and mark inference explicitly.
Format inferences with "[Inference]".
"""
    assembly = llm.complete(assembly_prompt)
    if strict_grounding:
        assembly = _enforce_or_repair_grounding(
            llm,
            assembly,
            require_evidence_line=False,
            fail_fast=strict_grounding_fail_fast,
            section_label="assembly",
        )
    return assembly


def generate_memoir(
    repo_name: str,
    chapters: list[Chapter],
    turning_points: list[TurningPoint],
    contributors: list[Contributor],
    origin_intent: str,
    current_identity: str,
    open_threads: list[str],
    llm: LLMClient,
    last_commit_sha: str,
    strict_grounding: bool = False,
    strict_grounding_fail_fast: bool = False,
    offline_mode: bool = False,
) -> RepoMemoirDocument:
    if strict_grounding_fail_fast and not strict_grounding:
        raise StrictGroundingError("strict_grounding_fail_fast requires strict_grounding=True")

    for chapter in chapters:
        generate_chapter_content(
            repo_name,
            chapter,
            llm,
            strict_grounding=strict_grounding,
            strict_grounding_fail_fast=strict_grounding_fail_fast,
        )

    for tp in turning_points:
        generate_turning_point_interpretation(
            repo_name,
            tp,
            llm,
            strict_grounding=strict_grounding,
            strict_grounding_fail_fast=strict_grounding_fail_fast,
        )

    assembly = generate_assembly_text(
        repo_name,
        origin_intent,
        current_identity,
        open_threads,
        llm,
        strict_grounding=strict_grounding,
        strict_grounding_fail_fast=strict_grounding_fail_fast,
    )

    generated_at = datetime.now(timezone.utc).isoformat()
    markdown = render_markdown(
        repo_name,
        generated_at,
        chapters,
        turning_points,
        contributors,
        origin_intent,
        current_identity,
        open_threads,
        assembly,
        offline_mode=offline_mode,
    )

    return RepoMemoirDocument(
        repo=repo_name,
        generated_at=generated_at,
        last_commit_sha=last_commit_sha,
        chapters=chapters,
        turning_points=turning_points,
        contributors=contributors,
        origin_intent=origin_intent,
        current_identity=current_identity,
        open_threads=open_threads,
        offline_mode=offline_mode,
        markdown=markdown,
    )


def render_markdown(
    repo: str,
    generated_at: str,
    chapters: list[Chapter],
    turning_points: list[TurningPoint],
    contributors: list[Contributor],
    origin_intent: str,
    current_identity: str,
    open_threads: list[str],
    assembly_text: str,
    offline_mode: bool = False,
) -> str:
    first_year = chapters[0].start_date.year if chapters else datetime.now(timezone.utc).year
    total_commits = sum(len(c.commits) for c in chapters)

    lines = [
        f"# The Repo Memoir of {repo}",
        "",
        f"*A living document. Last updated: {generated_at}. {total_commits} commits analyzed.*",
        "",
    ]
    if offline_mode:
        lines.extend(
            [
                "> **Mode:** Offline algorithmic mode (no external LLM or GitHub API calls).",
                "",
            ]
        )
    lines.extend(
        [
        "---",
        "",
        f"## Origins ({first_year})",
        "",
        origin_intent,
        "",
        ]
    )

    for chapter in chapters:
        lines.extend(
            [
                f"## {chapter.title} ({chapter.start_date.date()} - {chapter.end_date.date()})",
                "",
                chapter.summary or "No narrative generated.",
                "",
                f"**Evidence markers:** {min(6, len(chapter.commits))} commit references analyzed in this chapter.",
                "",
            ]
        )

        chapter_points = [tp for tp in turning_points if chapter.start_date <= tp.date <= chapter.end_date]
        for point in chapter_points:
            lines.extend(
                [
                    f"> **Turning Point:** {point.description}",
                    f"> **Evidence:** {point.evidence}",
                    f"> **Interpretation:** {point.impact}",
                    "",
                ]
            )

    lines.extend(
        [
            "---",
            "",
            "## Key Figures",
            "",
        ]
    )
    for contributor in contributors[:10]:
        start, end = contributor.active_period
        lines.extend(
            [
                f"**{contributor.handle}** - *{contributor.role}* - Shaped `{', '.join(contributor.core_areas)}` from {start.date()} to {end.date()}.",
                f"Influence score: {contributor.influence_score}",
                "",
            ]
        )

    lines.extend(
        [
            "---",
            "",
            "## What It Became vs What It Was",
            "",
            current_identity,
            "",
            "---",
            "",
            "## Open Threads",
            "",
            "Issues and debates still unresolved that shaped the codebase:",
            "",
        ]
    )

    if open_threads:
        lines.extend([f"- **{thread}**" for thread in open_threads])
    else:
        lines.append("- No open threads detected.")

    lines.extend(
        [
            "",
            "---",
            "",
            "*Generated by repo-memoir. All claims grounded in git history, PRs, and issues. Inferences explicitly marked.*",
            "",
            "<!-- assembly -->",
            assembly_text,
        ]
    )
    return "\n".join(lines)
