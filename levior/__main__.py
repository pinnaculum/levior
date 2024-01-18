import asyncio
import os

from pathlib import Path
from importlib import resources
from typing import Union, TextIO

from aiogemini.tofu import create_server_ssl_context
from aiogemini.server import Server

from omegaconf import OmegaConf
from omegaconf import DictConfig
from omegaconf import ListConfig

from . import default_cert_paths
from .handler import create_levior_handler
from .rules import parse_rules


try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except Exception:
    pass


def load_config_file(arg: Union[Path, TextIO]) -> tuple:
    """
    Load a levior config file and returns a tuple containing the
    config (as a DictConfig) and the list of URL rules
    """

    rules: list = []
    file_cfg: DictConfig = None

    if isinstance(arg, Path):
        fd = open(arg, 'rt')
    else:
        fd = arg

    file_cfg = OmegaConf.load(fd)

    assert file_cfg

    # Load rules from this file
    rules += parse_rules(file_cfg)

    includes = file_cfg.get('include')

    # Handle includes
    if isinstance(includes, ListConfig):
        for inc in file_cfg.include:
            inccfg: DictConfig = None
            loadt: str = None

            if isinstance(inc, DictConfig):
                iref = inc.get('src')
                iparams = inc.get('with')
            elif isinstance(inc, str):
                iref, iparams = inc, None

            if isinstance(iparams, DictConfig) and 0:
                # Set env vars passed in 'with' (disabled for now)
                for key, val in iparams.items():
                    if isinstance(val, (str, int, float)):
                        os.environ[f'LEV_{key}'] = str(val)

            if not isinstance(iref, str):
                continue

            if ':' in iref:
                loadt, path = iref.split(':')
            else:
                loadt, path = None, iref

            if loadt in ['levior', 'lev']:
                if not path.endswith('.yaml'):
                    path += '.yaml'

                inccfg = OmegaConf.load(
                    resources.open_text('levior.configs',
                                        path)
                )
            elif not loadt:
                # Local file
                inccfg = OmegaConf.load(open(path, 'rt'))

            if inccfg:
                rules += parse_rules(inccfg)

    return file_cfg, rules


def get_config(args) -> DictConfig:
    rules: list = []

    config = OmegaConf.create({
        'gemini_cert': args.gemini_cert,
        'gemini_key': args.gemini_key,

        'daemonize': args.daemonize,
        'pid_file_path': args.pid_file_path,
        'https_only': args.https_only,
        'mode': args.service_modes,
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

        'js_render': args.js_render,
        'js_render_always': args.js_render_always,

        'urules': [{
            'regex': r'.*',
            'cache': args.cache_enable,
            'ttl': args.cache_ttl_secs
        }]
    })

    cfgp = Path(args.config_path) if args.config_path else None

    if cfgp and cfgp.is_file():
        try:
            file_cfg, rules = load_config_file(args.config_path)

            config = OmegaConf.merge(config, file_cfg)
        except Exception as err:
            raise err

    return config, rules


def levior_configure_server(args) -> (DictConfig, Server):
    """
    Create a levior server from the command-line config arguments
    or by using a YAML config file.

    :rtype: Server
    """

    config, rules = get_config(args)

    try:
        for mode in config.mode.split(','):
            if not mode:
                continue

            assert mode.strip() in ['server', 'proxy', 'http-proxy']
    except AssertionError:
        raise ValueError(f'Invalid modes config: {config.mode}')

    if config.get('gemini_cert') and config.get('gemini_key'):
        cert_path, key_path = config.gemini_cert, config.gemini_key
    else:
        cert_path, key_path = default_cert_paths()

    return (config, Server(
        create_server_ssl_context(cert_path, key_path),
        create_levior_handler(config, rules),
        host=config.get('hostname', 'localhost'),
        port=config.get('port', 1965)
    ))
