from yarl import URL

from aiogemini import Status, GEMINI_MEDIA_TYPE
from aiogemini.server import _RequestHandler, Request, Response

from md2gemini import md2gemini

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


def create_levior_handler(args) -> _RequestHandler:
    try:
        if args.tor:
            host, port = 'localhost', 9050
        else:
            host, port = args.socks5_proxy.split(':')

        socksp_url = f'socks5://{host}:{port}'
    except Exception:
        socksp_url = None

    async def handle_request(req: Request) -> Response:
        sp = req.url.path.split('/')
        comps = [x for x in sp if x != '']

        if len(comps) == 0 and not req.url.query:
            return await input_response(req, 'Please enter a domain to visit')
        elif len(comps) == 0 and req.url.query:
            keys = list(req.url.query.keys())
            if keys:
                domain = keys.pop(0)
                return await redirect_response(
                    req, f'gemini://{args.hostname}/{domain}')
            else:
                return await error_response(req, 'Empty query')
        elif len(comps) == 1 and comps[0] == 'search':
            q = list(req.url.query.keys())
            if not q:
                return await input_response(req, 'Please enter a search query')

            term = q.pop(0)
            return await redirect_response(
                req,
                f'gemini://{args.hostname}/searx.be/search?q={term}'
            )
        else:
            domain = comps[0]

        path = '/' + '/'.join(comps[1:]) if len(comps) > 1 else '/'

        conv = crawler.PageConverter(
            levior_args=args,
            autolinks=False,
            wrap=True,
            wrap_width=80,
        )

        conv.domain = domain
        conv.req_path = path
        conv.gemini_server_host = args.hostname

        url = URL.build(
            scheme='http',
            host=domain,
            path=path,
            query=req.url.query,
            fragment=req.url.fragment
        )

        try:
            resp, rsc_ctype, data = await crawler.fetch(
                url,
                socks_proxy_url=socksp_url,
                verify_ssl=args.verify_ssl
            )
        except Exception as err:
            return await error_response(req, str(err))

        if not resp or not rsc_ctype or resp.status != 200:
            return await error_response(
                req, f'HTTP error code: {resp.status}')

        if rsc_ctype in crawler.ctypes_html:
            md = conv.convert(data)
            gemtext = md2gemini(
                md,
                links=args.md_links,
                checklist=False,
                strip_html=True,
                plain=True
            )

            if not gemtext:
                return await error_response(
                    req,
                    f'Geminification of {url} resulted in an empty document'
                )

            return await data_response(req, gemtext.encode(), 'text/gemini')
        else:
            if data:
                return await data_response(req, data, rsc_ctype)
            else:
                return await error_response(req, 'Empty page')

    return handle_request
