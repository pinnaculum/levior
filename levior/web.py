from typing import Union, Optional, List
from yarl import URL

from omegaconf import ListConfig

from random_user_agent.user_agent import UserAgent
from random_user_agent.params import OperatingSystem
from random_user_agent.params import SoftwareType

from aiohttp_socks import ProxyConnector, ChainProxyConnector


user_agent_rotator = UserAgent(
    software_types=[SoftwareType.WEB_BROWSER.value],
    operating_systems=[
        OperatingSystem.WINDOWS.value,
        OperatingSystem.LINUX.value,
        OperatingSystem.FREEBSD.value
    ],
    limit=1000
)


def random_useragent() -> str:
    return user_agent_rotator.get_random_user_agent()


def valid_proxy_url(url: Union[URL, str, None]) -> bool:
    if isinstance(url, URL):
        prox_url = url
    elif isinstance(url, str):
        prox_url = URL(url)
    else:
        return False

    return bool(prox_url.scheme in [
        'socks', 'socks4', 'socks5', 'http'] and prox_url.host)


def get_proxy_connector(
        proxy_url: Optional[Union[List[str], ListConfig, URL, str]] = None,
        proxy_chain: Optional[List[str]] = []
) -> Union[ProxyConnector, ChainProxyConnector, None]:
    if isinstance(proxy_url, (ListConfig, list)):
        return ChainProxyConnector.from_urls([
            url for url in proxy_url if isinstance(url, str) and
            valid_proxy_url(url)
        ])
    elif isinstance(proxy_url, (str, URL)) and valid_proxy_url(proxy_url):
        return ProxyConnector.from_url(
            str(proxy_url) if isinstance(proxy_url, URL) else proxy_url
        )
    else:
        return None
