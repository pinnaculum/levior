from importlib import resources


__appname__ = 'levior'
__version__ = '1.3.3'


def default_cert_paths() -> tuple:
    """
    Return a tuple containing the paths of the default levior
    certificate and key.
    """
    return (
        resources.files(__name__) / 'localhost.crt',
        resources.files(__name__) / 'localhost.key'
    )
