from importlib import resources


__appname__ = 'levior'
__version__ = '1.3.5'


def bytes_to_humanr(num: int, suffix: str = 'B') -> str:
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0

    return f"{num:.1f}Yi{suffix}"


def default_cert_paths() -> tuple:
    """
    Return a tuple containing the paths of the default levior
    certificate and key.
    """
    return (
        resources.files(__name__) / 'localhost.crt',
        resources.files(__name__) / 'localhost.key'
    )
