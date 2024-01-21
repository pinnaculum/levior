from dataclasses import dataclass, field

import asyncio
import importlib
import traceback

from trimgmi import Document as GmiDocument
from trimgmi import LineType
from trimgmi import Line

from .text import rm_bracketed_digits  # noqa
from .text import text_filter  # noqa
from .text import get_out  # noqa
from .text import uppercased  # noqa
from .misc import only_linetypes  # noqa


@dataclass
class FilterContext:
    doc: GmiDocument
    params: dict = field(default=None)
    line_num: int = field(default=0)
    line: Line = field(default=None)
    prev_line: Line = field(default=None)


async def run_gemtext_filters(doc: GmiDocument,
                              gemtext_filters: list) -> GmiDocument:
    """
    Run a series of gemtext filter functions on a gemtext document
    and return the modified document.

    :param GmiDocument doc: The original document
    :param list gemtext_filters: List of Python module names that contain
        the gemtext filter functions.
    :rtype: GmiDocument
    """

    filters: list = []
    lines: list = []

    for gtfilter in gemtext_filters:
        params = {}
        try:
            if isinstance(gtfilter, str):
                fnref = gtfilter
            elif isinstance(gtfilter, dict):
                params = gtfilter
                fnref = params.pop('filter')

            assert isinstance(fnref, str)

            if ':' in fnref:
                modspec, fnname = fnref.split(':')
            else:
                modspec, fnname = fnref, 'gemtext_filter'

            assert modspec

            mod = importlib.import_module(modspec)
            filter_fn = getattr(mod, fnname)
        except ModuleNotFoundError:
            print(f'Filter module with spec {fnref} not found')
            continue
        except ImportError:
            traceback.print_exc()
            continue
        except (AssertionError, AttributeError):
            continue
        except Exception:
            traceback.print_exc()
        else:
            filters.append((filter_fn, params))

    ctx = FilterContext(doc=doc)

    for line in doc.emit_line_objects(auto_tidy=True):
        if line.type == LineType.BLANK:
            ctx.line_num += 1
            continue

        filtered: bool = False
        rewritten: bool = False
        exit: bool = False

        ctx.line = line

        for ffn, fparams in filters:
            ctx.params = fparams if fparams else {}
            try:
                if asyncio.iscoroutinefunction(ffn):
                    result = await ffn(ctx)
                else:
                    result = ffn(ctx)

                if isinstance(result, Line):
                    lines.append(result)
                    rewritten = True
                    break
                elif isinstance(result, list):
                    for obj in result:
                        if isinstance(obj, Line):
                            lines.append(obj)
                            rewritten = True

                    if rewritten:
                        break
                elif isinstance(result, str):
                    line_type = LineType.identify(result, False)
                    lines.append(Line.extract(line_type, result))
                    rewritten = True
                    break
                elif isinstance(result, int) and result == -1:
                    exit = True
                    break
                elif isinstance(result, bool) and result is True:
                    filtered = True
                    break
            except AssertionError:
                # When a filter raises an assertion error we catch it
                # and move on (we should log these somewhere too)
                continue
            except Exception:
                traceback.print_exc()
                continue

        if exit:
            break

        if not filtered and not rewritten:
            lines.append(line)

        ctx.prev_line = line
        ctx.line_num += 1

        await asyncio.sleep(0)

    return GmiDocument(_lines=lines)
