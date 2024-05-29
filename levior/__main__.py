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

from omegaconf import OmegaConf
from omegaconf import DictConfig
from omegaconf import ListConfig

from . import __appname__
from . import caching
from . import default_cert_paths
from . import ocresolvers  # noqa

from .caching import load_cached_access_log
from .handler import create_levior_handler
from .rules import parse_rules


try:  # pragma: no cover
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except Exception:
    pass


def load_include(path: Union[Path, str],
                 iparams: Union[DictConfig, ListConfig]) -> DictConfig:
    cfd = StringIO()

    try:
        if iparams:
            OmegaConf.save(config=iparams, f=cfd)

        with open(path, 'rt') as f:
            cfd.write(f.read())

        cfd.seek(0, 0)

        inccfg = OmegaConf.load(cfd)
        assert isinstance(inccfg, DictConfig)
        return inccfg
    except BaseException:
        traceback.print_exc()


def load_config_file(src: Union[Path, str, TextIO]) -> tuple:
    """
    Load a levior config file and returns a tuple containing the
    config (as a DictConfig) and the list of URL rules
    """

    rules: list = []
    file_cfg: DictConfig = None

    if isinstance(src, (Path, str)):
        fd = open(src, 'rt')
    elif isinstance(src, StringIO):
        fd = src
    else:
        raise ValueError('Invalid source type')

    file_cfg = OmegaConf.load(fd)

    assert file_cfg

    # Load rules from this file
    rules += parse_rules(file_cfg)

    includes = file_cfg.get('include')
    configs_root: Path = resources.files('levior') / 'configs'

    # Handle includes
    if isinstance(includes, ListConfig):
        for inc in file_cfg.include:
            loadt: str = None

            if isinstance(inc, DictConfig):
                isrc = inc.get('src')
                iparams = inc.get('with')
            elif isinstance(inc, str):  # pragma: no cover
                isrc, iparams = inc, None

            if isinstance(iparams, DictConfig) and 0:
                # Set env vars passed in 'with' (disabled for now)
                for key, val in iparams.items():
                    if isinstance(val, (str, int, float)):
                        os.environ[f'LEV_{key}'] = str(val)

            if not isinstance(isrc, str):  # pragma: no cover
                continue

            if ':' in isrc:
                loadt, path_ref = isrc.split(':')
            else:
                loadt, path_ref = None, isrc

            if loadt in ['levior', 'lev']:
                # Levior library
                for glob_path in configs_root.glob(path_ref):
                    if glob_path.name.startswith('_'):
                        continue

                    rules += parse_rules(
                        load_include(glob_path, iparams),
                        inc  # context
                    )
            elif not loadt:
                # Local file
                rules += parse_rules(load_include(path_ref, iparams), inc)

    return file_cfg, rules


def get_config(cli_cfg: DictConfig) -> DictConfig:
    rules: list = []
    cfgp = Path(cli_cfg.config_path) if cli_cfg.config_path else None

    if cfgp and cfgp.is_file():
        try:
            file_cfg, rules = load_config_file(cli_cfg.config_path)

            config = OmegaConf.merge(cli_cfg, file_cfg)
        except Exception as err:
            raise err
    else:
        config = cli_cfg

    rules = sorted(
        rules, key=lambda rule: rule.config.get('priority', 1000)
    )

    return config, rules


def levior_configure_server(cli_cfg) -> Tuple[DictConfig, Server]:
    """
    Create a levior server from the command-line config arguments
    or by using a YAML config file.
    """

    config, rules = get_config(cli_cfg)

    data_dir: Path = Path(appdirs.user_data_dir(__appname__))  # noqa
    try:
        for mode in config.mode.split(','):
            if not mode:  # pragma: no cover
                continue

            assert mode.strip() in ['server', 'proxy', 'http-proxy']
    except AssertionError:  # pragma: no cover
        raise ValueError(f'Invalid modes config: {config.mode}')

    if config.get('gemini_cert') and config.get('gemini_key'):
        cert_path, key_path = config.gemini_cert, config.gemini_key
    else:
        cert_path, key_path = default_cert_paths()

    cache = caching.configure_cache(config)

    return (config, Server(
        create_server_ssl_context(cert_path, key_path),
        create_levior_handler(
            config, cache, rules,
            access_log=load_cached_access_log(cache)
        ),
        host=config.get('hostname', 'localhost'),
        port=config.get('port', 1965)
    ))
