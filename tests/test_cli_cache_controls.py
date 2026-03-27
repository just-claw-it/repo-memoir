from dataclasses import dataclass

from repomemoir.cli import _cache_options


@dataclass
class _Cfg:
    github_cache_dir: str = ".repomemoir-cache"
    github_cache_ttl_seconds: int = 3600


def test_cache_options_use_defaults_when_enabled():
    cache_dir, ttl = _cache_options(_Cfg(), no_cache=False)
    assert cache_dir == ".repomemoir-cache"
    assert ttl == 3600


def test_cache_options_disable_cache_when_no_cache_flag():
    cache_dir, ttl = _cache_options(_Cfg(), no_cache=True)
    assert cache_dir is None
    assert ttl == 0

