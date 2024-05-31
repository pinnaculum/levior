from typing import Union, Optional, List
from yarl import URL

from omegaconf import ListConfig

from random_user_agent.user_agent import UserAgent
from random_user_agent.params import OperatingSystem
from random_user_agent.params import SoftwareType
from random_user_agent.params import SoftwareName
from random_user_agent.params import SoftwareEngine
from random_user_agent.params import HardwareType

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
    """
    Returns a random user agent
    """
    return user_agent_rotator.get_random_user_agent()


def custom_random_useragent(
        stypes_list: List[str],
        os_list: Optional[List[str]] = [],
        software_list: Optional[List[str]] = [],
        engine_list: Optional[List[str]] = [],
        hw_list: Optional[List[str]] = []) -> str:
    """
    Returns a random user agent with specific params.
    """
    try:
        software_types = [
            getattr(SoftwareType, stype.upper()).value for stype in stypes_list
        ]
        operating_systems = [
            getattr(OperatingSystem, os.upper()).value for os in os_list
        ]
        software_names = [
            getattr(SoftwareName, name.upper()).value for name in software_list
        ]
        engine_names = [
            getattr(SoftwareEngine, name.upper()).value for name in engine_list
        ]
        hw_types = [
            getattr(HardwareType, name.upper()).value for name in hw_list
        ]
    except Exception as err:
        raise ValueError(f'Invalid params: {err}')

    rotator = UserAgent(
        software_types=software_types,
        software_names=software_names,
        software_engines=engine_names,
        hardware_types=hw_types,
        operating_systems=operating_systems,
        limit=25  # Limit size to avoid performance issues
    )

    try:
        return rotator.get_random_user_agent()
    except IndexError:
        # The combination gave an empty list: just return any random UA
        return random_useragent()
    except BaseException:
        raise


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
