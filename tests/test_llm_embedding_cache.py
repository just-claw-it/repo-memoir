from repomemoir.llm import LLMClient


def test_embedding_cache_reuses_previous_result(tmp_path):
    calls = {"count": 0}

    class FakeLLM(LLMClient):
        def _post_json(self, path, payload, timeout):  # type: ignore[override]
            calls["count"] += 1
            return {"data": [{"embedding": [0.1, 0.2]} for _ in payload["input"]]}

    client = FakeLLM(
        base_url="https://example.com",
        api_key="x",
        model="m",
        embedding_model="e",
        embedding_cache_dir=str(tmp_path),
        embedding_cache_ttl_seconds=1000,
    )
    first = client.embed_texts(["hello"])
    second = client.embed_texts(["hello"])

    assert first == [[0.1, 0.2]]
    assert second == [[0.1, 0.2]]
    assert calls["count"] == 1

