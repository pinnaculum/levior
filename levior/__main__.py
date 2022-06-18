import asyncio
from pathlib import Path

from aiogemini.security import TOFUContext
from aiogemini.server import Server

from .handler import create_levior_handler


try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except Exception:
    pass


__here__ = Path(__file__).parent


async def levior_main(args):
    certs = {}

    if args.gemini_cert and args.gemini_key:
        cert_path, key_path = args.gemini_cert, args.gemini_key
    else:
        cert_path = str(__here__.joinpath('localhost.crt'))
        key_path = str(__here__.joinpath('localhost.key'))

    security = TOFUContext(certs, cert_path, key_path)

    server = Server(
        security,
        create_levior_handler(args)
    )

    await server.serve()
