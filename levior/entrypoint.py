import sys
import asyncio
import argparse

from levior.__main__ import levior_main


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-c',
        '--config',
        dest='config_path',
        type=str,
        default='levior.yaml',
        help='Configuration path')

    parser.add_argument(
        '--host',
        dest='hostname',
        type=str,
        default='localhost',
        help='Listen hostname for the Gemini service')

    parser.add_argument(
        '--port',
        dest='port',
        type=int,
        default=1965,
        help='TCP listen port for the Gemini service')

    parser.add_argument(
        '--cache-path',
        dest='cache_path',
        type=str,
        default='/tmp/levior',
        help='Cache path')

    parser.add_argument(
        '--cache-ttl',
        dest='cache_ttl_secs',
        type=int,
        default=60 * 10,
        help='Default cache Time-to-Live in seconds')

    parser.add_argument(
        '--cache-enable',
        dest='cache_enable',
        action='store_true',
        default=False,
        help='Enable or disable cache')

    parser.add_argument(
        '--verify-ssl',
        dest='verify_ssl',
        action='store_true',
        default=True,
        help='Verify SSL certificates for HTTPs websites')

    parser.add_argument(
        '--lang-default',
        dest='lang_default_iso639',
        type=str,
        default='en',
        help='ISO-639-1 code of the default language')

    parser.add_argument(
        '--feathers',
        dest='feathers',
        type=int,
        default=4,
        help='Feathers (0-7): lowest means lighter pages')

    parser.add_argument(
        '--links',
        dest='md_links',
        type=str,
        default='paragraph',
        help='Gemini links generation mode: '
             'paragraph, newline, at-end, copy, off')

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

    try:
        return asyncio.run(levior_main(parser.parse_args()))
    except KeyboardInterrupt:
        pass
    except OSError as err:
        print(err, file=sys.stderr)
    except Exception:
        raise
