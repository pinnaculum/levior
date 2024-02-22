import pkg_resources


__version__ = '1.2.8'


def default_cert_paths() -> tuple:
    return (
        pkg_resources.resource_filename(
            'levior', 'localhost.crt'
        ),
        pkg_resources.resource_filename(
            'levior', 'localhost.key'
        )
    )
