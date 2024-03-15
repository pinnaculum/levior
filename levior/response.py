from yarl import URL
from aiogemini import Status, GEMINI_MEDIA_TYPE
from aiogemini.server import Request, Response


def data_response_init(req, content_type=GEMINI_MEDIA_TYPE,
                       status=Status.SUCCESS) -> Response:  # pragma: no cover
    response = Response()
    response.content_type = content_type
    response.status = status
    response.start(req)
    return response


async def data_response(req, data, content_type=GEMINI_MEDIA_TYPE,
                        reason: str = None,
                        status=Status.SUCCESS) -> Response:
    response = Response()
    response.content_type = content_type
    response.status = status
    response.reason = reason
    response.start(req)
    await response.write(data)
    await response.write_eof()
    return response


async def input_response(req, text: str) -> Response:
    response = Response()
    response.reason = f'{text}'
    response.status = Status.INPUT
    response.start(req)
    await response.write(text.encode())
    await response.write_eof()
    return response


async def redirect_response(req, url: URL) -> Response:
    response = Response()
    response.reason = str(url)
    response.status = Status.REDIRECT_TEMPORARY
    response.start(req)
    await response.write_eof()
    return response


async def error_response(req,
                         reason: str,
                         status=Status.TEMPORARY_FAILURE,
                         message: str = '',
                         content_type=GEMINI_MEDIA_TYPE) -> Response:
    return await data_response(req, message.encode(),
                               status=status,
                               reason=reason)


async def proxy_reqrefused_response(req, message: str) -> Response:
    return await error_response(
        req,
        reason=message,
        status=Status.PROXY_REQUEST_REFUSED
    )


async def http_crawler_error_response(
        req: Request,
        http_status: int) -> Response:  # pragma: no cover
    status: Status = Status.TEMPORARY_FAILURE

    if http_status == 400:
        status = Status.BAD_REQUEST
    elif http_status == 404:
        status = Status.NOT_FOUND
    elif http_status in [502, 504]:
        status = Status.PROXY_ERROR
    elif http_status == 503:
        status = Status.SERVER_UNAVAILABLE
    elif http_status == 429:
        status = Status.SLOW_DOWN
    elif http_status == 410:
        status = Status.GONE

    return await error_response(
        req,
        f'# HTTP crawler error for: {req.url}\n'
        f'HTTP status code: {http_status}',
        status=status
    )


async def markdownification_error(req: Request,
                                  url: URL) -> Response:  # pragma: no cover
    return await error_response(
        req,
        f'Markdownification of {url} failed'
    )
