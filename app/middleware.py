import uuid
import re 
from fastapi import Request
from starlette.responses import Response

REQUEST_ID_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{1,64}$")

async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", "")

    if not REQUEST_ID_PATTERN.fullmatch(request_id):
        request_id = str(uuid.uuid4())
    
    request.state.request_id = request_id

    response = await call_next(request)

    response.headers["X-Request-ID"] = request_id

    return response