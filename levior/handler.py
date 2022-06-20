import sys
import re
import traceback
from yarl import URL

from aiogemini import Status, GEMINI_MEDIA_TYPE
from aiogemini.server import _RequestHandler, Request, Response

from md2gemini import md2gemini
import diskcache

from . import crawler


async def data_response(req, data, content_type=GEMINI_MEDIA_TYPE,
                        status=Status.SUCCESS):
    response = Response()
    response.content_type = content_type
    response.status = status
    response.start(req)
    await response.write(data)
    await response.write_eof()
    return response


async def input_response(req, text: str):
    response = Response()
    response.reason = f'{text}'
    response.status = Status.INPUT
    response.start(req)
    await response.write(text.encode())
    await response.write_eof()
    return response


async def redirect_response(req, url):
    response = Response()
    response.reason = url
    response.status = Status.REDIRECT_TEMPORARY
    response.start(req)
    await response.write_eof()
    return response


async def error_response(req, message: str, content_type=GEMINI_MEDIA_TYPE):
    return await data_response(req, message.encode())


def cache_resource(cache: diskcache.Cache,
                   url: URL, ctype: str, data,
                   ttl: float = 60.0 * 10):
    try:
        cache.add(str(url), (ctype, data, None), expire=ttl, retry=True)
        return True
    except Exception as err:
        print(err, file=sys.stderr)
        return False


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

    async def handle_request(req: Request) -> Response:
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
        else:
            domain = comps[0]

        path = '/' + '/'.join(comps[1:]) if len(comps) > 1 else '/'

        url = URL.build(
            scheme='http',
            host=domain,
            path=path,
            query=req.url.query,
            fragment=req.url.fragment
        )

        cached = cache.get(str(url)) if cache else None
        if cached:
            rsc_ctype, data, _ = cached
        else:
            try:
                resp, rsc_ctype, rsc_clength, data = await crawler.fetch(
                    url,
                    socks_proxy_url=socksp_url,
                    verify_ssl=config.verify_ssl
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

        for urlc in config.urules:
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

                gemtext = md2gemini(
                    conv.convert(data),
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

    return handle_request
