import time

from repomemoir.extractors.github_cache import get_cached_payload, set_cached_payload


def test_cache_round_trip(tmp_path):
    cache_dir = str(tmp_path / "cache")
    set_cached_payload(cache_dir, "k1", {"a": 1})
    cached = get_cached_payload(cache_dir, "k1", ttl_seconds=10)
    assert cached == {"a": 1}


def test_cache_ttl_expiry(tmp_path):
    cache_dir = str(tmp_path / "cache")
    set_cached_payload(cache_dir, "k2", {"a": 1})
    time.sleep(0.01)
    cached = get_cached_payload(cache_dir, "k2", ttl_seconds=0)
    assert cached is None

