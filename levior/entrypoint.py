import sys
import asyncio
import argparse
from daemonize import Daemonize

from levior import __version__
from levior.__main__ import levior_configure_server


def parse_args(args: list = None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-c',
        '--config',
        dest='config_path',
        type=str,
        default=None,
        help='Configuration path')

    parser.add_argument(
        '-d',
        '--daemon',
        '--daemonize',
        dest='daemonize',
        action='store_true',
        default=False,
        help='Daemonize the server')

    parser.add_argument(
        '--pid-file',
        '--pid',
        dest='pid_file_path',
        type=str,
        default='levior.pid',
        help='Daemon process id (PID) file path')

    parser.add_argument(
        '--host',
        dest='hostname',
        type=str,
        default='localhost',
        help='Listening hostname for the Gemini service')

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
        '--https-only',
        dest='https_only',
        action='store_true',
        default=False,
        help='Only make requests on https URLs in server mode')

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
        '--mode',
        '--modes',
        '-m',
        dest='service_modes',
        type=str,
        default='proxy,server',
        help='Allowed service modes (comma-separated list). '
        'Can be "server" or "proxy" or "proxy,server". Default: "proxy,server"'
    )

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
        '--version',
        dest='show_version',
        action='store_true',
        default=False,
        help="Show levior's version and exit")

    return parser.parse_args(args=args)


def run():
    args = parse_args()

    if args.show_version:
        print(__version__)
        sys.exit(0)

    try:
        config, server = levior_configure_server(args)

        def daemon_run():
            return asyncio.run(server.serve())

        if config.daemonize:
            srvd = Daemonize(
                app='levior',
                pid=config.pid_file_path,
                action=daemon_run,
                verbose=True,
                auto_close_fds=False
            )
            srvd.start()
        else:
            daemon_run()
    except KeyboardInterrupt:
        pass
    except OSError as err:
        print(err, file=sys.stderr)
    except Exception:
        raise
