from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


def _cache_path(cache_dir: str, key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return Path(cache_dir) / f"{digest}.json"


def get_cached_payload(cache_dir: str, key: str, ttl_seconds: int) -> Any | None:
    path = _cache_path(cache_dir, key)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return None

    cached_at = payload.get("cached_at", 0)
    if time.time() - cached_at > ttl_seconds:
        return None
    return payload.get("data")


def set_cached_payload(cache_dir: str, key: str, data: Any) -> None:
    path = _cache_path(cache_dir, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"cached_at": time.time(), "data": data}
    path.write_text(json.dumps(payload))
