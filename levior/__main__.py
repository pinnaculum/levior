import asyncio
from pathlib import Path

from aiogemini.tofu import create_server_ssl_context
from aiogemini.server import Server

from omegaconf import OmegaConf
from omegaconf import DictConfig

from . import default_cert_paths
from .handler import create_levior_handler


try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except Exception:
    pass


def get_config(args) -> DictConfig:
    config = OmegaConf.create({
        'gemini_cert': args.gemini_cert,
        'gemini_key': args.gemini_key,

        'daemonize': args.daemonize,
        'pid_file_path': args.pid_file_path,
        'https_only': args.https_only,
        'mode': args.service_mode,
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

    cfgp = Path(args.config_path) if args.config_path else None

    if cfgp and cfgp.is_file():
        try:
            with open(args.config_path, 'rt') as fd:
                file_cfg = OmegaConf.load(fd)

            config = OmegaConf.merge(config, file_cfg)
        except Exception as err:
            raise err

    return config


def levior_configure_server(args) -> (DictConfig, Server):
    """
    Create a levior server from the command-line config arguments
    or by using a YAML config file.

    :rtype: Server
    """

    config = get_config(args)

    if config.get('gemini_cert') and config.get('gemini_key'):
        cert_path, key_path = config.gemini_cert, config.gemini_key
    else:
        cert_path, key_path = default_cert_paths()

    security = create_server_ssl_context(cert_path, key_path)

    return (config, Server(
        security,
        create_levior_handler(config),
        host=config.get('hostname', 'localhost'),
        port=config.get('port', 1965)
    ))
