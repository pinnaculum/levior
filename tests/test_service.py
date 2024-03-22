from dataclasses import dataclass
from pathlib import Path
from typing import Union

import tempfile
import hashlib
import pytest
import asyncio
import os
import re
import urllib
import signal
import shutil

from yarl import URL
from omegaconf import OmegaConf
from md2gemini import md2gemini

from levior import default_cert_paths
from levior import caching
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

from trimgmi import LineType
from trimgmi import Document


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
                            requrl: Union[URL, str],
                            proxy: tuple = ('localhost', 1965)):
        loop = asyncio.get_running_loop()
        protocol = Protocol(
            Request(url=URL(requrl) if isinstance(requrl, str) else requrl),
            loop=loop
        )

        await loop.create_connection(
            lambda: protocol,
            proxy[0],
            proxy[1],
            ssl=self.ssl
        )
        resp = await protocol.response
        return resp, await resp.read()

    async def proxy_request_gmidoc(self,
                                   requrl: Union[URL, str],
                                   proxy: tuple = ('localhost', 1965)):
        doc = Document()
        resp, data = await self.proxy_request(requrl, proxy)
        [doc.append(line) for line in data.decode().splitlines()]
        return resp, doc

    async def request_gmidoc(self, requrl: URL):
        doc = Document()
        resp = await self.send_request(Request(url=requrl))
        data = await resp.read()
        [doc.append(line) for line in data.decode().splitlines()]
        return resp, doc


def pythonclock_rw(fctx):
    # Basic rewriting filter

    if fctx.line.type == LineType.HEADING1 and \
       fctx.line.text.startswith('Python 2.7 will retire in'):
        return '# Python never retires'


@pytest.fixture
def config_with_filters(tmpdir):
    cfg = OmegaConf.create({
        'urules': [
            {
                'regexp': 'https://searx.be/search',
                'gemtext_filters': [
                    'levior.filters.links:strip_emailaddrs'
                ]
            },
            {
                'regexp': 'https://pythonclock.org',
                'gemtext_filters': [
                    'tests.test_service:pythonclock_rw'
                ]
            }
        ]
    })

    cfgp = Path(tmpdir).joinpath('srv1_rules.yaml')

    with open(cfgp, 'wt') as fd:
        OmegaConf.save(cfg, fd)

    return cfgp


@pytest.fixture
def config_with_includes(tmpdir):
    zimp = Path(tmpdir).joinpath('alpine.zim')

    with urllib.request.urlopen(
        'https://download.kiwix.org/zim/other/alpinelinux_en_all_nopic_2023-01.zim') as response:  # noqa
        with open(zimp, 'wb') as zim_file:
            shutil.copyfileobj(response, zim_file)

    cfg = OmegaConf.create({
        'persist_access_log': True,
        'access_log_endpoint': True,
        'mount': {
            '/alpine': {
                'type': 'zim',
                'path': str(zimp)
            }
        },
        'include': [
            {
                'src': 'levior:puretext.yaml',
                'with': {
                    'URL': [
                        'https://searx.be'
                    ]
                }
            },
            {
                'src': 'levior:sites/francetvinfo.yaml',
                'with': {
                    'ftvinfo_feeds': {
                        'sports': True
                    }
                }
            }
        ]
    })

    cfgp = Path(tmpdir).joinpath('srv2_includes.yaml')

    with open(cfgp, 'wt') as fd:
        OmegaConf.save(cfg, fd)

    return cfgp


@pytest.fixture
def config_with_includes_all(tmpdir):
    cfg = OmegaConf.create({
        'include': [
            {
                'src': 'levior:sites/*.yaml',
                'with': {
                    'ftvinfo_feeds': {
                        'sports': True
                    }
                }
            }
        ]
    })

    cfgp = Path(tmpdir).joinpath('srv3_includes_all.yaml')

    with open(cfgp, 'wt') as fd:
        OmegaConf.save(cfg, fd)

    return cfgp


@pytest.fixture
def client():
    return LeviorClient()


def server_mode_args():
    return parse_args(['--mode=server'])


def proxy_mode_args():
    return parse_args(['--mode=proxy'])


def mixed_mode_cachelinks_args():
    return parse_args(['--mode=proxy,server', '--page-cachelinks',
                       f'--cache-path={tempfile.mkdtemp()}'])


def mixed_mode_args():
    return parse_args(['--mode=proxy,server'])


async def service_with_args(args):
    config, srv = levior_configure_server(args)
    f = asyncio.ensure_future(srv.serve())
    await asyncio.sleep(1)
    return f, config, srv


@pytest.fixture
async def server():
    f, config, srv = await service_with_args(server_mode_args())
    yield srv
    f.cancel()


@pytest.fixture
async def proxy_server():
    f, config, srv = await service_with_args(proxy_mode_args())
    assert config.mode == 'proxy'
    yield srv
    f.cancel()


@pytest.fixture
async def mixed_server_with_cachelinks():
    f, config, srv = await service_with_args(mixed_mode_cachelinks_args())
    yield srv
    f.cancel()


@pytest.fixture
async def proxy_server_with_filters(config_with_filters):
    f, config, srv = await service_with_args(
        parse_args(['--mode=proxy', '-c', str(config_with_filters)])
    )
    yield srv
    f.cancel()


@pytest.fixture
async def proxy_server_with_includes(config_with_includes):
    f, config, srv = await service_with_args(
        parse_args(['--mode=proxy', '-c', str(config_with_includes)])
    )
    yield srv
    f.cancel()


@pytest.fixture
async def proxy_server_with_js():
    f, config, srv = await service_with_args(
        parse_args(['--mode=proxy', '--js', '--js-force'])
    )
    yield srv
    f.cancel()


@pytest.fixture
async def mixed_server_with_includes(config_with_includes):
    f, config, srv = await service_with_args(
        parse_args(['-c', str(config_with_includes)])
    )
    yield srv
    f.cancel()


@pytest.fixture
async def mixed_server_with_all_sites(config_with_includes_all):
    f, config, srv = await service_with_args(
        parse_args(['-c', str(config_with_includes_all)])
    )
    yield srv
    f.cancel()


@pytest.fixture
async def mixed_server():
    f, config, srv = await service_with_args(mixed_mode_args())
    yield srv
    f.cancel()


class TestURLs:
    def test_suburl(self):
        cfg, rules = get_config(parse_args([]))
        url = server_geminize_url(cfg, URL('https://docs.aiohttp.org'))
        assert str(url) == 'gemini://localhost/docs.aiohttp.org/'


class TestEntryPoint:
    @pytest.mark.parametrize(
        'args', [
            [],
            ['-d']
        ]
    )
    @pytest.mark.asyncio
    async def test_entrypoint(self, client, args):
        # Run levior via the console entrypoint and test that
        # it's up and serving requests

        proc = await asyncio.create_subprocess_exec('levior', *args)
        await asyncio.sleep(3)

        resp, doc = await client.request_gmidoc(
            URL('gemini://localhost/cache'))
        assert resp.status == Status.SUCCESS

        try:
            proc.terminate()
        except Exception:
            pidf = Path('levior.pid')
            if pidf.is_file():
                os.kill(int(pidf.read_text()), signal.SIGTERM)

    @pytest.mark.asyncio
    async def test_config_generate(self, tmpdir):
        cpath = Path(tmpdir).joinpath('leviorg.yaml')
        proc = await asyncio.create_subprocess_exec('levior',
                                                    '--config-gen',
                                                    str(cpath))
        await proc.wait()

        cfg = OmegaConf.load(cpath)
        assert cfg.daemonize is False
        assert cfg.hostname == 'localhost'


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
        config, rules = get_config(parse_args(['--mode=server']))
        conv = PageConverter(
            domain='test.org',
            http_proxy_mode=False,
            url_config={
                'cache': False,
                'ttl': 0
            },
            levior_config=config,
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
        cfg, rules = get_config(parse_args([]))
        assert cfg.hostname == 'localhost'
        assert cfg.port == 1965

        cfg, rules = get_config(
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

        cfg, rules = get_config(parse_args(['-c', str(cfgf)]))
        assert cfg.daemonize is True


class TestLeviorModes:
    @pytest.mark.asyncio
    async def test_server_routes(self, server, client):
        # /goto must ask for an INPUT
        req = Request(url=URL('gemini://localhost/goto'))
        resp = await client.send_request(req)
        assert resp.status == Status.INPUT

        # /goto when passing a domain
        req = Request(
            url=URL('gemini://localhost/goto').with_query('geminiprotocol.net')
        )
        resp = await client.send_request(req)
        assert resp.status == Status.REDIRECT_TEMPORARY
        assert resp.reason == 'gemini://localhost/geminiprotocol.net/'

        # /goto when passing a a full URL
        req = Request(
            url=URL('gemini://localhost/goto').with_query(
                'https://geminiprotocol.net')
        )
        resp = await client.send_request(req)
        assert resp.status == Status.REDIRECT_TEMPORARY
        assert resp.reason == 'gemini://localhost/geminiprotocol.net/'

        # Test that nonexistent routes return NOT_FOUND
        for path in ['/noway', '/not_here', '/404', '/localhost']:
            assert (await client.send_request(
                Request(
                    url=URL('gemini://localhost').with_path(path)
                )
            )).status == Status.NOT_FOUND

    @pytest.mark.asyncio
    async def test_server_mode(self, server, client):
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

        # In server-only mode, this should fail with PROXY_REQUEST_REFUSED
        resp, data = await client.proxy_request('https://docs.aiohttp.org')
        assert resp.status == Status.PROXY_REQUEST_REFUSED

        resp, doc = await client.request_gmidoc(
            URL('gemini://localhost/search')
        )
        assert resp.status == Status.INPUT

    @pytest.mark.asyncio
    async def test_proxy_mode(self, proxy_server, client):
        resp, data = await client.proxy_request('https://docs.aiohttp.org')
        assert resp.status == Status.REDIRECT_TEMPORARY
        assert resp.reason == 'https://docs.aiohttp.org/en/stable/'

        resp, data = await client.proxy_request(resp.reason)
        assert resp.status == Status.SUCCESS
        assert resp.content_type.startswith('text/gemini')
        assert data.decode().splitlines()[0].startswith('Welcome to AIOHTTP')

        # In proxy-only mode, this should fail with PROXY_REQUEST_REFUSED
        resp = await client.send_request(
            Request(url=URL('gemini://localhost')))
        assert resp.status == Status.PROXY_REQUEST_REFUSED

        # Test 404
        resp, data = await client.proxy_request(
            'https://docs.aiohttp.org/404willneverbefound.html')
        assert resp.status == Status.NOT_FOUND

        # Get an image
        resp, data = await client.proxy_request(
            'https://docs.aiohttp.org/en/stable/_static/aiohttp-plain.svg'
        )
        assert resp.status == Status.SUCCESS
        assert resp.content_type.startswith('image/')

    @pytest.mark.asyncio
    async def test_cachelinks(self,
                              mixed_server_with_cachelinks,
                              client):
        # Test that the cache links are added at the beginning of the page
        url = URL('https://docs.python.org/3/library/index.html')

        resp, doc = await client.proxy_request_gmidoc(url)
        line0 = doc._lines[0]
        assert line0.type == LineType.LINK
        assert line0.text.startswith('Cache this page for')

        # Cache it
        resp, doc = await client.proxy_request_gmidoc(url.with_query(
            {caching.query_cache_forever_key: 'true'})
        )

        # Once it's cached, the cache links shouldn't be shown
        resp, doc = await client.proxy_request_gmidoc(url)
        assert not doc._lines[0].text.startswith('Cache this page for')

        # List the cache entries and check that the page was cached
        resp, doc = await client.request_gmidoc(
            URL('gemini://localhost/cache')
        )

        for line in doc.emit_line_objects():
            if line.type == LineType.LINK:
                assert line.extra == str(url)

        url2 = URL('https://docs.python.org/3/library/importlib.html')
        resp, doc = await client.proxy_request_gmidoc(url2.with_query(
            {caching.query_cachettl_key: str(86400)}
        ))
        resp, doc = await client.request_gmidoc(
            URL('gemini://localhost/cache')
        )
        assert resp.status == Status.SUCCESS

    @pytest.mark.asyncio
    async def test_mixed_mode(self, mixed_server, client):
        """
        Verify that in the proxy+server mode, both types of requests are
        allowed to go through.
        """
        resp, data = await client.proxy_request(
            'https://docs.aiohttp.org/en/stable/')
        assert resp.status == Status.SUCCESS

        resp = await client.send_request(
            Request(url=URL('gemini://localhost/goto')))
        assert resp.status == Status.INPUT

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        os.getenv("LEVIOR_PYTEST_IPFS") is None,
        reason="Not testing IPFS proxying in this environment"
    )
    async def test_proxy_ipfs(self, proxy_server, client):  # pragma: no cover
        # Fetch some IPFS file and verify the checksum
        h = hashlib.sha256()
        resp, data = await client.proxy_request(
            'ipfs://bafybeigrf2dwtpjkiovnigysyto3d55opf6qkdikx6d65onrqnfzwgdkfa'  # noqa
        )
        assert resp.status == Status.SUCCESS
        h.update(data)

        assert h.hexdigest() == \
            'c749ac31ca6e6b917bdbd4148a7c0fec6fea2aaa036211211bddf8d6ae4c33f4'

    @pytest.mark.asyncio
    async def test_proxy_feed(self, proxy_server, client):
        resp, data = await client.proxy_request('https://openrss.org/rss')
        assert resp.content_type.startswith('text/gemini')


class TestFeedsAggregation:
    @pytest.mark.asyncio
    async def test_feeds_aggregation(self, mixed_server_with_includes, client):
        feed_url = URL('gemini://localhost/ftvinfo')

        for x in range(0, 2):
            resp, doc = await client.request_gmidoc(feed_url)

            assert resp.status == Status.SUCCESS
            assert len(doc._lines) > 0

        # Requesting a specific feed by id (fails because nonexistent)
        resp, doc = await client.request_gmidoc(feed_url.with_query('50'))
        assert resp.status == Status.TEMPORARY_FAILURE

        # Request the access log
        resp, doc = await client.request_gmidoc(
            URL('gemini://localhost/access_log')
        )
        assert resp.status == Status.SUCCESS
        assert doc._lines[0].text == 'Access log'


class TestZIM:
    """
    Test the ZIM mounting feature
    """

    @pytest.mark.asyncio
    async def test_zim_mount(self, mixed_server_with_includes, client):
        murl = URL('gemini://localhost/alpine')
        # Request /alpine, which shound redirect to the main article
        resp, doc = await client.request_gmidoc(murl)

        assert resp.status == Status.REDIRECT_TEMPORARY
        assert resp.reason == str(murl.joinpath('A/Main_Page'))
        # assert resp.reason == 'gemini://localhost/alpine/A/Main_Page'

        # Get the main article and check that it's properly rendered
        resp, doc = await client.request_gmidoc(URL(resp.reason))
        assert doc._lines[0].text == 'Main Page'

        # Hit the search endpoint, and check that we're prompted for a query
        resp, doc = await client.request_gmidoc(murl.joinpath('search'))
        assert resp.status == Status.INPUT

        # Search something and check the results
        resp, doc = await client.request_gmidoc(
            murl.joinpath('search').with_query('dualbooting')
        )
        assert doc._lines[0].text == 'Found 5 results for: dualbooting'

        # Get the favicon and check the content type and size
        resp = await client.send_request(Request(url=murl.joinpath('favicon')))
        assert resp.content_type == 'image/png'
        assert len(await resp.read()) == 3077


class TestGemtextFilters:
    @pytest.mark.asyncio
    async def test_filters(self, proxy_server_with_filters, client):
        # Check that all email address links are removed by the
        # strip_emailaddrs filter

        resp, data = await client.proxy_request(
            'https://searx.be/search?q=cats')

        for line in data.decode().splitlines():
            assert not line.startswith('=> mailto:')

        # Test rewriting headings
        resp, data = await client.proxy_request('https://pythonclock.org')
        found = False
        for line in data.decode().splitlines():
            assert not line.startswith('# Python 2.7 will retire in')
            if line == '# Python never retires':
                found = True
                break

        assert found


class TestIncludes:
    @pytest.mark.asyncio
    async def test_puretext(self, proxy_server_with_includes, client):
        resp, data = await client.proxy_request(
            'https://searx.be/search?q=cats')

        # Test that all links are removed by the puretext rule
        for line in data.decode().splitlines():
            assert not line.startswith('=>')

    @pytest.mark.asyncio
    async def test_all_sites(self, mixed_server_with_all_sites, client):
        for path in ['/ftvinfo', '/theguardian']:
            resp, doc = await client.request_gmidoc(
                URL('gemini://localhost').with_path(path)
            )
            assert resp.status == Status.SUCCESS
            assert len(doc._lines) > 0


class TestJavascript:
    @pytest.mark.skip(reason="Fails when running the whole test suite")
    @pytest.mark.asyncio
    async def test_js(self, proxy_server_with_js, client):
        resp, doc = await client.proxy_request_gmidoc(
            URL('https://www.jsstatus.com/')
        )

        assert any([line.text.lower().startswith(
            'your javascript is active') for line in doc._lines])
