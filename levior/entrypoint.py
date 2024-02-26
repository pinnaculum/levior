import sys
import asyncio
import argparse
import traceback
import signal
from asyncio import tasks

from daemonize import Daemonize

from levior import crawler
from levior import __version__
from levior.__main__ import levior_configure_server

try:
    from pyppeteer.chromium_downloader import (check_chromium,
                                               download_chromium)
    have_pyppeteer = True
except Exception:
    traceback.print_exc()
    have_pyppeteer = False


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
        default=None,
        help='Cache path')

    parser.add_argument(
        '--cache-ttl',
        '--default-cache-ttl',
        dest='cache_ttl_default',
        type=int,
        default=60 * 60 * 24,
        help='Default cache items expiration lifetime (in seconds)')

    parser.add_argument(
        '--cache-size-limit',
        dest='cache_size_limit',
        type=int,
        default=2048,  # 2Gb
        help='Maximum cache size (in megabytes)')

    parser.add_argument(
        '--cache-eviction-policy',
        dest='cache_eviction_policy',
        type=str,
        default='least-recently-stored',
        help='Cache items eviction policy '
        '(least-recently-stored, least-recently-used, '
        'least-frequently-used, none)')

    parser.add_argument(
        '--cache-enable',
        dest='cache_enable',
        action='store_true',
        default=True,
        help='Enable or disable the cache system (deprecated, always enabled)')

    parser.add_argument(
        '--https-only',
        dest='https_only',
        action='store_true',
        default=False,
        help='Only make requests on https URLs in server mode')

    parser.add_argument(
        '--js',
        '--js-render',
        dest='js_render',
        action='store_true',
        default=False,
        help='Enable Javascript rendering (requires "requests-html")')

    parser.add_argument(
        '--js-force',
        dest='js_render_always',
        action='store_true',
        default=False,
        help='Always run Javascript rendering even if no script tags are found'
    )

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


async def stop_process(sig, loop) -> None:
    if crawler.rhtml_session:
        # Close the AsyncHTMLSession, this will stop the browser process
        await crawler.rhtml_session.close()

    for task in tasks.all_tasks():
        task.cancel()

    await asyncio.sleep(0.5)

    loop.close()
    sys.exit(0)


def run():
    loop = asyncio.get_event_loop()
    args = parse_args()

    if args.show_version:
        print(__version__)
        sys.exit(0)

    for sig in [signal.SIGINT, signal.SIGTERM, signal.SIGHUP]:
        loop.add_signal_handler(sig, lambda sig=sig:
                                asyncio.create_task(stop_process(sig, loop)))

    try:
        config, server = levior_configure_server(args)

        if have_pyppeteer and config.js_render:
            # If pyppeteer is installed and the user wants to
            # render JS code, check that chromium is installed early on

            if not check_chromium():
                download_chromium()

        def daemon_run():
            return loop.run_until_complete(server.serve())

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
    except asyncio.CancelledError:
        pass
    except Exception:
        raise
