from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


def _to_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _from_iso(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


@dataclass
class CommitRecord:
    sha: str
    message: str
    author: str
    date: datetime
    files_changed: list[str]
    insertions: int
    deletions: int
    embedding: list[float] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["date"] = _to_iso(self.date)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CommitRecord":
        data = dict(payload)
        data["date"] = _from_iso(data.get("date"))
        return cls(**data)


@dataclass
class Chapter:
    title: str
    start_date: datetime
    end_date: datetime
    commits: list[CommitRecord]
    dominant_files: list[str]
    dominant_contributors: list[str]
    summary: str
    is_turning_point: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "start_date": _to_iso(self.start_date),
            "end_date": _to_iso(self.end_date),
            "commits": [c.to_dict() for c in self.commits],
            "dominant_files": self.dominant_files,
            "dominant_contributors": self.dominant_contributors,
            "summary": self.summary,
            "is_turning_point": self.is_turning_point,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Chapter":
        return cls(
            title=payload["title"],
            start_date=_from_iso(payload["start_date"]),
            end_date=_from_iso(payload["end_date"]),
            commits=[CommitRecord.from_dict(c) for c in payload.get("commits", [])],
            dominant_files=payload.get("dominant_files", []),
            dominant_contributors=payload.get("dominant_contributors", []),
            summary=payload.get("summary", ""),
            is_turning_point=payload.get("is_turning_point", False),
        )


@dataclass
class TurningPoint:
    date: datetime
    type: str
    description: str
    evidence: str
    impact: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["date"] = _to_iso(self.date)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TurningPoint":
        data = dict(payload)
        data["date"] = _from_iso(data.get("date"))
        return cls(**data)


@dataclass
class Contributor:
    handle: str
    commit_count: int
    influence_score: float
    core_areas: list[str]
    active_period: tuple[datetime, datetime]
    role: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "handle": self.handle,
            "commit_count": self.commit_count,
            "influence_score": self.influence_score,
            "core_areas": self.core_areas,
            "active_period": [_to_iso(self.active_period[0]), _to_iso(self.active_period[1])],
            "role": self.role,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Contributor":
        start, end = payload.get("active_period", [None, None])
        return cls(
            handle=payload["handle"],
            commit_count=payload.get("commit_count", 0),
            influence_score=payload.get("influence_score", 0.0),
            core_areas=payload.get("core_areas", []),
            active_period=(_from_iso(start), _from_iso(end)),
            role=payload.get("role", "maintainer"),
        )


@dataclass
class RepoMemoirDocument:
    repo: str
    generated_at: str
    last_commit_sha: str
    chapters: list[Chapter] = field(default_factory=list)
    turning_points: list[TurningPoint] = field(default_factory=list)
    contributors: list[Contributor] = field(default_factory=list)
    origin_intent: str = ""
    current_identity: str = ""
    open_threads: list[str] = field(default_factory=list)
    offline_mode: bool = False
    markdown: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo": self.repo,
            "generated_at": self.generated_at,
            "last_commit_sha": self.last_commit_sha,
            "chapters": [c.to_dict() for c in self.chapters],
            "turning_points": [tp.to_dict() for tp in self.turning_points],
            "contributors": [c.to_dict() for c in self.contributors],
            "origin_intent": self.origin_intent,
            "current_identity": self.current_identity,
            "open_threads": self.open_threads,
            "offline_mode": self.offline_mode,
            "markdown": self.markdown,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RepoMemoirDocument":
        return cls(
            repo=payload["repo"],
            generated_at=payload["generated_at"],
            last_commit_sha=payload["last_commit_sha"],
            chapters=[Chapter.from_dict(c) for c in payload.get("chapters", [])],
            turning_points=[TurningPoint.from_dict(tp) for tp in payload.get("turning_points", [])],
            contributors=[Contributor.from_dict(c) for c in payload.get("contributors", [])],
            origin_intent=payload.get("origin_intent", ""),
            current_identity=payload.get("current_identity", ""),
            open_threads=payload.get("open_threads", []),
            offline_mode=payload.get("offline_mode", False),
            markdown=payload.get("markdown", ""),
        )
