import aiohttp
from aiohttp_socks import ProxyConnector

from urllib.parse import urlparse
from yarl import URL
from markdownify import MarkdownConverter


ctypes_html = ['text/html', 'application/xhtml+xml']


async def fetch(url, socks_proxy_url=None):
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:33.0) '
                      'Gecko/20100101 Firefox/33.0'
    }

    if socks_proxy_url:
        connector = ProxyConnector.from_url(socks_proxy_url)
    else:
        connector = None

    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    return response, None, None

                ctypeh = response.headers.get('Content-Type')
                ctype = ctypeh.split(';').pop(0)

                if ctype in ctypes_html:
                    return response, ctype, await response.text()
                else:
                    return response, ctype, await response.read()
        except (aiohttp.ClientProxyConnectionError,
                aiohttp.ClientConnectorError) as err:
            raise err
        except Exception as err:
            raise err


class PageConverter(MarkdownConverter):
    banned = [
        'script',
        'style',
        'meta',
        'form',
        'input',
        'th'
    ]

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

        # Tags to totally forget about
        for tag in self.banned:
            setattr(self, f'convert_{tag}', self._gone)

    def _gone(self, el, text, convert_as_inline):
        return ''

    def convert_tr(self, el, text, convert_as_inline):
        return text

    def convert_img(self, el, text, convert_as_inline):
        src = el.get('src', None)

        if not src:
            return super().convert_img(el, text, convert_as_inline)

        el['src'] = self._rewrite(src)
        return super().convert_img(el, text, convert_as_inline)

    def convert_a(self, el, text, convert_as_inline):
        href = el.get('href', '')

        if not href or href.startswith('javascript'):
            return ''

        el['href'] = self._rewrite(href)
        return super().convert_a(el, text, convert_as_inline)

    def _rewrite(self, url_string: str):
        # Rewrite url_string to work with gemini

        ru, url = None, urlparse(url_string)

        if url.scheme in ['http', 'https'] and url.netloc:
            ru = URL.build(
                scheme='gemini',
                host=self.gemini_server_host,
                path='/' + url.netloc + url.path,
                fragment=url.fragment,
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
                path = url.path

            ru = URL.build(
                scheme='gemini',
                host=self.gemini_server_host,
                path='/' + self.domain + path,
                fragment=url.fragment,
                query=url.query,
                encoded=True  # Critical
            )

        if ru:
            return str(ru)
        else:
            return url_string
