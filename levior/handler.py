import asyncio
import logging
import re
import sys
import traceback
from yarl import URL
from pathlib import Path
from typing import Tuple
from datetime import datetime

from aiogemini import Status
from aiogemini.server import _RequestHandler, Request, Response

import diskcache

from md2gemini import md2gemini

from omegaconf import OmegaConf
from omegaconf import DictConfig

from trimgmi import Document as GmiDocument

from IPy import IP

from . import crawler
from . import feed2gem
from . import mounts
from . import caching

from .filters import run_gemtext_filters

from .request import log_request
from .request import get_req_ipaddr
from .request import ipaddr_allowed

from .response import http_crawler_error_response
from .response import data_response
from .response import data_response_init
from .response import error_response
from .response import input_response
from .response import redirect_response
from .response import proxy_reqrefused_response
from .response import markdownification_error


logger = logging.getLogger()


def get_url_config(config: DictConfig,
                   rules: list,
                   url: URL) -> dict:
    url_config = {
        'cache': False,
        'ttl': config.cache_ttl_default
    }

    for rule in rules:
        if any(reg.search(str(url)) for reg in rule.regexps):
            url_config.update(rule.config)

            # First hit wins
            break

    return url_config


def gemtext_title_extract(gemtext: str) -> str:
    for line in gemtext.splitlines():
        ma = re.match(r'^#\s(.*)$', line)
        if ma:
            return ma.group(1)


def page_prepend_actions(config: DictConfig,
                         gemtext: str,
                         url: URL) -> str:
    """
    Add links for caching a page at the beginning of a gemtext document
    """

    actions: str = ''

    forever_query = dict(url.query)
    forever_query[caching.query_cache_forever_key] = 'true'

    for ttl_day in range(1,
                         config.get('page_cachelinks_maxdays', 14),
                         config.get('page_cachelinks_daystep', 3)):
        orig_query = dict(url.query)
        orig_query[caching.query_cachettl_key] = str(86400 * ttl_day)

        actions += f'=> {url.with_query(orig_query)} ' + \
            f'Cache this page for {ttl_day} day(s)\n'

    actions += f'=> {url.with_query(forever_query)}  Cache this page forever\n'

    return actions + gemtext


async def build_response(req: Request,
                         config: DictConfig,
                         url_config: dict,
                         cache,
                         rsc_ctype: str,
                         data: bytes,
                         domain: str = None,
                         gemini_server_host: str = None,
                         is_cached: bool = False,
                         proxy_mode: bool = False,
                         req_path: str = None) -> Tuple[Response, str]:
    """
    Build a gemini response for a request made on a levior instance

    :param Request req: Gemini request
    :param DictConfig config: Levior config
    :param dict url_config: Matching URL rule
    :param cache: Disk cache
    :param str rsc_ctype: Resource content type
    :param bytes data: Resource data as bytes
    :param bool is_cached: Cached status in disk cache for this URL
    """

    fdoc: GmiDocument = None
    loop = asyncio.get_event_loop()
    gemtext: str = None
    doc_title: str = None

    url_cache: bool = cache and not is_cached and url_config.get('cache')
    links_mode: str = url_config.get('links_mode', config.links_mode)
    cache_ttl = None

    try:
        cache_ttl = int(url_config.get('ttl', config.cache_ttl_default))
    except (TypeError, ValueError):
        cache_ttl = config.cache_ttl_default
    except BaseException:
        traceback.print_exc()

    # Look for a cache ttl option in the query
    try:
        if req.url.query.get(caching.query_cache_forever_key):
            url_cache = True
            cache_ttl = -1
        else:
            url_q_cachettl = int(req.url.query.get(
                caching.query_cachettl_key)
            )
            assert url_q_cachettl > 0

            url_cache = True
            cache_ttl = url_q_cachettl
    except (AssertionError, TypeError, ValueError):
        pass

    gemtext_filters = url_config.get('gemtext_filters', [])

    if rsc_ctype in ['application/xml',
                     'application/x-rss+xml',
                     'application/rss+xml',
                     'text/xml',
                     'application/atom+xml']:
        # Atom or RSS feed: return a tinylog if we manage to convert it

        tinyl = await loop.run_in_executor(
            None,
            feed2gem.feed2tinylog,
            data.decode()
        )

        if tinyl:
            return (await data_response(req, tinyl.encode(), 'text/gemini'),
                    None)
        else:
            return (await data_response(req, data, rsc_ctype), None)
    elif rsc_ctype in crawler.ctypes_html:
        # HTML => Markdown => gemtext

        conv = crawler.PageConverter(
            domain=domain,
            http_proxy_mode=proxy_mode,
            url_config=url_config,
            levior_config=config,
            autolinks=False,
            wrap=True,
            wrap_width=80
        )

        conv.req_path = req_path if req_path else req.url.path

        if gemini_server_host:
            conv.gemini_server_host = gemini_server_host

        md = conv.convert(data)

        if not md:
            return (await markdownification_error(req, req.url), None)

        gemtext = md2gemini(
            md,
            links=links_mode if links_mode else 'paragraph',
            checklist=False,
            strip_html=True,
            plain=True
        )

        if not gemtext:
            return (await error_response(
                req,
                f'Geminification of {req.url} resulted in an empty document'
            ), None)

        doc_title = gemtext_title_extract(gemtext)

        if gemtext_filters:
            # Construct a GmiDocument with what we received
            doc = GmiDocument()
            for line in gemtext.splitlines():
                doc.append(line)

            # Run the filters on the document
            fdoc = await run_gemtext_filters(
                doc, OmegaConf.to_container(gemtext_filters)
            )
            await asyncio.sleep(0)

            gemtext = '\n'.join(
                [geml for geml in fdoc.emit_trim_gmi()]
            )

        # Prepend the cache links if this page is not cached
        if not is_cached and config.get('page_cachelinks_show', False) is True:
            gemtext = page_prepend_actions(config, gemtext, req.url)

        if url_cache:
            caching.cache_resource(cache, req.url, rsc_ctype, data,
                                   ttl=cache_ttl)

        return (await data_response(req, gemtext.encode(), 'text/gemini'),
                doc_title)
    else:
        if data:
            if not is_cached and url_cache:
                caching.cache_resource(cache, req.url, rsc_ctype, data,
                                       ttl=cache_ttl)

            return (await data_response(req, data, rsc_ctype),
                    doc_title)
        else:
            return (await error_response(req, 'Empty page'), None)


async def build_cache_listing(req: Request,
                              config: DictConfig,
                              cache: diskcache.Cache) -> Response:
    """
    List all the entries in the cache and show the content's URL
    and its expiration time for each entry.
    """

    gemtext: str = '# Cache entries\n'

    for key in list(cache.iterkeys()):
        try:
            exp_dt, url = None, URL(key)
            assert url.scheme

            entry, expires = cache.get(key, expire_time=True)

            if expires:
                exp_dt = datetime.fromtimestamp(expires)

            gemtext += f'=> {url}  {url} '

            if exp_dt:
                gemtext += f'(expires: {exp_dt})\n'
            else:
                gemtext += '(no expiration date)\n'
        except BaseException:
            continue

    return await data_response(req, gemtext.encode(), 'text/gemini')


async def feeds_aggregate(req: Request,
                          config: DictConfig,
                          cache: diskcache.Cache,
                          url_config: dict,
                          gemini_server_host: str = None) -> Response:
    feed_only_idx: int
    gemtext: str = None
    feeds: list = []

    feeds_config = url_config.get('feeds')
    sort_mode = url_config.get('sort_mode', 'date')

    try:
        # If an integer is passed in the query, only the feed
        # corresponding to this index will be shown
        feed_only_idx: int = int(list(req.url.query.keys()).pop(0)) if \
            req.url.query else -1
    except (ValueError, TypeError):
        feed_only_idx = -1

    for feed_idx, (feed_url, feed_config) in enumerate(feeds_config.items()):
        # Skip this feed if it doesn't match the requested feed index
        if feed_only_idx >= 0 and feed_idx != feed_only_idx:
            continue

        # Skip this feed if it's disabled
        if feed_config.get('enabled', True) is False:
            continue

        feed = None

        # Feed cache expire (in seconds)
        cache_expire_time: int = feed_config.get('expire_time',
                                                 3600 * 24 * 3)

        # Cache vars
        cache_key = f'feedc_{feed_url}'
        cached_etag, cached_lastm = None, None
        cached = cache.get(cache_key)

        try:
            if cached:
                cached_etag = cached.get('etag')
                cached_lastm = cached.get('last-modified')

            resp, data, feed, etag, lastm = await feed2gem.feed_fromurl(
                URL(feed_url),
                etag=cached_etag,
                last_modified=cached_lastm,
                timeout=feed_config.get('req_timeout', 10),
                socks_proxy_url=config.socks5_proxy
            )

            if feed and feed['entries']:
                # TODO: check that the feed can be serialized before caching it

                cache.set(cache_key, {
                    'etag': etag,
                    'last-modified': lastm,
                    'feed': feed
                }, expire=cache_expire_time)

                feed.feed_config = feed_config
                feeds.append(feed)
        except (feed2gem.FeedNotModified,
                asyncio.CancelledError,
                asyncio.TimeoutError):
            """
            Not modified, or timeout.
            If the feed had been cached, serve that.
            """

            if cached and 'feed' in cached:
                feed = cached['feed']
                feed.feed_config = feed_config
                feeds.append(feed)

            continue
        except BaseException:
            traceback.print_exc()

    try:
        assert len(feeds) > 0

        gemtext = feed2gem.feeds2tinylog(feeds, sort_mode=sort_mode)
        return await data_response(req, gemtext.encode(), 'text/gemini')
    except AssertionError:
        return await error_response(req, 'No valid feeds were found')
    except BaseException:
        return await error_response(req, 'Failed to aggregate feeds')


def server_geminize_url(config: DictConfig, url: URL) -> str:
    if url.scheme == 'gemini':
        return url

    return URL.build(
        scheme='gemini',
        host=config.hostname,
        path=f'/{url.host}{url.path}',
        query=url.query,
        fragment=url.fragment
    )


def get_custom_reply(url_config: DictConfig) -> DictConfig:
    cresp = url_config.get('response')

    if isinstance(cresp, DictConfig) and 'status' in cresp:
        return cresp


async def send_custom_reply(req: Request, cresp: DictConfig) -> Response:
    rstatus = Status.SUCCESS
    reason = cresp.get('reason')
    content = cresp.get('text')

    if isinstance(cresp.status, str):
        try:
            rstatus = getattr(Status, cresp.status)
        except AttributeError:
            pass

    resp = data_response_init(req, status=rstatus)
    if isinstance(reason, str):
        resp.reason = reason

    if isinstance(content, str):
        await resp.write(content.encode())

    await resp.write_eof()
    return resp


def create_levior_handler(config: DictConfig,
                          cache: diskcache.Cache,
                          rules,
                          access_log: GmiDocument = None) -> _RequestHandler:
    loop = asyncio.get_event_loop()
    mountpoints: dict = {}

    access_log_doc: GmiDocument = access_log if access_log else GmiDocument()
    access_log_doc._scount = 0

    if config.get('cache_access_log', False) is True:
        loop.create_task(caching.cache_persist_task(cache, access_log_doc))

    ipfilter_allow: list = [
        IP(ip) for ip in config.get('client_ip_allow', [])
    ]

    if config.get('tor') is True:
        socksp_url = 'socks5://localhost:9050'
    else:
        socksp_url = config.socks5_proxy

    for mpath, mcfg in config.get('mount', {}).items():
        _type = mcfg.pop('type', None)

        if _type == 'zim' and mounts.have_zim is True:
            _path = mcfg.pop('path', None)
            if not _path:
                continue

            zmp = mounts.ZimMountPoint(mpath, Path(_path), **mcfg)

            if zmp.setup():
                mountpoints[mpath] = zmp
                print(f'Mounted zim file {_path} on: {mpath}', file=sys.stderr)
            else:
                print(f'Cannot mount zim file: {_path}', file=sys.stderr)

    async def handle_request_server_mode(req: Request) -> Response:
        """
        Server mode handler

        :param Request req: The incoming gemini request
        :rtype: Response
        """

        reqd = datetime.now()

        if req.url.scheme != 'gemini':
            return await error_response(
                req,
                'Levior is running in server mode, requested URLs must use '
                'the gemini:// URL scheme'
            )

        url_config = get_url_config(config, rules, req.url)

        cresp = get_custom_reply(url_config)
        if cresp:
            return await send_custom_reply(req, cresp)

        sp = req.url.path.split('/')
        pparts = [x for x in sp if x != '']

        rule_type = url_config.get('type')

        if rule_type in ['feed_aggregator', 'feeds_aggregator']:
            resp = await feeds_aggregate(req, config, cache, url_config)
            log_request(access_log_doc, req, reqd, resp, url_config)
            return resp

        if len(pparts) == 0 and not req.url.query:
            return await input_response(req, 'Please enter a domain to visit')
        elif len(pparts) == 0 and req.url.query:
            keys = list(req.url.query.keys())
            if keys:
                domain = keys.pop(0)
                return await redirect_response(
                    req,
                    server_geminize_url(config, URL(f'https://{domain}'))
                )
            else:
                return await error_response(req, 'Empty query')
        elif len(pparts) == 1 and pparts[0] == 'search':
            q = list(req.url.query.keys())
            if not q:
                return await input_response(req, 'Please enter a search query')

            term = q.pop(0)

            return await redirect_response(
                req,
                server_geminize_url(
                    config,
                    URL(f'https://searx.be/search?q={term}')
                )
            )
        elif len(pparts) == 1 and pparts[0] == 'access_log' and config.get(
                'access_log_endpoint', False) is True:
            data = '# Access log\n'
            data += '\n'.join(
                reversed([gmi for gmi in access_log_doc.emit_trim_gmi()]))
            data += f'\n{datetime.utcnow()}'
            return await data_response(req, data.encode())
        elif len(pparts) == 1 and pparts[0] == 'cache':
            return await build_cache_listing(req, config, cache)
        elif len(pparts) > 0:
            domain = pparts[0]

            # Check mounts

            for mp, mount in mountpoints.items():
                if mp == f'/{domain}':
                    return await mount.handle_request(req, config)

        path = '/' + '/'.join(pparts[1:]) if len(pparts) > 1 else '/'
        if req.url.path.endswith('/') and not path.endswith('/'):
            path += '/'

        url = URL.build(
            scheme='https',
            host=domain,
            path=path,
            query=req.url.query,
            fragment=req.url.fragment
        )
        url_http = url.with_scheme('http')

        resp, rsc_ctype, rsc_clength, data = None, None, None, None
        cached = cache.get(caching.cache_key_for_url(url)) if cache else None

        if cached:
            rsc_ctype, data, _ = cached
        else:
            try_urls = [url] if \
                config.get('https_only', False) else [url, url_http]

            for try_url in try_urls:
                try:
                    resp, rsc_ctype, rsc_clength, data = await crawler.fetch(
                        try_url,
                        config,
                        url_config,
                        socks_proxy_url=socksp_url,
                        verify_ssl=config.verify_ssl,
                        user_agent=config.get('http_user_agent')
                    )
                except crawler.RedirectRequired as redirect:
                    return await redirect_response(
                        req,
                        server_geminize_url(config, redirect.url)
                    )
                except Exception:
                    continue
                else:
                    break

            if not resp:
                return await error_response(
                    req,
                    f'Could not fetch {url} or {url_http}'
                )

            if not resp or not rsc_ctype or resp.status != 200:
                return await http_crawler_error_response(req, resp.status)

        resp, title = await build_response(
            req,
            config,
            url_config,
            cache,
            rsc_ctype,
            data,
            gemini_server_host=config.hostname,
            domain=domain,
            is_cached=cached is not None,
            req_path=path
        )

        log_request(access_log_doc, req, reqd, resp, url_config,
                    title=title)

        access_log_doc._scount += 1

        return resp

    async def handle_request_proxy_mode(req: Request) -> Response:
        """
        Handler for serving in http proxy mode

        :param Request req: The incoming gemini request
        :rtype: Response
        """

        reqd = datetime.utcnow()

        if req.url.scheme not in ['http', 'https', 'ipfs', 'ipns']:
            return await error_response(
                req, f'Unsupported URL scheme: {req.url.scheme}')

        url_config = get_url_config(config, rules, req.url)

        cresp = get_custom_reply(url_config)
        if cresp:
            return await send_custom_reply(req, cresp)

        cached = cache.get(
            caching.cache_key_for_url(req.url)) if cache else None

        if cached:
            rsc_ctype, data, _ = cached
        else:
            try:
                resp, rsc_ctype, rsc_clength, data = await crawler.fetch(
                    req.url,
                    config,
                    url_config,
                    socks_proxy_url=socksp_url,
                    verify_ssl=config.verify_ssl,
                    user_agent=config.get('http_user_agent')
                )
            except crawler.RedirectRequired as redirect:
                return await redirect_response(req, str(redirect.url))

            except Exception:
                return await error_response(req, traceback.format_exc())

            if not resp or not rsc_ctype or resp.status != 200:
                return await http_crawler_error_response(req, resp.status)

        resp, title = await build_response(
            req,
            config,
            url_config,
            cache,
            rsc_ctype,
            data,
            domain=req.url.host,
            is_cached=cached is not None,
            proxy_mode=True
        )

        log_request(access_log_doc, req, reqd, resp, url_config,
                    title=title)

        access_log_doc._scount += 1
        return resp

    async def handle_request(req: Request) -> Response:
        """
        Main entrypoint for requests.
        """

        client_ip: IP = get_req_ipaddr(req)

        if len(ipfilter_allow) > 0 and not ipaddr_allowed(
                client_ip, ipfilter_allow):
            # The client's IP is not allowed to access the service

            return await proxy_reqrefused_response(
                req,
                f'{req.url}: Your IP address ({client_ip}) is not allowed '
                'to access the service'
            )

        modes = config.get('mode', 'proxy,server').split(',')

        if req.url.scheme == 'gemini' and 'server' in modes:
            return await handle_request_server_mode(req)
        elif req.url.scheme in ['http', 'https', 'ipfs', 'ipns'] and \
                'proxy' in modes or 'http-proxy' in modes:
            return await handle_request_proxy_mode(req)
        else:
            # Return a PROXY_REQUEST_REFUSED response
            return await proxy_reqrefused_response(
                req,
                f'Unauthorized request for URL: {req.url}'
            )

    return handle_request
