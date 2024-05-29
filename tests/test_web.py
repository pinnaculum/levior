import pytest
from yarl import URL
from omegaconf import OmegaConf
from aiohttp_socks import ProxyConnector, ChainProxyConnector
from aiohttp_socks import ProxyType

from levior.web import get_proxy_connector
from levior.web import valid_proxy_url


class TestProxies:
    @pytest.mark.parametrize(
        'url', [
            'http://127.0.0.1:8090',
            'http://127.0.0.1:8092',
            'socks4://locahost:9050',
        ]
    )
    def test_proxy_urls(self, url: str):
        assert valid_proxy_url(url) is True
        assert valid_proxy_url(URL(url)) is True
        assert valid_proxy_url(None) is False

    def test_proxy_connector(self):
        conn = get_proxy_connector('socks5://localhost:9050')
        assert type(conn) is ProxyConnector
        assert conn._proxy_type == ProxyType.SOCKS5
        assert conn._proxy_host == 'localhost'
        assert conn._proxy_port == 9050

    @pytest.mark.parametrize(
        'url', [
            [
                'http://127.0.0.1:8090',
                'http://127.0.0.1:8092'
            ],
            OmegaConf.create([
                'http://127.0.0.1:8090',
                'http://127.0.0.1:8092'
            ])
        ]
    )
    def test_proxy_chain_connector(self, url):
        conn = get_proxy_connector(url)
        assert type(conn) is ChainProxyConnector
        assert len(conn._proxy_infos) == 2
        assert conn._proxy_infos[0].proxy_type == ProxyType.HTTP
        assert conn._proxy_infos[1].proxy_type == ProxyType.HTTP
        assert conn._proxy_infos[0].host == '127.0.0.1'
        assert conn._proxy_infos[0].port == 8090
        assert conn._proxy_infos[1].port == 8092
