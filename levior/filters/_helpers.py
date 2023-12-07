from trimgmi import Line, LineType


def is_text(line: Line):
    return line.type in [LineType.REGULAR,
                         LineType.QUOTE,
                         LineType.LIST_ITEM]


def is_heading(line: Line):
    return line.type in [LineType.HEADING1,
                         LineType.HEADING2,
                         LineType.HEADING3]
