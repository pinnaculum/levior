import traceback
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Union
from yarl import URL
from trimgmi import Document as GmiDocument
from trimgmi import LineType as GmiLineType

from rdflib.namespace import XSD, DC, DCTERMS  # noqa
from rdflib import URIRef
from rdflib import Graph, Literal
from rdflib.store import NO_STORE, VALID_STORE


index_query = """
PREFIX dct: <http://purl.org/dc/terms/>

SELECT ?puri ?link ?created
WHERE {
    ?puri dct:references ?link .
    ?puri dct:created ?created .
}
ORDER BY DESC(?created)
"""

search_query = """
PREFIX dct: <http://purl.org/dc/terms/>

SELECT ?puri ?title
WHERE {
    ?puri dct:title ?title .
    ?puri dct:created ?created .
    OPTIONAL { ?puri dct:tableOfContents ?toc } .
    FILTER(regex(?title, ?query, "i") ||
        regex(?toc, ?query, "i"))
}
ORDER BY DESC(?created)
"""


def rdf_graph_init(path: Path,
                   identifier: Optional[str] = 'urn:levior:g0'):
    try:
        graph = Graph("BerkeleyDB",
                      bind_namespaces="rdflib",
                      identifier=identifier)

        rt = graph.open(str(path), create=False)

        if rt == NO_STORE:
            graph.open(str(path), create=True)
        else:
            assert rt == VALID_STORE, "The underlying store is corrupt"

        return graph
    except ImportError:
        return None
    except BaseException:
        traceback.print_exc()
        return None


def absolute_link_url(base: URL, lurl: URL) -> Union[URIRef,  None]:
    if lurl.scheme:
        return URIRef(str(lurl))
    elif not lurl.scheme and lurl.path:
        return URIRef(str(base.join(lurl)))
    else:
        return None


def utc_now():
    return datetime.now(timezone.utc).isoformat(
        timespec='seconds').replace('+00:00', 'Z')


def utc_now_literal() -> Literal:
    return Literal(utc_now(), datatype=XSD.dateTime)


def graph_resource(graph, gemtext: str, url: URL,
                   content_type: str,
                   title: str) -> None:
    """
    :param Graph graph: RDF graph
    :param str gemtext: The gemtext for thie resource
    :param URL url: Page URL
    :param str content_type: Content type for the document
    :param str title: Page title
    """
    if graph is None:
        return

    doc = GmiDocument()
    uref = URIRef(str(url))

    # For web pages, these attributes can change, so remove the triples first
    graph.remove((uref, DCTERMS.title, None))
    graph.remove((uref, DCTERMS.created, None))
    graph.remove((uref, DCTERMS.references, None))
    graph.remove((uref, DCTERMS.format, None))

    graph.add((uref, DCTERMS.created, utc_now_literal()))
    graph.add((uref, DCTERMS.format, Literal(content_type)))

    if title:
        graph.add((uref, DCTERMS.title, Literal(title)))
    else:
        graph.add((uref, DCTERMS.title, Literal('No title')))

    for text in gemtext.splitlines():
        doc.append(text)

        line = doc._lines[-1] if doc._lines else None
        if not line:
            continue

        if line.type == GmiLineType.LINK:
            lnk_uri = absolute_link_url(url, URL(line.extra))

            created = list(graph.objects(
                lnk_uri, DCTERMS.created, unique=True)
            )
            if not created:
                graph.add((lnk_uri, DCTERMS.created, utc_now_literal()))

            graph.add((uref, DCTERMS.references, lnk_uri))

            if line.text:  # title
                graph.add((lnk_uri, DCTERMS.title, Literal(line.text)))
        elif line.type in [GmiLineType.HEADING1,
                           GmiLineType.HEADING2,
                           GmiLineType.HEADING3] and line.text:
            graph.add((uref, DCTERMS.tableOfContents,
                       Literal(line.text)))

    graph.commit()
