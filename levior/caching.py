import asyncio
import traceback
from io import BytesIO
from typing import Union, Optional

from trimgmi import Document as GmiDocument

from yarl import URL
import diskcache


def cache_key_for_url(url: URL) -> str:
    """
    Return the diskcache key for this URL, stripped of its optional
    fragment and user auth/password attributes.
    """
    return str(url.with_fragment(None).with_user(None).with_password(None))


def cache_resource(cache: diskcache.Cache,
                   url: URL, ctype: str, data,
                   ttl: Union[int, float] = None) -> bool:
    """
    Cache the content associated with a URL
    """
    try:
        lifetime = None

        if isinstance(ttl, (int, float)):
            if ttl >= 0:
                lifetime = int(ttl)
            elif ttl < 0:
                # Negative ttl = never lifetime
                lifetime = None

        cache.set(cache_key_for_url(url),
                  (ctype, data, None),
                  expire=lifetime, retry=True)

        return True
    except Exception:
        traceback.print_exc()
        return False


# The default diskcache key for the main access log
global_access_log_key: str = 'main_access_log'

# Tag for access log cache entries
access_log_tag: str = 'access_log'


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

    try:
        for line in access_log.emit_trim_gmi():
            fd.write(f'{line}\n'.encode())

        fd.seek(0, 0)  # needed

        return cache.set(key, fd, tag=access_log_tag, expire=expire, read=True)
    except Exception:
        traceback.print_exc()


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
    except (diskcache.Timeout, AssertionError):
        return GmiDocument()
    except Exception:
        traceback.print_exc()
        return None


async def cache_persist_task(cache: diskcache.Cache,
                             access_log: GmiDocument) -> None:
    while True:
        await asyncio.sleep(3)

        if access_log._scount > 0:
            cache_access_log(cache, access_log)

            access_log._scount = 0
