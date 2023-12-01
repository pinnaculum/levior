import asyncio
import sys
import re
import traceback
from yarl import URL
from pathlib import Path

from aiogemini.server import _RequestHandler, Request, Response

from md2gemini import md2gemini
import diskcache
from omegaconf import DictConfig

from . import crawler
from . import feed2gem
from . import mounts

from .response import data_response
from .response import error_response
from .response import input_response
from .response import redirect_response
from .response import proxy_reqrefused_response


def cache_resource(cache: diskcache.Cache,
                   url: URL, ctype: str, data,
                   ttl: float = 60.0 * 10):
    try:
        cache.add(str(url), (ctype, data, None), expire=ttl, retry=True)
        return True
    except Exception as err:
        print(err, file=sys.stderr)
        return False


def get_url_config(config: DictConfig, url: URL) -> dict:
    url_config = {
        'cache': False,
        'ttl': 0
    }

    for urlc in config.get('urules', []):
        mtype, urlre = urlc.get('mime'), urlc.get('regexp')
        if not urlre and not mtype:
            continue

        if isinstance(urlre, str) and re.search(urlre, str(url)):
            url_config.update(urlc)

            # First hit wins
            break

    return url_config


async def markdownification_error(req, url):
    return await error_response(
        req,
        f'Markdownification of {url} failed'
    )


async def build_response(req: Request,
                         config: DictConfig,
                         url_config: dict,
                         cache,
                         rsc_ctype: str,
                         data: bytes,
                         domain: str = None,
                         gemini_server_host: str = None,
                         cached: bool = False,
                         proxy_mode: bool = False,
                         req_path: str = None) -> Response:
    """
    Build a gemini response for a request made on a levior instance

    :param Request req: Gemini request
    :param DictConfig config: Levior config
    :param dict url_config: Matching URL rule
    :param cache: Disk cache
    :param str rsc_ctype: Resource content type
    :param bytes data: Resource data as bytes
    :param bool cached: Cached status in disl cache for this URL
    """

    loop = asyncio.get_event_loop()
    gemtext: str = None

    url_cache: bool = cache and not cached and url_config.get('cache')
    links_mode: str = url_config.get('links_mode', config.links_mode)

    try:
        cache_ttl = float(url_config.get('ttl', config.cache_ttl_default))
    except BaseException:
        cache_ttl = 60 * 10

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
            return await data_response(req, tinyl.encode(), 'text/gemini')
        else:
            return await data_response(req, data, rsc_ctype)
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
            return await markdownification_error(req, req.url)

        gemtext = md2gemini(
            md,
            links=links_mode if links_mode else 'paragraph',
            checklist=False,
            strip_html=True,
            plain=True
        )

        if not gemtext:
            return await error_response(
                req,
                f'Geminification of {req.url} resulted in an empty document'
            )
        else:
            if not req.url.query and url_cache:
                # Only cache documents with no query
                cache_resource(url_cache, req.url, rsc_ctype, data,
                               ttl=cache_ttl)

        return await data_response(req, gemtext.encode(), 'text/gemini')
    else:
        if data:
            if not cached and url_cache:
                cache_resource(url_cache, req.url, rsc_ctype, data,
                               ttl=cache_ttl)

            return await data_response(req, data, rsc_ctype)
        else:
            return await error_response(req, 'Empty page')


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


def create_levior_handler(config: DictConfig) -> _RequestHandler:
    try:
        if config.get('tor') is True:
            socksp_url = 'socks5://localhost:9050'
        else:
            socksp_url = config.socks5_proxy
    except Exception:
        socksp_url = None

    if config.cache_enable:
        cache = diskcache.Cache(config.get('cache_path', '/tmp/levior'))
    else:
        cache = None

    mountpoints = {}

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

        if req.url.scheme != 'gemini':
            return await error_response(
                req,
                'Levior is running in server mode, requested URLs must use '
                'the gemini:// URL scheme'
            )

        sp = req.url.path.split('/')
        comps = [x for x in sp if x != '']

        if len(comps) == 0 and not req.url.query:
            return await input_response(req, 'Please enter a domain to visit')
        elif len(comps) == 0 and req.url.query:
            keys = list(req.url.query.keys())
            if keys:
                domain = keys.pop(0)
                return await redirect_response(
                    req,
                    server_geminize_url(config, URL(f'https://{domain}'))
                )
            else:
                return await error_response(req, 'Empty query')
        elif len(comps) == 1 and comps[0] == 'search':
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
        elif len(comps) > 0:
            domain = comps[0]

            # Check mounts

            for mp, mount in mountpoints.items():
                if mp == f'/{domain}':
                    return await mount.handle_request(req, config)

        path = '/' + '/'.join(comps[1:]) if len(comps) > 1 else '/'
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
        cached = cache.get(str(url)) if cache else None

        if cached:
            rsc_ctype, data, _ = cached
        else:
            try_urls = [url] if \
                config.get('https_only', False) else [url, url_http]

            for try_url in try_urls:
                try:
                    resp, rsc_ctype, rsc_clength, data = await crawler.fetch(
                        try_url,
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
                return await error_response(
                    req, f'HTTP error code: {resp.status}')

        return await build_response(
            req,
            config,
            get_url_config(config, url),
            cache,
            rsc_ctype,
            data,
            gemini_server_host=config.hostname,
            domain=domain,
            cached=cached,
            req_path=path
        )

    async def handle_request_proxy_mode(req: Request) -> Response:
        """
        Handler for serving in http proxy mode

        :param Request req: The incoming gemini request
        :rtype: Response
        """

        if req.url.scheme not in ['http', 'https', 'ipfs', 'ipns']:
            return await error_response(
                req, f'Unsupported URL scheme: {req.url.scheme}')

        cached = cache.get(str(req.url)) if cache else None
        if cached:
            rsc_ctype, data, _ = cached
        else:
            try:
                resp, rsc_ctype, rsc_clength, data = await crawler.fetch(
                    req.url,
                    socks_proxy_url=socksp_url,
                    verify_ssl=config.verify_ssl,
                    user_agent=config.get('http_user_agent')
                )
            except crawler.RedirectRequired as redirect:
                return await redirect_response(req, str(redirect.url))

            except Exception:
                return await error_response(req, traceback.format_exc())

            if not resp or not rsc_ctype or resp.status != 200:
                return await error_response(
                    req, f'HTTP error code: {resp.status}')

        return await build_response(
            req,
            config,
            get_url_config(config, req.url),
            cache,
            rsc_ctype,
            data,
            domain=req.url.host,
            cached=cached,
            proxy_mode=True
        )

    async def handle_request(req: Request) -> Response:
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
