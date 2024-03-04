import asyncio
import os
import traceback
from io import StringIO

from pathlib import Path
from importlib import resources
from typing import Tuple, Union, TextIO

from aiogemini.tofu import create_server_ssl_context
from aiogemini.server import Server

import appdirs
import diskcache

from omegaconf import OmegaConf
from omegaconf import DictConfig
from omegaconf import ListConfig

from . import __appname__
from . import default_cert_paths
from . import ocresolvers  # noqa

from .caching import load_cached_access_log
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

            cfd = StringIO()
            if iparams:
                OmegaConf.save(config=iparams, f=cfd)

            if not path.endswith('.yaml'):
                path += '.yaml'

            if loadt in ['levior', 'lev']:
                # Load from the builtin library

                rp = resources.files('levior') / 'configs'

                with open(rp.joinpath(path), 'rt') as f:
                    cfd.write(f.read())
            elif not loadt:
                # Local file

                with open(path, 'rt') as f:
                    cfd.write(f.read())

            cfd.seek(0, 0)

            try:
                inccfg = OmegaConf.load(cfd)
                assert isinstance(inccfg, DictConfig)

                rules += parse_rules(inccfg)
            except Exception:
                traceback.print_exc()
                continue

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
        'log_file_path': args.log_file_path,
        'cache_path': args.cache_path,
        'cache_enable': args.cache_enable,
        'cache_ttl_default': args.cache_ttl_default,
        'cache_size_limit': args.cache_size_limit,
        'cache_eviction_policy': args.cache_eviction_policy,
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
            'ttl': args.cache_ttl_default
        }]
    })

    cfgp = Path(args.config_path) if args.config_path else None

    if cfgp and cfgp.is_file():
        try:
            file_cfg, rules = load_config_file(args.config_path)

            config = OmegaConf.merge(config, file_cfg)
        except Exception as err:
            raise err

    rules = sorted(
        rules, key=lambda rule: rule.config.get('priority', 1000)
    )

    return config, rules


def configure_cache(config: DictConfig) -> diskcache.Cache:
    cache_dir: Path = Path(
        config.cache_path if config.cache_path else
        appdirs.user_cache_dir(__appname__)
    )

    if not cache_dir.exists():
        cache_dir.mkdir(parents=True)

    if config.cache_eviction_policy in ['least-recently-stored',
                                        'least-recently-used',
                                        'least-frequently-used',
                                        'none']:
        cpolicy = config.cache_eviction_policy
    else:
        cpolicy = 'least-recently-stored'

    if isinstance(config.cache_size_limit, (int, float)) and \
       config.cache_size_limit > 0:
        size_limit_mb = config.cache_size_limit
    else:
        size_limit_mb = 2048

    return diskcache.Cache(
        str(cache_dir),
        eviction_policy=cpolicy,
        size_limit=size_limit_mb * 1024 * 1024
    )


def levior_configure_server(args) -> Tuple[DictConfig, Server]:
    """
    Create a levior server from the command-line config arguments
    or by using a YAML config file.
    """

    config, rules = get_config(args)

    data_dir: Path = Path(appdirs.user_data_dir(__appname__))  # noqa
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

    cache = configure_cache(config)

    return (config, Server(
        create_server_ssl_context(cert_path, key_path),
        create_levior_handler(
            config, cache, rules,
            access_log=load_cached_access_log(cache)
        ),
        host=config.get('hostname', 'localhost'),
        port=config.get('port', 1965)
    ))
