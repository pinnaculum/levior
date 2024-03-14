import appdirs
import asyncio
import logging
import traceback

import diskcache
from pathlib import Path
from datetime import timedelta
from io import BytesIO
from typing import Union, Optional
from yarl import URL

from omegaconf import DictConfig
from trimgmi import Document as GmiDocument

from . import __appname__


logger = logging.getLogger()


# The URL query key used to set the cache ttl for a page
query_cachettl_key = 'levior_cache_ttl'

# The URL query key used to cache a page forever
query_cache_forever_key = 'levior_cache_forever'


# The default diskcache key for the main access log
global_access_log_key: str = 'main_access_log'

# Tag for access log cache entries
access_log_tag: str = 'access_log'

# Default cache size limit (in megabytes)
default_size_limit_mb: int = 2048


def humanize_seconds(seconds: int) -> str:
    return str(timedelta(seconds=seconds))


def default_cache_dir() -> str:
    return appdirs.user_cache_dir(__appname__)


def mbtobytes(size: Union[int, float]) -> float:
    return size * 1024 * 1024


def configure_cache(config: DictConfig) -> diskcache.Cache:
    cache_dir: Path = Path(
        config.cache_path if config.cache_path else default_cache_dir()
    )

    if not cache_dir.exists():
        cache_dir.mkdir(parents=True)

    if config.cache_eviction_policy in ['least-recently-stored',
                                        'least-recently-used',
                                        'least-frequently-used',
                                        'none']:
        cpolicy = config.cache_eviction_policy
    else:
        cpolicy = 'least-recently-stored'

    if isinstance(config.cache_size_limit, (int, float)) and \
       config.cache_size_limit > 0:
        size_limit_mb = config.cache_size_limit
    else:
        size_limit_mb = default_size_limit_mb

    return diskcache.Cache(
        str(cache_dir),
        eviction_policy=cpolicy,
        size_limit=mbtobytes(size_limit_mb)
    )


def cache_key_for_url(url: URL) -> str:
    """
    Return the diskcache key for this URL, stripped of its optional
    fragment, query and user auth/password attributes.
    """
    return str(url
               .with_fragment(None)
               .with_user(None)
               .with_password(None)
               .with_query(None))


def cache_resource(cache: diskcache.Cache,
                   url: URL, ctype: str, data,
                   ttl: Union[int, float] = None) -> bool:
    """
    Cache the content associated with a URL
    """
    lifetime = None

    if not isinstance(url, URL):
        raise ValueError('Invalid url parameter')

    cache_key: str = cache_key_for_url(url)

    if isinstance(ttl, (int, float)):
        if ttl >= 0:
            lifetime = int(ttl)
        elif ttl < 0:
            # Negative ttl = never lifetime
            lifetime = None

    if lifetime is None:
        logger.info(f'{cache_key}: cached forever')
    else:
        logger.info(
            f'{cache_key}: cached for {humanize_seconds(lifetime)}')

    return cache.set(cache_key,
                     (ctype, data, None),
                     expire=lifetime, retry=True)


def cache_update_expiration(cache: diskcache.Cache,
                            url: URL,
                            ttl: Union[int, float] = None) -> bool:
    """
    Update the expiration time for this url.
    """

    return cache.touch(cache_key_for_url(url), expire=ttl)


def cache_access_log(cache: diskcache.Cache,
                     access_log: GmiDocument,
                     key: str = None,
                     expire: float = None) -> bool:
    """
    Cache this access log in the diskcache

    :param GmiDocument access_log: Access log stored as a gmi document
    :param str key: cache key
    :param float expire: Cache lifetime in seconds
    """

    key: str = key if key else global_access_log_key
    fd = BytesIO()

    for line in access_log.emit_trim_gmi():
        fd.write(f'{line}\n'.encode())

    fd.seek(0, 0)  # needed

    return cache.set(key, fd, tag=access_log_tag, expire=expire, read=True)


def load_cached_access_log(cache: diskcache.Cache,
                           key: str = None) -> Optional[GmiDocument]:
    """
    Load the access log cached in the diskcache and return a trimgmi
    Document rebuilt from the cached bytes.
    """

    key: str = key if key else global_access_log_key
    doc = GmiDocument()

    try:
        fd = cache.get(key, read=True)
        assert fd is not None

        for lineb in fd.readlines():
            doc.append(lineb.decode())

        return doc
    except (diskcache.Timeout, AssertionError):  # pragma: no cover
        return GmiDocument()
    except BaseException:  # pragma: no cover
        traceback.print_exc()
        return None


async def cache_persist_task(cache: diskcache.Cache,
                             access_log: GmiDocument) -> None:
    while True:
        await asyncio.sleep(3)

        if access_log._scount > 0:
            cache_access_log(cache, access_log)

            access_log._scount = 0
