import logging
from datetime import datetime
from typing import List

from IPy import IP
from aiogemini.server import Request, Response

from trimgmi import Document as GmiDocument


logger = logging.getLogger()


def get_req_ipaddr(req: Request) -> IP:
    try:
        peer = req.transport.get_extra_info('peername')
        return IP(peer[0])
    except BaseException:
        return None


def ipaddr_allowed(ip: IP, ipflist: List[IP]) -> bool:
    """
    Return True if ip belongs to one of the IP filters in ipflist
    """
    return any(ip in ipf for ipf in ipflist)


def log_request(access_log: GmiDocument,
                req: Request, reqd: datetime,
                resp: Response, url_config,
                title: str = None) -> None:
    """
    Log a request's URL and response status as a gemtext link.
    """

    rdt: str = reqd.strftime("%d/%b/%Y %H:%M:%S")
    client_ip = get_req_ipaddr(req)

    gemline: str = f'=> {req.url}  [{rdt}] '
    if title:
        gemline += title
    else:
        gemline += str(req.url)

    gemline += f'({client_ip}, status: {resp.status.value}, '
    gemline += f'ctype: {resp.content_type})'

    access_log.append(gemline)

    logger.info(gemline)
