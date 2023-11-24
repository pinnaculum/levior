import feedparser
import traceback
import io


def feed2tinylog(data: str) -> str:
    """
    Convert an RSS or Atom feed to a gemini tinylog

    :rtype: str
    """

    buff = io.StringIO()
    try:
        f = feedparser.parse(data)
    except Exception:
        traceback.print_exc()
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
