import re

from dataclasses import dataclass, field
from typing import List
from typing import Optional

from omegaconf import DictConfig
from omegaconf import ListConfig


@dataclass
class URLRule:
    regexps: list

    proxy_chain: list
    proxy_url: str = field(default=None)

    match_count: int = field(default=0)
    config: DictConfig = field(default=None)

    # The omegaconf context config node, containing optional params like
    # proxy, user agent, ..
    context: DictConfig = field(default=None)


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
    else:  # pragma: no cover
        return None

    return URLRule(
        regexps=[re.compile(r) for r in regs],
        config=urlc,
        proxy_chain=[]
    )


def parse_rules(config: DictConfig,
                context: Optional[DictConfig] = None,
                proxy_chain: Optional[ListConfig] = None,
                proxy_url: Optional[str] = None) -> List[URLRule]:
    """
    Parse the URL rules in a DictConfig and returns them as a list of URLRule
    """

    rules: list = []

    if config is None:
        return rules

    re_ruledef = re.compile(r'^(?P<prefix>u?)rules$')

    for key, obj in config.items():
        rem = re_ruledef.match(key)

        if not rem:
            continue

        if not isinstance(obj, ListConfig):  # pragma: no cover
            continue

        prefix = rem.group('prefix')  # noqa

        for item in obj:
            _rule = instantiate_rule(item)

            if not _rule:
                continue

            _rule.context = context if context else item

            rules.append(_rule)

    return rules
