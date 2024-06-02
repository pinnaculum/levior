from dataclasses import dataclass
from omegaconf import DictConfig
from typing import Optional, List, Mapping
import asyncio
import aiohttp
import logging
import re
import traceback

from aiogemini import GEMINI_PORT

from pathlib import Path
from urllib.parse import urlparse
from urllib.parse import urljoin
from yarl import URL
from markdownify import MarkdownConverter

from .web import random_useragent
from .web import get_proxy_connector


try:
    from requests_html import HTML
    from requests_html import AsyncHTMLSession
    have_rhtml = True
except Exception:  # pragma: no cover
    have_rhtml = False

rhtml_session = None
ctypes_html: list = ['text/html', 'application/xhtml+xml']
user_agent_default: str = 'Mozilla/5.0 (X11; Linux x86_64; rv:54.0) Gecko/20100101 Firefox/64.0'  # noqa
scripts_re = re.compile(r'(?s)<(script).*?</\1>', re.MULTILINE)


logger = logging.getLogger()


@dataclass(frozen=True)
class RedirectRequired(Exception):
    url: URL


async def on_request_start(session, trace_config_ctx, params):
    trace_config_ctx.request_start = asyncio.get_event_loop().time()


async def on_request_end(session, trace_config_ctx, params):
    elapsed_time = round((
        asyncio.get_event_loop().time() - trace_config_ctx.request_start
    ) * 1000)

    print(f'Req time: {elapsed_time} msecs, '
          f'headers: {dict(params.response.request_info.headers)}')


async def fetch(url: URL,
                config: DictConfig,
                url_config,
                proxy_url: Optional[URL] = None,
                proxy_chain: Optional[List] = None,
                trace: bool = False,
                verify_ssl: bool = True,
                allow_redirects: bool = False,
                http_headers: Optional[Mapping[str, str]] = {},
                user_agent: Optional[str] = None) -> tuple:
    """
    :param URL url: The requested URL
    :param DictConfig config: Configuration
    :param bool verify_ssl: Verify SSL certificate validity
    :param str user_agent: HTTP user agent
    :rtype: tuple
    """

    global rhtml_session

    headers = {
        'User-Agent': user_agent if isinstance(user_agent, str) else
        random_useragent()
    }  # pragma: no cover

    if isinstance(http_headers, dict):
        for header, value in http_headers.items():
            if isinstance(value, str):
                headers[header] = value

    if proxy_url:
        connector = get_proxy_connector(proxy_url)
    else:
        connector = aiohttp.TCPConnector(
            limit=20,
            limit_per_host=5,
            use_dns_cache=False,
            force_close=True
        )

    if trace:
        trace_config = aiohttp.TraceConfig()
        trace_config.on_request_start.append(on_request_start)
        trace_config.on_request_end.append(on_request_end)
    else:
        trace_config = None

    if url.scheme in ['ipfs', 'ipns']:  # pragma: no cover
        # ipfs URL. Route through dweb.link's HTTP gateway

        url = URL.build(
            scheme='https',
            host=f'{url.host}.{url.scheme}.dweb.link',
            path=url.path,
            query=url.query,
            fragment=url.fragment
        )

    async with aiohttp.ClientSession(
            trace_configs=[trace_config] if trace_config else [],
            connector=connector) as session:
        try:
            async with session.get(url, headers=headers,
                                   allow_redirects=allow_redirects,
                                   verify_ssl=verify_ssl) as response:
                location = response.headers.get('Location')

                if location and response.status in range(300, 310):
                    # Catch redirects so that we can notify the gemini browser
                    raise RedirectRequired(url=URL(location))

                if response.status != 200:
                    return response, None, None, None

                ctypeh = response.headers.get('Content-Type')
                ctype = ctypeh.split(';').pop(0)
                clength = int(response.headers.get('Content-Length', 0))

                if ctype not in ctypes_html:
                    return response, ctype, clength, await response.read()

                try:
                    jsmatch = None
                    html_text = await response.text()

                    use_jsr = (config.js_render and url_config.get(
                        'js_render', False))

                    if have_rhtml and use_jsr:
                        jsmatch = scripts_re.search(html_text)

                    if have_rhtml and (jsmatch or config.js_render_always):
                        # Use requests-html to render the JS code

                        if rhtml_session is None:
                            # No session yet, create one
                            rhtml_session = AsyncHTMLSession()

                        rhtml = HTML(html=html_text, session=rhtml_session)
                        await rhtml.arender()

                        return response, ctype, clength, rhtml.html

                    return response, ctype, clength, html_text
                except Exception:
                    # Revert to ISO-8859-1 if chardet fails

                    logger.warning(traceback.format_exc())

                    return response, ctype, clength, \
                        await response.text('ISO-8859-1')

        except (aiohttp.ClientProxyConnectionError,
                aiohttp.ClientConnectorError) as err:
            raise err
        except Exception as err:
            raise err


class BaseConverter(MarkdownConverter):
    banned = [
        'script',
        'style',
        'form',
        'input'
    ]

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.domain = kw.pop('domain', None)
        self.req_path = kw.pop('req_path', '/')

        for tag in self.banned:
            setattr(self, f'convert_{tag}', self._gone)

    def _gone(self, el, text, convert_as_inline):
        return ''


class ZimConverter(BaseConverter):  # pragma: no cover
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.mp = kw.pop('mountp', '/')

    def _rewrite(self, url_string: str):
        url = urlparse(url_string)

        if not url.scheme:
            rp = Path(self.req_path)
            p = Path(self.mp).joinpath(rp.parent).joinpath(url.path)

            return URL.build(
                path=str(p),
                query=url.query,
                encoded=True
            )
        else:
            return URL(url_string)

        return None


class PageConverter(BaseConverter):
    banned = [
        'script',
        'style',
        'form',
        'input'
    ]

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

        self.config = kw.pop('levior_config')
        self.url_config = kw.pop('url_config')
        self.domain = kw.pop('domain', None)
        self.http_proxy_mode = kw.pop('http_proxy_mode', False)
        self.setup()

    def setup(self):
        # Tags to totally forget about

        for tag in self.url_config.get('html_tags_ban', []) + self.banned:
            setattr(self, f'convert_{tag}', self._gone)

        if self.feathers in range(0, 1):
            self.url_config['http_links_domains'] = [self.domain]

    @property
    def feathers(self):
        f = self.url_config.get('feathers')
        if isinstance(f, int):
            return f

        return self.config.get('feathers_default', 4)

    @property
    def links_domains(self):
        return self.url_config.get('http_links_domains', [])

    def convert_tr(self, el, text, convert_as_inline):
        return text

    def convert_img(self, el, text, convert_as_inline):
        if self.http_proxy_mode is True:
            # Don't rewrite in http proxy mode
            return super().convert_img(el, text, convert_as_inline)

        if self.feathers in range(0, 2) or \
                self.url_config.get('images') is False:
            # No images with 0-1 feathers
            return ''

        src = el.get('src', None)

        if not src:
            return super().convert_img(el, text, convert_as_inline)

        el['src'] = self._rewrite(src)
        return MarkdownConverter.convert_img(self, el, text, convert_as_inline)

    def convert_a(self, el, text, convert_as_inline):
        href = el.get('href', '')

        if self.http_proxy_mode is True:
            # Don't rewrite URLs in http proxy mode
            return super().convert_a(el, text, convert_as_inline)

        if not href or href.startswith('javascript'):
            return ''

        href = self._rewrite(href)
        if href is None:
            return ''

        el['href'] = href
        return MarkdownConverter.convert_a(self, el, text, convert_as_inline)

    def _rewrite(self, url_string: str):
        # Rewrite url_string to work with gemini

        ru, url = None, urlparse(url_string)

        if url.scheme == 'gemini':
            # No need to rewrite
            return url_string

        if url.scheme in ['data', 'ftp']:
            return None
        elif url.scheme in ['http', 'https'] and url.netloc:
            if self.links_domains and url.netloc not in self.links_domains:
                # links with a domain different from the
                # visited website are removed
                return None

            ru = URL.build(
                scheme='gemini',
                host=self.gemini_server_host,
                port=self.config.port if
                self.config.port != GEMINI_PORT else None,
                path='/' + url.netloc + url.path,
                query=url.query,
                encoded=True  # Critical
            )
        elif url.scheme == 'mailto':
            ru = URL.build(
                scheme='mailto',
                path=url.path if url.path else ''
            )
        else:
            ru = URL.build(
                scheme='gemini',
                host=self.gemini_server_host,
                port=self.config.port if
                self.config.port != GEMINI_PORT else None,
                path='/' + self.domain +
                urljoin(self.req_path, url.path if url.path else ''),
                query=url.query,
                encoded=True  # Critical
            )

        if ru:
            return str(ru)
        else:
            return url_string
