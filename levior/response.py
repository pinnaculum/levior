from yarl import URL
from aiogemini import Status, GEMINI_MEDIA_TYPE
from aiogemini.server import Response


def data_response_init(req, content_type=GEMINI_MEDIA_TYPE,
                       status=Status.SUCCESS):
    response = Response()
    response.content_type = content_type
    response.status = status
    response.start(req)
    return response


async def data_response(req, data, content_type=GEMINI_MEDIA_TYPE,
                        status=Status.SUCCESS):
    response = Response()
    response.content_type = content_type
    response.status = status
    response.start(req)
    await response.write(data)
    await response.write_eof()
    return response


async def input_response(req, text: str):
    response = Response()
    response.reason = f'{text}'
    response.status = Status.INPUT
    response.start(req)
    await response.write(text.encode())
    await response.write_eof()
    return response


async def redirect_response(req, url: URL):
    response = Response()
    response.reason = str(url)
    response.status = Status.REDIRECT_TEMPORARY
    response.start(req)
    await response.write_eof()
    return response


async def error_response(req, message: str, content_type=GEMINI_MEDIA_TYPE):
    return await data_response(req, message.encode())
