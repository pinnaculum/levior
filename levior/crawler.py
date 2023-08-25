import aiohttp
from aiohttp_socks import ProxyConnector

from pathlib import Path
from urllib.parse import urlparse
from yarl import URL
from markdownify import MarkdownConverter


ctypes_html = ['text/html', 'application/xhtml+xml']


async def fetch(url, socks_proxy_url=None, verify_ssl=True):
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux; rv:74.0) '
                      'Gecko/20100101 Firefox/74.0'
    }

    if socks_proxy_url:
        connector = ProxyConnector.from_url(socks_proxy_url)
    else:
        connector = None

    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            async with session.get(url, headers=headers,
                                   verify_ssl=verify_ssl) as response:
                if response.status != 200:
                    return response, None, None, None

                ctypeh = response.headers.get('Content-Type')
                ctype = ctypeh.split(';').pop(0)
                clength = int(response.headers.get('Content-Length', 0))

                if ctype in ctypes_html:
                    try:
                        return response, ctype, clength, await response.text()
                    except Exception:
                        # Revert to ISO-8859-1 if chardet fails
                        return response, ctype, clength, \
                            await response.text('ISO-8859-1')
                else:
                    return response, ctype, clength, await response.read()
        except (aiohttp.ClientProxyConnectionError,
                aiohttp.ClientConnectorError) as err:
            raise err
        except Exception as err:
            raise err


class BaseConverter(MarkdownConverter):
    banned = [
        'script',
        'style',
        'meta',
        'form',
        'input'
    ]

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.domain = kw.pop('domain', None)
        self.req_path = kw.pop('req_path', None)

        for tag in self.banned:
            setattr(self, f'convert_{tag}', self._gone)

    def _gone(self, el, text, convert_as_inline):
        return ''

    def convert_a(self, el, text, convert_as_inline):
        href = el.get('href', '')

        if not href or href.startswith('javascript'):
            return ''

        href = self._rewrite(href)
        if href is None:
            return ''

        el['href'] = href
        return super().convert_a(el, text, convert_as_inline)

    def convert_img(self, el, text, convert_as_inline):
        src = el.get('src', None)

        if not src:
            return super().convert_img(el, text, convert_as_inline)

        el['src'] = self._rewrite(src)
        return super().convert_img(el, text, convert_as_inline)


class ZimConverter(BaseConverter):
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
        'meta',
        'form',
        'input'
    ]

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

        self.config = kw.pop('levior_config')
        self.url_config = kw.pop('url_config')
        self.domain = kw.pop('domain', None)
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
            if not url.path:
                path = self.req_path.rstrip('/')
            else:
                path = '/' + url.path if not \
                    url.path.startswith('/') else url.path

            ru = URL.build(
                scheme='gemini',
                host=self.gemini_server_host,
                path='/' + self.domain + path,
                query=url.query,
                encoded=True  # Critical
            )

        if ru:
            return str(ru)
        else:
            return url_string
