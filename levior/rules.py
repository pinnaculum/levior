import re

from dataclasses import dataclass, field
from typing import List

from omegaconf import DictConfig
from omegaconf import ListConfig


@dataclass
class URLRule:
    regexps: list
    match_count: int = field(default=0)
    config: DictConfig = field(default=None)


def instantiate_rule(urlc: DictConfig) -> URLRule:
    """
    Create a URLRule object based on a rule's configuration

    :rtype: URLRule
    """

    urlre = urlc.get('url', urlc.get('regexp'))

    if isinstance(urlre, ListConfig):
        regs = list(urlre)
    elif isinstance(urlre, str):
        regs = [urlre]
    else:
        return None

    return URLRule(
        regexps=[re.compile(r) for r in regs],
        config=urlc
    )


def parse_rules(config: DictConfig) -> List[URLRule]:
    """
    Parse the URL rules in a DictConfig and returns them as a list of URLRule
    """

    rules: list = []
    re_ruledef = re.compile(r'^(?P<prefix>u?)rules$')

    for key, obj in config.items():
        rem = re_ruledef.match(key)

        if not rem:
            continue

        if not isinstance(obj, ListConfig):
            continue

        prefix = rem.group('prefix')  # noqa

        for item in obj:
            _rule = instantiate_rule(item)

            if _rule:
                rules.append(_rule)

    return rules
