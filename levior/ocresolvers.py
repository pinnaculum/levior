from omegaconf import OmegaConf
from datetime import datetime


OmegaConf.register_new_resolver(
    "datetime_now_iso",
    lambda: datetime.now().isoformat(timespec='seconds', sep=' '))
