import asyncio
import argparse

from levior.__main__ import levior_main


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--port',
        '--serve-port',
        dest='port',
        type=int,
        default=1965,
        help='TCP port for the Gemini service')

    parser.add_argument(
        '--lang-default',
        dest='lang_default_iso639',
        type=str,
        default='en',
        help='ISO-639-1 code of the default language')

    parser.add_argument(
        '--socks5-proxy',
        dest='socks5_proxy',
        default=None,
        help="Socks proxy address (e.g: 'localhost:9050')")

    parser.add_argument(
        '--tor',
        dest='tor',
        action='store_true',
        default=False,
        help="Use tor's default socks proxy (localhost:9050)")

    parser.add_argument(
        '--cert',
        dest='gemini_cert',
        default=None,
        help="Path to Gemini server certificate")

    parser.add_argument(
        '--key',
        dest='gemini_key',
        default=None,
        help="Path to Gemini server key")

    parser.add_argument(
        '--hostname',
        dest='hostname',
        default='localhost',
        help="Server hostname")

    try:
        return asyncio.run(levior_main(parser.parse_args()))
    except KeyboardInterrupt:
        pass
    except Exception:
        raise
