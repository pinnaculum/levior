import random
from omegaconf import OmegaConf
from omegaconf import ListConfig
from datetime import datetime
from typing import Optional, List

from .web import random_useragent
from .web import custom_random_useragent


def choice(items):
    if isinstance(items, ListConfig):
        return random.choice(items)


def random_wb_user_agent(os_list,
                         software_list: Optional[List[str]] = [],
                         engine_list: Optional[List[str]] = [],
                         hw_list: Optional[List[str]] = []) -> str:
    return custom_random_useragent(
        ['WEB_BROWSER'],
        os_list, software_list, engine_list, hw_list
    )


OmegaConf.register_new_resolver("choice", choice)
OmegaConf.register_new_resolver("random", choice)
OmegaConf.register_new_resolver("random_user_agent", random_useragent)
OmegaConf.register_new_resolver("ua_roulette", random_useragent)
OmegaConf.register_new_resolver("rweb_user_agent",
                                random_wb_user_agent)
OmegaConf.register_new_resolver("custom_ua_roulette",
                                random_wb_user_agent)
OmegaConf.register_new_resolver(
    "datetime_now_iso",
    lambda: datetime.now().isoformat(timespec='seconds', sep=' ')
)
