import pytest

from freezegun import freeze_time

from yarl import URL
from omegaconf import OmegaConf
from trimgmi import Document as GmiDocument

from levior.caching import cache_access_log
from levior.caching import load_cached_access_log
from levior import caching


@pytest.fixture
def cache(tmpdir):
    return caching.configure_cache(OmegaConf.create({
        'cache_eviction_policy': 'least-recently-used',
        'cache_path': str(tmpdir.join('diskcache')),
        'cache_size_limit': int(1e6)
    }))


class TestCaching:
    @pytest.mark.parametrize('url', [
        URL('https://example.org/hello#frag1'),
        URL('https://me:pass@example.org/hello?test=1')
    ])
    def test_cachekey(self, url):
        ukey = URL(caching.cache_key_for_url(url))
        assert not ukey.fragment
        assert not ukey.user
        assert not ukey.password
        assert not ukey.query

    @pytest.mark.parametrize('url', [
        URL('https://cacheme.org/document.txt'),
        URL('https://docs.aiohttp.org/index.html#fragment')
    ])
    def test_cache_resource(self, cache, url):
        with freeze_time("2024-02-14 12:00:00") as ft:
            assert caching.cache_resource(
                cache, url, 'text/plain', 'Hello',
                ttl=60) is True

            val = cache.get(caching.cache_key_for_url(url))
            assert val[0] == 'text/plain'
            assert val[1] == 'Hello'

            ft.tick(60 * 10)
            assert cache.get(caching.cache_key_for_url(url)) is None

        with freeze_time("2024-02-24") as ft:
            assert caching.cache_resource(
                cache, url, 'text/plain', 'Hello')

            caching.cache_update_expiration(cache, url, 10)
            ft.tick(60)
            assert cache.get(caching.cache_key_for_url(url)) is None

        with freeze_time("2024-02-24") as ft:
            assert caching.cache_resource(
                cache, url, 'text/plain', 'Hello', ttl=-1)
            ft.tick(86400 * 365)
            assert cache.get(caching.cache_key_for_url(url)) is not None

    def test_access_log_cache(self, cache):
        log = GmiDocument()
        log.append('=> / Test')
        log.append('=> /doc Doc')

        assert cache_access_log(cache, log) is True

        clog = load_cached_access_log(cache)
        assert len(clog._lines) == 2
