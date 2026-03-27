from datetime import datetime, timezone

import pytest

from repomemoir.generator import StrictGroundingError, generate_memoir, validate_grounding_text
from repomemoir.models import Chapter, CommitRecord, Contributor, TurningPoint


def test_validate_grounding_requires_evidence_line():
    ok, reasons = validate_grounding_text(
        "This likely improved reliability.\nEvidence used: commit A; commit B",
        require_evidence_line=True,
    )
    assert not ok
    assert "contains inferred language without [Inference] marker" in reasons


def test_validate_grounding_accepts_marked_inference_and_evidence():
    ok, reasons = validate_grounding_text(
        "[Inference] This likely improved reliability.\nEvidence used: commit A; commit B",
        require_evidence_line=True,
    )
    assert ok
    assert reasons == []


def test_validate_grounding_flags_missing_evidence_line():
    ok, reasons = validate_grounding_text(
        "Concrete summary with no inference.",
        require_evidence_line=True,
    )
    assert not ok
    assert "missing 'Evidence used:' line" in reasons


class _BadLLM:
    def complete(self, prompt: str, system: str = "x") -> str:
        if "Create a concise chapter title" in prompt:
            return "Bad Title"
        if "Given these commits" in prompt:
            return "This likely changed architecture."
        if "This event occurred in repo" in prompt:
            return "It probably changed direction."
        return "Assembly likely reflects new scope."


def _sample_inputs():
    now = datetime.now(timezone.utc)
    commit = CommitRecord(
        sha="abc",
        message="do thing",
        author="alice",
        date=now,
        files_changed=["src/a.py"],
        insertions=5,
        deletions=1,
        embedding=[0.1, 0.2],
    )
    chapter = Chapter(
        title="Chapter 1",
        start_date=now,
        end_date=now,
        commits=[commit],
        dominant_files=["src/a.py"],
        dominant_contributors=["alice"],
        summary="",
    )
    tp = TurningPoint(date=now, type="pivot", description="desc", evidence="evidence", impact="")
    contributor = Contributor(
        handle="alice",
        commit_count=1,
        influence_score=3.0,
        core_areas=["src"],
        active_period=(now, now),
        role="maintainer",
    )
    return [chapter], [tp], [contributor]


def test_fail_fast_requires_strict_enabled():
    chapters, points, contributors = _sample_inputs()
    with pytest.raises(StrictGroundingError):
        generate_memoir(
            repo_name="owner/repo",
            chapters=chapters,
            turning_points=points,
            contributors=contributors,
            origin_intent="origin",
            current_identity="current",
            open_threads=[],
            llm=_BadLLM(),
            last_commit_sha="abc",
            strict_grounding=False,
            strict_grounding_fail_fast=True,
        )


def test_fail_fast_raises_on_invalid_generated_content():
    chapters, points, contributors = _sample_inputs()
    with pytest.raises(StrictGroundingError):
        generate_memoir(
            repo_name="owner/repo",
            chapters=chapters,
            turning_points=points,
            contributors=contributors,
            origin_intent="origin",
            current_identity="current",
            open_threads=[],
            llm=_BadLLM(),
            last_commit_sha="abc",
            strict_grounding=True,
            strict_grounding_fail_fast=True,
        )

