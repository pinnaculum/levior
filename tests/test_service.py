from dataclasses import dataclass
from pathlib import Path
import pytest
import asyncio
import re

from yarl import URL
from omegaconf import OmegaConf

from levior import default_cert_paths
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
            f'{url.host}{url.path}'
        )

        return await self.send_request(Request(url=req_url))

    async def proxy_request(self, request: Request,
                            proxy: tuple = ('localhost', 1965)):
        assert request.url.host, "URL must specify host"
        loop = asyncio.get_running_loop()
        protocol = Protocol(request, loop=loop)

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
    config, srv = levior_configure_server(parse_args([]))
    f = asyncio.ensure_future(srv.serve())
    await asyncio.sleep(2)
    yield srv
    f.cancel()


@pytest.fixture
async def proxy_server():
    config, srv = levior_configure_server(parse_args(['--mode=http-proxy']))
    assert config.mode == 'http-proxy'
    f = asyncio.ensure_future(srv.serve())
    await asyncio.sleep(2)
    yield srv
    f.cancel()


class TestLeviorConfig:
    def test_configuration(self, tmpdir):
        cfg = get_config(parse_args([]))
        assert cfg.hostname == 'localhost'
        assert cfg.port == 1965

        cfg = get_config(
            parse_args(['--daemonize', '--https-only', '--mode=http-proxy'])
        )

        assert cfg.daemonize is True
        assert cfg.https_only is True
        assert cfg.mode == 'http-proxy'

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
        assert resp.content_type == 'text/gemini'
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
        assert resp.status == Status.SUCCESS
        assert resp.content_type == 'text/gemini'

        data = (await resp.read()).decode()
        assert data.splitlines()[0] == 'The FreeBSD Project'

        # Test that the content type is properly set
        resp = await client.local_req(
            'https://www.freebsd.org/images/logo-red.png'
        )
        assert resp.status == Status.SUCCESS
        assert resp.content_type == 'image/png'

    @pytest.mark.asyncio
    async def test_proxy_mode(self, proxy_server, client):
        req = Request(url=URL('https://freebsd.org'))
        resp = await client.proxy_request(req)
        assert resp.status == Status.SUCCESS
        data = (await resp.read()).decode()
        assert resp.content_type == 'text/gemini'
        assert data.splitlines()[0] == 'The FreeBSD Project'
