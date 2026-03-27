from repomemoir.cli import _load_remote_signals
from repomemoir.llm import OfflineLLMClient


class _Cfg:
    github_token = None
    github_cache_dir = ".repomemoir-cache"
    github_cache_ttl_seconds = 3600


def test_offline_llm_embeddings_deterministic():
    llm = OfflineLLMClient()
    first = llm.embed_texts(["hello world"])
    second = llm.embed_texts(["hello world"])
    assert first == second
    assert len(first[0]) == 16


def test_load_remote_signals_offline_skips_remote():
    prs, issues, readme = _load_remote_signals("owner/repo", _Cfg(), no_cache=False, offline=True)
    assert prs == []
    assert issues == []
    assert readme == ""

