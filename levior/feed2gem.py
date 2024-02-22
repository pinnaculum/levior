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

    def datesort(item):
        entry, feed = item

        if 'updated' in entry:
            return dateutil.parser.parse(entry['updated'])
        elif 'published' in entry:
            return dateutil.parser.parse(entry['published'])

    entries = [(item, feed) for feed in feeds for item in feed.entries]
    entries.sort(key=datesort, reverse=True)

    for fe, feed in entries:
        try:
            if hasattr(fe, 'published'):
                date = dateutil.parser.parse(fe.updated)
                print(type(date))
                buff.write(f'## {feed.feed.title} ({fe.published})\n')
            elif hasattr(fe, 'updated'):
                buff.write(f'## {feed.feed.title} ({fe.updated})\n')

            buff.write(f'=> {fe.link} {fe.title}\n')

            for lnk in fe.links:
                if lnk.get('href') != fe.link:
                    buff.write(f'=> {lnk.href} {lnk.href}\n')

            buff.write('\n')
        except Exception:
            continue

    return buff.getvalue()
