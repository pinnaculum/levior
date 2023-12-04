import re
from typing import Union
from trimgmi import Line, LineType

from . import FilterContext


def strip_emailaddrs(fctx: FilterContext) -> Union[Line, str, bool]:
    """
    Filter to remove links to email addresses
    """
    if fctx.line.type == LineType.LINK and \
       fctx.line.extra.startswith('mailto:'):
        # Remove mail address links
        return True


def url_remove(fctx: FilterContext) -> Union[Line, str, bool]:
    """
    Filter to remove URLs matched by regular expressions
    """

    uregexps = fctx.params.get('urls', [])

    if fctx.line.type == LineType.LINK:
        return any(re.search(reg, fctx.line.extra) for reg in uregexps)
