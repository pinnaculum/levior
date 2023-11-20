import pkg_resources


def default_cert_paths() -> tuple:
    return (
        pkg_resources.resource_filename(
            'levior', 'localhost.crt'
        ),
        pkg_resources.resource_filename(
            'levior', 'localhost.key'
        )
    )
