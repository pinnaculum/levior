from ._helpers import str_to_linetype


def only_linetypes(fctx) -> bool:
    """
    Filter out lines that don't match the given line types
    """

    types = [
        str_to_linetype(_type) for _type in fctx.params.get('types', [])
    ]

    if types:
        return fctx.line.type not in types

    return False
