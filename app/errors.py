from fastapi.responses import JSONResponse


class DomainError(Exception):
    def __init__(self, code, message, status=422):
        self.code = code
        self.message = message
        self.status = status


async def respond(_request, error):
    return JSONResponse({"code": error.code, "message": error.message}, status_code=error.status)
