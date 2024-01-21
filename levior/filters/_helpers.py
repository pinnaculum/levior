from trimgmi import Line, LineType


def str_to_linetype(type_s: str) -> LineType:
    try:
        return getattr(LineType, type_s.upper())
    except AttributeError:
        return None


def is_text(line: Line):
    return line.type in [LineType.REGULAR,
                         LineType.QUOTE,
                         LineType.LIST_ITEM]


def is_heading(line: Line):
    return line.type in [LineType.HEADING1,
                         LineType.HEADING2,
                         LineType.HEADING3]
