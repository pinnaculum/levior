import re

from ._helpers import is_text


def rm_bracketed_digits(fctx) -> bool:
    """
    Remove any annoying lines that ends with digits
    inside square brackets like:

    Videos[2]
    Plus d'information[45]
    """

    assert is_text(fctx.line)

    return re.search(r'^.*?\[\d+\]', fctx.line.text) is not None


def text_filter(fctx) -> bool:
    """
    Remove that line of text if any of the regexps matches

    :rtype: bool
    """

    assert is_text(fctx.line), f"Not a text line: {fctx.line.type}"

    textre = fctx.params.get('re', [])
    return any(re.search(reg, fctx.line.text) for reg in textre)


def get_out(fctx) -> int:
    """
    Skip the processing (return -1) of the rest of the document if the
    line's text matches any of the regexps passed in the params

    :rtype: int
    """

    assert is_text(fctx.line)

    textre = fctx.params.get('re', [])

    if any(re.search(reg, fctx.line.text) for reg in textre):
        return -1


def uppercased(fctx):
    assert is_text(fctx.line)

    words = fctx.params.get('words', [])

    if not words:
        return fctx.line

    fctx.line.text = ' '.join(
        w.upper() if w in words else w for w in fctx.line.text.split()
    )

    return fctx.line
