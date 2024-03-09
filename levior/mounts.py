import re
import traceback
import logging

from yarl import URL
from pathlib import Path
from aiogemini.server import Request, Response
from md2gemini import md2gemini

try:
    from libzim.reader import Archive
    from libzim.search import Query, Searcher
except ImportError:  # pragma: no cover
    have_zim = False
else:
    have_zim = True


from .response import data_response
from .response import data_response_init
from .response import error_response
from .response import input_response
from .response import redirect_response
from . import crawler


logger = logging.getLogger()


class ZimMountPoint:
    def __init__(self, mppath: str, source: Path, **opts):
        self.mp = mppath
        self._zim_path = source
        self._zim = None

        self.search_path = opts.get('search_path', '/search')
        self.search_max = opts.get('search_results_max', 4096)

    def setup(self):
        try:
            assert self._zim_path.is_file()

            logger.debug(f'Loading ZIM archive from: {self._zim_path}')

            self._zim = Archive(str(self._zim_path))
            self._searcher = Searcher(self._zim)
            return True
        except Exception:
            traceback.print_exc()
            return False

    async def search_results_response(self, req: Request, qstr: str):
        try:
            query = Query().set_query(qstr)
            search = self._searcher.search(query)
            search_count = search.getEstimatedMatches()

            response = data_response_init(req)

            await response.write(
                f'# Found {search_count} results for: {qstr}\n\n'.encode())

            for result in search.getResults(
                    0, min(self.search_max, search_count)):
                await response.write(f'=> {result}\n'.encode())

            await response.write_eof()
            return response
        except Exception:
            return await error_response(
                req,
                f'Failed to perform search for: {qstr}'
            )

    async def handle_request(self, req: Request, config) -> Response:
        # The URL of the zim mountpoint on the levior gemini server
        mountp_url = URL.build(
            scheme='gemini',
            host=config.hostname,
            port=config.port if config.port != 1965 else None,
            path=self.mp
        )

        raw_path = re.sub(self.mp, '', req.url.path)
        path = req.url.path.lstrip(self.mp)

        if raw_path == self.search_path:
            if not req.url.query:
                return await input_response(
                    req,
                    'ZIM: Enter a search query'
                )
            else:
                return await self.search_results_response(
                    req,
                    list(req.url.query.keys()).pop(0)
                )
        elif not path:
            try:
                # Redirect to the main entry
                return await redirect_response(
                    req, mountp_url.joinpath(
                        self._zim.main_entry.get_item().path
                    )
                )
            except Exception:  # pragma: no cover
                return await error_response(
                    req,
                    'No main entry found in the ZIM archive'
                )

        entry = self._zim.get_entry_by_path(path)
        if not entry:
            return await error_response(req, f'{path}: Not found')

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
                conv.convert(data.decode()),
                links=config.get('links_mode', 'paragraph'),
                checklist=False,
                strip_html=True,
                plain=True
            )

            if not gemtext:  # pragma: no cover
                return await error_response(
                    req,
                    'Geminification resulted in an empty document'
                )

            return await data_response(req, gemtext.encode(), 'text/gemini')
        else:
            return await data_response(req, data, mime)
