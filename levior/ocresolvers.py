import random
from omegaconf import OmegaConf
from omegaconf import ListConfig
from datetime import datetime

from .web import random_useragent


def choice(items):
    if isinstance(items, ListConfig):
        return random.choice(items)


OmegaConf.register_new_resolver("choice", choice)
OmegaConf.register_new_resolver("random", choice)
OmegaConf.register_new_resolver("random_user_agent", random_useragent)
OmegaConf.register_new_resolver(
    "datetime_now_iso",
    lambda: datetime.now().isoformat(timespec='seconds', sep=' ')
)
