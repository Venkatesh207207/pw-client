import logging
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from typing import Any, Dict

logger = logging.getLogger("core.exceptions")


def add_exception_handlers(app):
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        logger.info("HTTPException at %s: %s", request.url, exc.detail)
        content: Dict[str, Any] = {"detail": exc.detail}
        return JSONResponse(status_code=exc.status_code, content=content)

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        logger.warning("ValueError at %s: %s", request.url, exc)
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(RuntimeError)
    async def runtime_error_handler(request: Request, exc: RuntimeError):
        logger.error("RuntimeError at %s: %s", request.url, exc, exc_info=True)
        return JSONResponse(
            status_code=500, content={"detail": "Internal server error"}
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled Exception at %s: %s", request.url, exc)
        return JSONResponse(
            status_code=500, content={"detail": "Internal server error"}
        )
