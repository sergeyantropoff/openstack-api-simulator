"""OpenStack-style error responses."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


class OpenStackError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        title: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.title = title or code


async def openstack_error_handler(_request: Request, exc: OpenStackError) -> JSONResponse:
    # Neutron/Glance often use {"NeutronError": ...} etc.; use a common envelope
    # that openstacksdk accepts for generic HTTP errors, plus itemized faults.
    body: dict[str, object]
    if exc.status_code in {401, 403}:
        body = {
            "error": {
                "code": exc.status_code,
                "title": exc.title,
                "message": exc.message,
            }
        }
    elif "Compute" in exc.code or exc.code.startswith("compute"):
        body = {
            "itemNotFound" if exc.status_code == 404 else "badRequest": {
                "code": exc.status_code,
                "message": exc.message,
            }
        }
    else:
        body = {
            "error": {
                "code": exc.status_code,
                "title": exc.title,
                "message": exc.message,
            }
        }
    return JSONResponse(status_code=exc.status_code, content=body)
