import sys
import re
import traceback
from yarl import URL
from pathlib import Path

from aiogemini.server import _RequestHandler, Request, Response

from md2gemini import md2gemini
import diskcache

from . import crawler
from .response import data_response
from .response import error_response
from .response import input_response
from .response import redirect_response
from . import mounts


def cache_resource(cache: diskcache.Cache,
                   url: URL, ctype: str, data,
                   ttl: float = 60.0 * 10):
    try:
        cache.add(str(url), (ctype, data, None), expire=ttl, retry=True)
        return True
    except Exception as err:
        print(err, file=sys.stderr)
        return False


async def markdownification_error(req, url):
    return await error_response(
        req,
        f'Markdownification of {url} failed'
    )


def create_levior_handler(config) -> _RequestHandler:
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
        gemtext = None
        sp = req.url.path.split('/')
        comps = [x for x in sp if x != '']

        if len(comps) == 0 and not req.url.query:
            return await input_response(req, 'Please enter a domain to visit')
        elif len(comps) == 0 and req.url.query:
            keys = list(req.url.query.keys())
            if keys:
                domain = keys.pop(0)
                return await redirect_response(
                    req, f'gemini://{config.hostname}/{domain}')
            else:
                return await error_response(req, 'Empty query')
        elif len(comps) == 1 and comps[0] == 'search':
            q = list(req.url.query.keys())
            if not q:
                return await input_response(req, 'Please enter a search query')

            term = q.pop(0)
            return await redirect_response(
                req,
                f'gemini://{config.hostname}/searx.be/search?q={term}'
            )
        elif len(comps) > 0:
            domain = comps[0]

            # Check mounts

            for mp, mount in mountpoints.items():
                if mp == f'/{domain}':
                    return await mount.handle_request(req, config)

        path = '/' + '/'.join(comps[1:]) if len(comps) > 1 else '/'

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

        # Get the config for the URL

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

        url_cache = cache and not cached and url_config.get('cache')
        links_mode = url_config.get('links_mode', config.links_mode)

        try:
            ttl = float(url_config.get('ttl', config.cache_ttl_default))
        except BaseException:
            ttl = 60 * 10

        if rsc_ctype in crawler.ctypes_html:
            if not gemtext:
                conv = crawler.PageConverter(
                    domain=domain,
                    url_config=url_config,
                    levior_config=config,
                    autolinks=False,
                    wrap=True,
                    wrap_width=80,
                )

                conv.req_path = path
                conv.gemini_server_host = config.hostname

                md = conv.convert(data)

                if not md:
                    return await markdownification_error(req, url)

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
                    f'Geminification of {url} resulted in an empty document'
                )
            else:
                if not url.query and url_cache:
                    # Only cache documents with no query
                    cache_resource(cache, url, rsc_ctype, data,
                                   ttl=ttl)

            return await data_response(req, gemtext.encode(), 'text/gemini')
        else:
            if data:
                if not cached and url_cache:
                    cache_resource(cache, url, rsc_ctype, data,
                                   ttl=ttl)

                return await data_response(req, data, rsc_ctype)
            else:
                return await error_response(req, 'Empty page')

    async def handle_request_proxy_mode(req: Request) -> Response:
        """
        Handler for serving in http proxy mode
        """

        gemtext = None
        domain = req.url.host
        path = req.url.path

        if req.url.scheme not in ['http', 'https']:
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
            except Exception:
                return await error_response(req, traceback.format_exc())

            if not resp or not rsc_ctype or resp.status != 200:
                return await error_response(
                    req, f'HTTP error code: {resp.status}')

        # Get the config for the URL

        url_config = {
            'cache': False,
            'ttl': 0
        }

        for urlc in config.get('urules', []):
            mtype, urlre = urlc.get('mime'), urlc.get('regexp')
            if not urlre and not mtype:
                continue

            if isinstance(urlre, str) and re.search(urlre, str(req.url)):
                url_config.update(urlc)

                # First hit wins
                break

        url_cache = cache and not cached and url_config.get('cache')
        links_mode = url_config.get('links_mode', config.links_mode)

        try:
            ttl = float(url_config.get('ttl', config.cache_ttl_default))
        except BaseException:
            ttl = 60 * 10

        if rsc_ctype in crawler.ctypes_html:
            if not gemtext:
                conv = crawler.PageConverter(
                    domain=domain,
                    http_proxy_mode=True,
                    url_config=url_config,
                    levior_config=config,
                    autolinks=False,
                    wrap=True,
                    wrap_width=80
                )

                conv.req_path = path

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
                    f'Geminification of {req.url} resulted in '
                    'an empty document'
                )
            else:
                if not req.url.query and url_cache:
                    # Only cache documents with no query
                    cache_resource(cache, req.url, rsc_ctype, data,
                                   ttl=ttl)

            return await data_response(req, gemtext.encode(), 'text/gemini')
        else:
            if data:
                if not cached and url_cache:
                    cache_resource(cache, req.url, rsc_ctype, data,
                                   ttl=ttl)

                return await data_response(req, data, rsc_ctype)
            else:
                return await error_response(req, 'Empty page')

    if config.get('mode', 'server') in ['proxy', 'http-proxy']:
        print('levior: Serving in http proxy mode', file=sys.stderr)
        return handle_request_proxy_mode
    else:
        print(f'levior: Built gemini service handler for: {config.hostname}',
              file=sys.stderr)
        return handle_request_server_mode
