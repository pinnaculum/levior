import traceback
from pathlib import Path
from aiogemini.server import Request, Response
from md2gemini import md2gemini

try:
    from libzim.reader import Archive
except ImportError:
    have_zim = False
else:
    have_zim = True


from .response import data_response
from .response import error_response
from .response import redirect_response
from . import crawler


class ZimMountPoint:
    def __init__(self, mppath: str, source: Path):
        self.mp = mppath
        self._zim_path = source
        self._zim = None

    def setup(self):
        try:
            self._zim = Archive(str(self._zim_path))
            return True
        except Exception:
            traceback.print_exc()
            return False

    async def handle_request(self, req: Request, config) -> Response:
        path = req.url.path.lstrip(self.mp)

        if not path:
            try:
                path = self._zim.main_entry.get_item().path
                return await redirect_response(
                    req, f'gemini://{config.hostname}/{self.mp}/{path}')
            except Exception:
                return await error_response(
                    req,
                    'No main entry found in the ZIM archive'
                )

        try:
            entry = self._zim.get_entry_by_path(path)
            assert entry, f'Entry with path {path} not found'
        except Exception:
            if not entry:
                return await error_response(req, 'Not found')

        conv = crawler.ZimConverter(
            req_path=path,
            mountp=self.mp,
            autolinks=False
        )

        mime = entry.get_item().mimetype
        data = bytes(entry.get_item().content)

        conv.req_path = path
        conv.gemini_server_host = config.hostname

        if mime == 'text/html':
            gemtext = md2gemini(
                conv.convert(data.decode('UTF-8')),
                links=config.get('links_mode', 'paragraph'),
                checklist=False,
                strip_html=True,
                plain=True
            )

            if not gemtext:
                return await error_response(
                    req,
                    'Geminification resulted in an empty document'
                )

            return await data_response(req, gemtext.encode(), 'text/gemini')
        else:
            return await data_response(req, data, mime)
