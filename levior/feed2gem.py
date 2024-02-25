import feedparser
import traceback
import io

import dateutil.parser


def feed_fromdata(data: str):
    try:
        return feedparser.parse(data)
    except Exception:
        traceback.print_exc()
        return None


def feed2tinylog(data: str) -> str:
    """
    Convert an RSS or Atom feed to a gemini tinylog

    :rtype: str
    """

    buff = io.StringIO()

    f = feed_fromdata(data)
    if not f:
        return None

    buff.write(f'# {f.feed.title}\n')

    if hasattr(f.feed, 'description'):
        buff.write(f.feed.description + '\n')

    if hasattr(f.feed, 'published'):
        buff.write(f'Feed publishing date: {f.feed.published}\n')

    for fe in f.entries:
        try:
            if hasattr(fe, 'published'):
                buff.write(f'## {fe.published}\n')
            elif hasattr(fe, 'updated'):
                buff.write(f'## {fe.updated}\n')

            buff.write(f'=> {fe.link} {fe.title}\n')

            for lnk in fe.links:
                if lnk.get('href') != fe.link:
                    buff.write(f'=> {lnk.href} {lnk.href}\n')

            buff.write('\n')
        except Exception:
            continue

    return buff.getvalue()


def feeds2tinylog(feeds: list, sort_mode: str = 'date') -> str:
    """
    Convert a list of RSS or Atom feeds to a gemini tinylog

    :rtype: str
    """

    buff = io.StringIO()

    def fentry_date(entry):
        if 'updated' in entry:
            return dateutil.parser.parse(entry['updated'])
        elif 'published' in entry:
            return dateutil.parser.parse(entry['published'])

    entries = [(item, feed) for feed in feeds for item in feed.entries]
    entries.sort(key=lambda item: fentry_date(item[0]), reverse=True)

    shown_days = []

    for fe, feedo in entries:
        ftitle = feedo.feed_config.get('title', feedo.feed.title)
        fdate = fentry_date(fe)

        if not fdate:
            continue

        fday = fdate.strftime('%d/%m/%Y')

        if fday not in shown_days:
            buff.write(f'# {fday}\n')
            shown_days.append(fday)

        try:
            if feedo.feed_config.get('title_display_mode') == 'header':
                if hasattr(fe, 'published'):
                    buff.write(f'## {ftitle} ({fe.published})\n')
                elif hasattr(fe, 'updated'):
                    buff.write(f'## {ftitle} ({fe.updated})\n')

                buff.write(f'=> {fe.link}  {fe.title}\n')
            else:
                ed_fmt = feedo.feed_config.get('entry_date_format',
                                               '%H:%M:%S')

                if feedo.feed_config.get('show_entry_dates', False):
                    title = f"({ftitle}) {fe.title} ({fdate.strftime(ed_fmt)})"
                else:
                    title = f"({ftitle}) {fe.title}"

                buff.write(f'=> {fe.link}  {title}\n')

            if feedo.feed_config.get('show_entry_links', False) is True:
                for lnk in fe.links:
                    if lnk.get('href') != fe.link:
                        buff.write(f'=> {lnk.href} {lnk.href}\n')

            buff.write('\n')
        except Exception:
            continue

    return buff.getvalue()
