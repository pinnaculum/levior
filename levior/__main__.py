
import asyncio
from pathlib import Path

from aiogemini.security import TOFUContext
from aiogemini.server import Server

from .handler import create_levior_handler

from easydict import EasyDict
import yaml

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader


try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except Exception:
    pass


__here__ = Path(__file__).parent


async def levior_main(args):
    certs = {}
    cfgp = Path(args.config_path)

    if cfgp.is_file():
        try:
            with open(args.config_path, 'rt') as fd:
                config = EasyDict(yaml.load(fd, Loader))
        except Exception as err:
            raise err
    else:
        config = EasyDict({
            'gemini_cert': args.gemini_cert,
            'gemini_key': args.gemini_key,

            'hostname': args.hostname,
            'port': args.port,
            'cache_path': args.cache_path,
            'cache_enable': args.cache_enable,
            'cache_ttl_default': args.cache_ttl_secs,
            'verify_ssl': args.verify_ssl,
            'socks5_proxy': args.socks5_proxy,
            'tor': args.tor,
            'links_mode': args.md_links,
            'feathers_default': args.feathers,

            'urules': [{
                'regex': r'.*',
                'cache': args.cache_enable,
                'ttl': args.cache_ttl_secs
            }]
        })

    if config.get('gemini_cert') and config.get('gemini_key'):
        cert_path, key_path = config.gemini_cert, config.gemini_key
    else:
        cert_path = str(__here__.joinpath('localhost.crt'))
        key_path = str(__here__.joinpath('localhost.key'))

    security = TOFUContext(certs, cert_path, key_path)

    server = Server(
        security,
        create_levior_handler(config),
        host=config.get('hostname', 'localhost'),
        port=config.get('port', 1965)
    )

    await server.serve()
