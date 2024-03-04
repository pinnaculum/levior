from diskcache import Cache
from trimgmi import Document as GmiDocument

from levior.caching import cache_access_log
from levior.caching import load_cached_access_log


class TestCaching:
    def test_access_log_cache(self):
        cache = Cache()

        log = GmiDocument()
        log.append('=> / Test')
        log.append('=> /doc Doc')

        assert cache_access_log(cache, log) is True

        clog = load_cached_access_log(cache)
        assert len(clog._lines) == 2
