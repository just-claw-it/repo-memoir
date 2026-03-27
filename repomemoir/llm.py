from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Sequence

import requests


class LLMClient:
    def __init__(
        self,
        base_url: str | None,
        api_key: str | None,
        model: str,
        embedding_model: str,
        *,
        max_retries: int = 3,
        retry_backoff_seconds: float = 1.0,
        embedding_cache_dir: str | None = None,
        embedding_cache_ttl_seconds: int = 7 * 24 * 3600,
    ):
        self.base_url = (base_url or "https://api.openai.com").rstrip("/")
        self.api_key = api_key
        self.model = model
        self.embedding_model = embedding_model
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.embedding_cache_dir = embedding_cache_dir
        self.embedding_cache_ttl_seconds = embedding_cache_ttl_seconds

    @property
    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _post_json(self, path: str, payload: dict, timeout: int) -> dict:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(
                    f"{self.base_url}{path}",
                    headers=self._headers,
                    json=payload,
                    timeout=timeout,
                )
                response.raise_for_status()
                return response.json()
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(self.retry_backoff_seconds * (2**attempt))
        if last_error:
            raise last_error
        raise RuntimeError("Unexpected retry loop termination")

    def _embedding_cache_path(self, text: str) -> Path | None:
        if not self.embedding_cache_dir:
            return None
        key = f"{self.embedding_model}:{text}".encode("utf-8")
        digest = hashlib.sha256(key).hexdigest()
        path = Path(self.embedding_cache_dir) / "embeddings" / f"{digest}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _load_cached_embedding(self, text: str) -> list[float] | None:
        path = self._embedding_cache_path(text)
        if not path or not path.exists():
            return None
        try:
            payload = json.loads(path.read_text())
        except Exception:
            return None
        cached_at = payload.get("cached_at", 0)
        if time.time() - cached_at > self.embedding_cache_ttl_seconds:
            return None
        return payload.get("embedding")

    def _save_cached_embedding(self, text: str, embedding: list[float]) -> None:
        path = self._embedding_cache_path(text)
        if not path:
            return
        path.write_text(json.dumps({"cached_at": time.time(), "embedding": embedding}))

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        ordered = list(texts)
        resolved: list[list[float] | None] = [None] * len(ordered)
        misses: list[tuple[int, str]] = []

        for idx, text in enumerate(ordered):
            cached = self._load_cached_embedding(text)
            if cached is not None:
                resolved[idx] = cached
            else:
                misses.append((idx, text))

        if misses:
            miss_texts = [text for _, text in misses]
            data = self._post_json(
                "/v1/embeddings",
                {"model": self.embedding_model, "input": miss_texts},
                timeout=60,
            )["data"]
            fresh = [item["embedding"] for item in data]
            for (idx, text), embedding in zip(misses, fresh, strict=True):
                resolved[idx] = embedding
                self._save_cached_embedding(text, embedding)

        return [item for item in resolved if item is not None]

    def complete(self, prompt: str, *, system: str = "You are a careful software historian.") -> str:
        payload = self._post_json(
            "/v1/chat/completions",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            },
            timeout=90,
        )
        return payload["choices"][0]["message"]["content"].strip()


class OfflineLLMClient(LLMClient):
    """Deterministic local fallback that avoids external API calls."""

    def __init__(self):
        super().__init__(
            base_url="offline://local",
            api_key=None,
            model="offline",
            embedding_model="offline-embedding",
            max_retries=0,
            retry_backoff_seconds=0,
            embedding_cache_dir=None,
            embedding_cache_ttl_seconds=0,
        )

    def _offline_vector(self, text: str, dim: int = 16) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values: list[float] = []
        for i in range(dim):
            byte = digest[i % len(digest)]
            values.append((byte / 255.0) * 2 - 1)
        return values

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:  # type: ignore[override]
        return [self._offline_vector(text) for text in texts]

    def complete(self, prompt: str, *, system: str = "You are a careful software historian.") -> str:  # type: ignore[override]
        lower = prompt.lower()
        if "create a concise chapter title" in lower:
            return "Algorithmic Development Phase"
        if "given these commits" in lower:
            return (
                "This chapter is generated in offline mode from commit metadata only. "
                "It summarizes likely implementation focus based on commit messages and changed files.\n\n"
                "Evidence used: commit messages, dominant files, dominant contributors."
            )
        if "this event occurred in repo" in lower:
            return "Offline interpretation: event indicates a likely architectural shift inferred from commit evidence."
        return "Offline mode assembly summary from local signals only."
