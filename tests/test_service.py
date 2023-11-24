from dataclasses import dataclass
from pathlib import Path
import hashlib
import pytest
import asyncio
import re

from yarl import URL
from omegaconf import OmegaConf
from md2gemini import md2gemini

from levior import default_cert_paths
from levior.handler import server_geminize_url
from levior.crawler import PageConverter
from levior.entrypoint import parse_args
from levior.__main__ import levior_configure_server
from levior.__main__ import get_config

from aiogemini import Status
from aiogemini.tofu import create_client_ssl_context
from aiogemini.client import Client
from aiogemini.client.protocol import Request
from aiogemini.client.protocol import Protocol


@dataclass
class ProxiedRequest(Request):
    proxy_url: URL


class LeviorClient(Client):
    def __init__(self):
        certs = default_cert_paths()

        super().__init__(
            create_client_ssl_context({}, certs[0], certs[1])
        )

    async def local_req(self, req_url: str):
        url = URL(req_url)

        req_url = URL('gemini://localhost').with_path(
            f'/{url.host}{url.path}'
        )

        return await self.send_request(Request(url=req_url))

    async def proxy_request(self,
                            requrl: URL,
                            proxy: tuple = ('localhost', 1965)):
        loop = asyncio.get_running_loop()
        protocol = Protocol(Request(url=URL(requrl)), loop=loop)

        await loop.create_connection(
            lambda: protocol,
            proxy[0],
            proxy[1],
            ssl=self.ssl
        )
        return await protocol.response


@pytest.fixture
def client():
    return LeviorClient()


@pytest.fixture
async def server():
    config, srv = levior_configure_server(parse_args(['--mode=server']))
    f = asyncio.ensure_future(srv.serve())
    await asyncio.sleep(2)
    yield srv
    f.cancel()


@pytest.fixture
async def proxy_server():
    config, srv = levior_configure_server(parse_args(['--mode=proxy']))
    assert config.mode == 'proxy'
    f = asyncio.ensure_future(srv.serve())
    await asyncio.sleep(2)
    yield srv
    f.cancel()


class TestURLs:
    def test_suburl(self):
        cfg = get_config(parse_args([]))
        url = server_geminize_url(cfg, URL('https://docs.aiohttp.org'))
        assert str(url) == 'gemini://localhost/docs.aiohttp.org/'


class TestCrawler:
    @pytest.mark.parametrize(
        'htmlsrc', [
            ('<a href="/test">Test</a>',
             '=> gemini://localhost/test.org/test Test'),
            ('<a href="/test/">Test</a>',
             '=> gemini://localhost/test.org/test/ Test'),
            ('<a href="test">Test</a>',
             '=> gemini://localhost/test.org/test Test'),
            ('<a href="https://docs.aiohttp.org">aiohttp</a>',
             '=> gemini://localhost/docs.aiohttp.org aiohttp'),
            ('<a href="gemini://geminispace.info">gs</a>',
             '=> gemini://geminispace.info gs'),
        ])
    def test_urls(self, htmlsrc):
        """
        Test URLs rewriting in server mode
        """
        conv = PageConverter(
            domain='test.org',
            http_proxy_mode=False,
            url_config={
                'cache': False,
                'ttl': 0
            },
            levior_config=get_config(parse_args(['--mode=server'])),
            autolinks=False,
            wrap=True,
            wrap_width=80
        )
        conv.gemini_server_host = 'localhost'

        l0 = md2gemini(
            conv.convert(htmlsrc[0]),
            checklist=False,
            strip_html=True,
            plain=True
        ).splitlines().pop(0)
        assert l0 == htmlsrc[1]


class TestLeviorConfig:
    def test_configuration(self, tmpdir):
        cfg = get_config(parse_args([]))
        assert cfg.hostname == 'localhost'
        assert cfg.port == 1965

        cfg = get_config(
            parse_args(['--daemonize', '--https-only', '--mode=proxy'])
        )

        assert cfg.daemonize is True
        assert cfg.https_only is True
        assert cfg.mode == 'proxy'

        cfgf = Path(tmpdir).joinpath('levior.yaml')

        cfg = OmegaConf.create({
            'daemonize': True
        })

        with open(cfgf, 'wt') as f:
            OmegaConf.save(cfg, f)

        cfg = get_config(parse_args(['-c', str(cfgf)]))
        assert cfg.daemonize is True


class TestLeviorModes:
    @pytest.mark.asyncio
    async def test_server_mode(self, server, client):
        # / must ask for an INPUT
        req = Request(url=URL('gemini://localhost'))
        resp = await client.send_request(req)
        assert resp.status == Status.INPUT

        # Fetch https://geminiprotocol.net and check that the links
        # are rewired to go through localhost

        resp = await client.local_req('https://geminiprotocol.net')
        assert resp.status == Status.SUCCESS
        assert resp.content_type.startswith('text/gemini')
        data = (await resp.read()).decode()

        for line in data.splitlines():
            lkm = re.search(r'^=> (gemini://localhost/.*?)\s(.*)$', line)
            if not lkm:
                continue

            url = URL(lkm.group(1))
            ps = url.path.lstrip('/').split('/')

            if url.scheme == 'gemini' and ps and ps[0] == 'geminiprotocol.net':
                assert url.host == 'localhost'

        resp = await client.local_req('https://freebsd.org')
        assert resp.status == Status.REDIRECT_TEMPORARY
        assert resp.reason == 'gemini://localhost/www.freebsd.org/'

        resp = await client.local_req('https://docs.aiohttp.org')
        assert resp.status == Status.REDIRECT_TEMPORARY
        assert resp.reason == 'gemini://localhost/docs.aiohttp.org/en/stable/'

        resp = await client.send_request(Request(url=URL(resp.reason)))
        data = (await resp.read()).decode()
        assert data.splitlines()[0].startswith('Welcome to AIOHTTP')

        # Test that the content type is properly set
        resp = await client.local_req(
            'https://www.freebsd.org/images/logo-red.png'
        )
        assert resp.status == Status.SUCCESS
        assert resp.content_type == 'image/png'

    @pytest.mark.asyncio
    async def test_proxy_https(self, proxy_server, client):
        resp = await client.proxy_request('https://docs.aiohttp.org')
        assert resp.status == Status.REDIRECT_TEMPORARY
        assert resp.reason == 'https://docs.aiohttp.org/en/stable/'

        resp = await client.proxy_request(resp.reason)
        assert resp.status == Status.SUCCESS
        data = (await resp.read()).decode()
        assert resp.content_type.startswith('text/gemini')
        assert data.splitlines()[0].startswith('Welcome to AIOHTTP')

    @pytest.mark.asyncio
    async def test_proxy_ipfs(self, proxy_server, client):
        # Fetch some IPFS file and verify the checksum
        h = hashlib.sha256()
        resp = await client.proxy_request(
            'ipfs://bafybeigrf2dwtpjkiovnigysyto3d55opf6qkdikx6d65onrqnfzwgdkfa'  # noqa
        )
        assert resp.status == Status.SUCCESS
        h.update(await resp.read())

        assert h.hexdigest() == \
            'c749ac31ca6e6b917bdbd4148a7c0fec6fea2aaa036211211bddf8d6ae4c33f4'

    @pytest.mark.asyncio
    async def test_proxy_feed(self, proxy_server, client):
        resp = await client.proxy_request('https://openrss.org/rss')
        assert resp.content_type.startswith('text/gemini')
